import urllib.request
from flask.json import JSONEncoder
import mysql.connector
from sqlalchemy.pool import QueuePool
import jwt
import os

import redis

from common import *
from dc import *
from views.post_initialize import _post_initialize
from views.get_isu_list import _get_isu_list
from views.post_isu_condition import _post_isu_condition
from views.get_trend import _get_trend

class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Isu):
            cols = ["id", "jia_isu_uuid", "name", "character"]
            return {col: obj.__dict__[col] for col in cols}
        return JSONEncoder.default(self, obj)


app = Flask(__name__, static_folder=f"{FRONTEND_CONTENTS_PATH}/assets", static_url_path="/assets")
app.session_cookie_name = "isucondition_python"
app.secret_key = getenv("SESSION_KEY", "isucondition")
app.json_encoder = CustomJSONEncoder
app.send_file_max_age_default = timedelta(0)
app.config["JSON_AS_ASCII"] = False





@app.errorhandler(HTTPException)
def error_handler(e):
    return make_response(e.description, e.code, {"Content-Type": "text/plain"})


mysql_connection_env = {
    "host": getenv("MYSQL_HOST", "127.0.0.1"),
    "port": getenv("MYSQL_PORT", 3306),
    "user": getenv("MYSQL_USER", "isucon"),
    "password": getenv("MYSQL_PASS", "isucon"),
    "database": getenv("MYSQL_DBNAME", "isucondition"),
    "time_zone": "+09:00",
}

# コネクションプール サイズ10
cnxpool = QueuePool(lambda: mysql.connector.connect(**mysql_connection_env), pool_size=10)

r = redis.Redis(host=getenv("REDIS_HOST", "127.0.0.1"), port=6379, db=0)

with open(JIA_JWT_SIGNING_KEY_PATH, "rb") as f:
    jwt_public_key = f.read()

post_isu_condition_target_base_url = getenv("POST_ISUCONDITION_TARGET_BASE_URL")
if post_isu_condition_target_base_url is None:
    raise Exception("missing: POST_ISUCONDITION_TARGET_BASE_URL")


def get_jia_service_url() -> str:
    """
    JIAのサーバ登録なので多分キャッシュにできるかも
    """
    # TODO ほぼ普遍なので一回取ってキャッシュで良さそう
    query = "SELECT * FROM `isu_association_config` WHERE `name` = %s"
    config = select_row(cnxpool, query, ("jia_service_url",))
    return config["url"] if config is not None else DEFAULT_JIA_SERVICE_URL


@app.route("/initialize", methods=["POST"])
def post_initialize():
    _post_initialize(cnxpool, r)
    return {"language": "python"}


@app.route("/api/auth", methods=["POST"])
def post_auth():
    """サインアップ・サインイン"""
    req_authorization_header = request.headers.get("Authorization")
    if req_authorization_header is None:
        raise Forbidden("forbidden")

    try:
        req_jwt = req_authorization_header.removeprefix("Bearer ")
        req_jwt_header = jwt.get_unverified_header(req_jwt)
        req_jwt_payload = jwt.decode(req_jwt, jwt_public_key, algorithms=[req_jwt_header["alg"]])
    except jwt.exceptions.PyJWTError:
        raise Forbidden("forbidden")

    jia_user_id = req_jwt_payload.get("jia_user_id")
    if type(jia_user_id) is not str:
        raise BadRequest("invalid JWT payload")

    cnx = cnxpool.connect()
    try:
        cur = cnx.cursor()
        # インサート時にキーが重複してたらそれは無視するINSERT
        # ここにレコードがあるIDは認可済としている
        query = "INSERT IGNORE INTO user (`jia_user_id`) VALUES (%s)"
        cur.execute(query, (jia_user_id,))
        cnx.commit()

        r.set(REDIS_USER_PREFIX + jia_user_id, 1)
    finally:
        cnx.close()

    session["jia_user_id"] = jia_user_id

    return ""


@app.route("/api/signout", methods=["POST"])
def post_signout():
    """サインアウト"""
    get_user_id_from_session(r)
    session.clear()
    return ""


@app.route("/api/user/me", methods=["GET"])
def get_me():
    """サインインしている自分自身の情報を取得"""
    jia_user_id = get_user_id_from_session(r)
    return {"jia_user_id": jia_user_id}


@app.route("/api/isu", methods=["GET"])
def get_isu_list():
    return _get_isu_list(cnxpool, r)


@app.route("/api/isu", methods=["POST"])
def post_isu():
    """ISUを登録"""
    jia_user_id = get_user_id_from_session(r)

    use_default_image = False

    jia_isu_uuid = request.form.get("jia_isu_uuid")
    isu_name = request.form.get("isu_name")
    image = request.files.get("image")

    if image is None:
        use_default_image = True

    if use_default_image:
        # TODO 毎回Openするなら開いとけ。
        with open(DEFAULT_ICON_FILE_PATH, "rb") as f:
            image = f.read()
    else:
        image = image.read()

    cnx = cnxpool.connect()
    # トランザクションここから
    try:
        cnx.start_transaction()
        cur = cnx.cursor(dictionary=True)

        try:
            query = """
                INSERT
                INTO `isu` (`jia_isu_uuid`, `name`, `jia_user_id`)
                VALUES (%s, %s, %s)
                """
            cur.execute(query, (jia_isu_uuid, isu_name, jia_user_id))

            filepath = APP_ROUTE + f"api/isu/{jia_isu_uuid}/icon"
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(image)

            # redisにisuを登録
            r.set(REDIS_ISU_PREFIX + jia_isu_uuid, 1)
            r.set(f'{REDIS_ICON_PREFIX}{jia_user_id}{jia_isu_uuid}', 1)

        except mysql.connector.errors.IntegrityError as e:
            if e.errno == MYSQL_ERR_NUM_DUPLICATE_ENTRY:
                abort(409, "duplicated: isu")
            raise

        target_url = f"{get_jia_service_url()}/api/activate"
        body = {
            "target_base_url": post_isu_condition_target_base_url,
            "isu_uuid": jia_isu_uuid,
        }
        headers = {
            "Content-Type": "application/json",
        }
        req_jia = urllib.request.Request(target_url, json.dumps(body).encode(), headers)
        try:
            with urllib.request.urlopen(req_jia) as res:
                isu_from_jia = json.load(res)
        except urllib.error.HTTPError as e:
            app.logger.error(f"JIAService returned error: status code {e.code}, message: {e.reason}")
            abort(e.code, "JIAService returned error")
        except urllib.error.URLError as e:
            app.logger.error(f"failed to request to JIAService: {e.reason}")
            raise InternalServerError

        # ISUの正確を登録する
        query = "UPDATE `isu` SET `character` = %s WHERE  `jia_isu_uuid` = %s"
        cur.execute(query, (isu_from_jia["character"], jia_isu_uuid))
        # ISUの情報を取得して戻す
        # TODO where句が多いかも
        # トランザクションに入れる意味もなさそう
        query = "SELECT * FROM `isu` WHERE `jia_user_id` = %s AND `jia_isu_uuid` = %s"
        cur.execute(query, (jia_user_id, jia_isu_uuid))
        isu = Isu(**cur.fetchone())

        cnx.commit()
    except:
        cnx.rollback()
        raise
    finally:
        cnx.close()

        # ↑トランザクションここまで

    return jsonify(isu), 201


@app.route("/api/isu/<jia_isu_uuid>", methods=["GET"])
def get_isu_id(jia_isu_uuid):
    """ISUの情報を取得"""

    # TODO
    # uuidが一意だったらuser_idはクエリにはいらないのでこれ自体省けるが無認可でAPIを叩くテストが混ざってると死ぬ
    jia_user_id = get_user_id_from_session(r)
    query = "SELECT * FROM `isu` WHERE `jia_user_id` = %s AND `jia_isu_uuid` = %s"
    res = select_row(cnxpool, query, (jia_user_id, jia_isu_uuid))
    if res is None:
        raise NotFound("not found: isu")

    return jsonify(Isu(**res))


@app.route("/api/isu/<jia_isu_uuid>/icon", methods=["GET"])
def get_isu_icon(jia_isu_uuid):
    """ISUのアイコンを取得"""
    # TODO nginx配信に切り替えたい
    jia_user_id = get_user_id_from_session(r)
    res = r.get(f'{REDIS_ICON_PREFIX}{jia_user_id}{jia_isu_uuid}')

    if res is None:
        raise NotFound("not found: isu")

    with open(APP_ROUTE + f'api/isu/{jia_isu_uuid}/icon', "rb") as f:
        image = f.read()

    return make_response(image, 200, {"Content-Type": "image/jpeg"})


@app.route("/api/isu/<jia_isu_uuid>/graph", methods=["GET"])
def get_isu_graph(jia_isu_uuid):
    """ISUのコンディショングラフ描画のための情報を取得"""
    jia_user_id = get_user_id_from_session(r)

    dt = request.args.get("datetime")
    if dt is None:
        raise BadRequest("missing: datetime")
    try:
        dt = datetime.fromtimestamp(int(dt), tz=TZ)
    except:
        raise BadRequest("bad format: datetime")
    dt = truncate_datetime(dt)

    # ISUの存在確認をしている
    count = r.get(f'{REDIS_ICON_PREFIX}{jia_user_id}{jia_isu_uuid}')
    if count is None:
        raise NotFound("not found: isu")
    # ISUのグラフ情報を取得している
    res = generate_isu_graph_response(jia_isu_uuid, dt)
    return jsonify(res)


def truncate_datetime(dt: datetime) -> datetime:
    """datetime 値の指定した粒度で切り捨てる"""
    return datetime(dt.year, dt.month, dt.day, dt.hour, tzinfo=dt.tzinfo)


# TODO おっそい
def generate_isu_graph_response(jia_isu_uuid: str, graph_date: datetime) -> list[GraphResponse]:
    """グラフのデータ点を一日分生成"""
    data_points = []
    conditions_in_this_hour = []
    timestamps_in_this_hour = []
    start_time_in_this_hour = None
    start_time_of_this_day = graph_date
    end_time_of_this_day = graph_date + 86400  # 1日分

    query = "SELECT * FROM `isu_condition` WHERE `jia_isu_uuid` = %s and `timestamp` >= %s and timestamp =< %s ORDER BY `timestamp` ASC"
    rows = select_all(cnxpool, query, (jia_isu_uuid, start_time_of_this_day, end_time_of_this_day))
    for row in rows:
        condition = IsuCondition(**row)
        # condition情報の時刻を時間単位に切り捨てる
        truncated_condition_time = truncate_datetime(condition.timestamp)
        # start_time_in_this_hour は初めてその時刻でのポイントされたtimestampが入っている
        # その時刻で最初のときだけグラフポイントGraphDataPointWithInfo を作る
        # ここは時刻ごとのBufferで時刻の切り替わりでリセットしてる
        if truncated_condition_time != start_time_in_this_hour:
            if len(conditions_in_this_hour) > 0:
                data_points.append(
                    GraphDataPointWithInfo(
                        jia_isu_uuid=jia_isu_uuid,
                        start_at=start_time_in_this_hour,
                        data=calculate_graph_data_point(conditions_in_this_hour),
                        condition_timestamps=timestamps_in_this_hour,
                    )
                )
            start_time_in_this_hour = truncated_condition_time
            conditions_in_this_hour = []
            timestamps_in_this_hour = []
        conditions_in_this_hour.append(condition)
        timestamps_in_this_hour.append(int(condition.timestamp.timestamp()))

    if len(conditions_in_this_hour) > 0:
        data_points.append(
            GraphDataPointWithInfo(
                jia_isu_uuid=jia_isu_uuid,
                start_at=start_time_in_this_hour,
                data=calculate_graph_data_point(conditions_in_this_hour),
                condition_timestamps=timestamps_in_this_hour,
            )
        )

    end_time = graph_date + timedelta(days=1)
    start_index = len(data_points)
    end_next_index = len(data_points)
    for i, graph in enumerate(data_points):
        if start_index == len(data_points) and graph.start_at >= graph_date:
            start_index = i
        if end_next_index == len(data_points) and graph.start_at > end_time:
            end_next_index = i

    filtered_data_points = []
    if start_index < end_next_index:
        filtered_data_points = data_points[start_index:end_next_index]

    response_list = []
    index = 0
    this_time = graph_date

    while this_time < graph_date + timedelta(days=1):
        data = None
        timestamps = []

        if index < len(filtered_data_points):
            data_with_info = filtered_data_points[index]

            if data_with_info.start_at == this_time:
                data = data_with_info.data
                timestamps = data_with_info.condition_timestamps
                index += 1

        response_list.append(
            GraphResponse(
                start_at=int(this_time.timestamp()),
                end_at=int((this_time + timedelta(hours=1)).timestamp()),
                data=data,
                condition_timestamps=timestamps,
            )
        )

        this_time += timedelta(hours=1)

    return response_list


# TODO ちょっと遅い
# order by timestampが遅い
@app.route("/api/condition/<jia_isu_uuid>", methods=["GET"])
def get_isu_confitions(jia_isu_uuid):
    """ISUのコンディションを取得"""
    jia_user_id = get_user_id_from_session(r)

    try:
        end_time = datetime.fromtimestamp(int(request.args.get("end_time")), tz=TZ)
    except:
        raise BadRequest("bad format: end_time")

    # 検索条件
    condition_level_csv = request.args.get("condition_level")
    if condition_level_csv is None:
        raise BadRequest("missing: condition_level")
    condition_level = set(condition_level_csv.split(","))

    start_time_str = request.args.get("start_time")
    start_time = None
    if start_time_str is not None:
        try:
            start_time = datetime.fromtimestamp(int(start_time_str), tz=TZ)
        except:
            raise BadRequest("bad format: start_time")

    # ISU名取得
    query = "SELECT name FROM `isu` WHERE `jia_isu_uuid` = %s AND `jia_user_id` = %s"
    row = select_row(cnxpool, query, (jia_isu_uuid, jia_user_id))
    if row is None:
        raise NotFound("not found: isu")
    isu_name = row["name"]

    # ISUの状態をdbから取得
    # SQLあり
    condition_response = get_isu_conditions_from_db(
        cnxpool,
        jia_isu_uuid,
        end_time,
        condition_level,
        start_time,
        CONDITION_LIMIT,
        isu_name,
    )

    return jsonify(condition_response)


@app.route("/api/trend", methods=["GET"])
def get_trend():
    return _get_trend(cnxpool ,r)


@app.route("/api/condition/<jia_isu_uuid>", methods=["POST"])
def post_isu_condition(jia_isu_uuid):
    return _post_isu_condition(app, cnxpool, jia_isu_uuid, r)


def get_index(**kwargs):
    return send_file(f"{FRONTEND_CONTENTS_PATH}/index.html")


app.add_url_rule("/", view_func=get_index)
app.add_url_rule("/isu/<jia_isu_uuid>", view_func=get_index)
app.add_url_rule("/isu/<jia_isu_uuid>/condition", view_func=get_index)
app.add_url_rule("/isu/<jia_isu_uuid>/graph", view_func=get_index)
app.add_url_rule("/register", view_func=get_index)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=getenv("SERVER_APP_PORT", 3000), threaded=True)
