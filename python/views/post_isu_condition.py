from common import *
from dc import *


BUFFER = []
BUFFER_LIMIT = 100
DROP_PROBABILITY = 0.5


def _post_isu_condition(app, cnxpool, jia_isu_uuid):

    """
    JIAから翔んでくるISUからのコンディションを受け取る

    処理自体は思いように感じないのでとても多いのかもしれない。
    キャッシュなどでいい感じにバッファしてBulkでInsertさせたい

    加点要素
    """
    global BUFFER
    # TODO: 一定割合リクエストを落としてしのぐようにしたが、本来は全量さばけるようにすべき
    # 1/10になってる！
    drop_probability = DROP_PROBABILITY
    if random() <= drop_probability:
        app.logger.warning("drop post isu condition request")
        return "", 202
    try:
        req = [PostIsuConditionRequest(**row) for row in request.json]
    except:
        raise BadRequest("bad request body")

    cnx = cnxpool.connect()
    try:
        # トランザクション
        cnx.start_transaction()
        cur = cnx.cursor(dictionary=True)

        # ISUの存在チェック
        # TODO いらないかも？ 上でフィルタしたときに202返してるならココでNotFoundを返す理由があまりない
        query = "SELECT COUNT(*) AS cnt FROM `isu` WHERE `jia_isu_uuid` = %s"
        cur.execute(query, (jia_isu_uuid,))
        count = cur.fetchone()["cnt"]
        if count == 0:
            raise NotFound("not found: isu")

        for cond in req:
            # no sql
            if not is_valid_condition_format(cond.condition):
                raise BadRequest("bad request body")

            BUFFER.append(
                (
                    jia_isu_uuid,
                    datetime.fromtimestamp(cond.timestamp, tz=TZ),
                    cond.is_sitting,
                    cond.condition,
                    cond.warn_count,
                    cond.message,
                )
            )

            # cur.execute(
            #     query,
            #     (
            #         jia_isu_uuid,
            #         datetime.fromtimestamp(cond.timestamp, tz=TZ),
            #         cond.is_sitting,
            #         cond.condition,
            #         cond.warn_count,
            #         cond.message,
            #     ),
            # )

        if len(BUFFER) > 100:
            query = """
                INSERT
                INTO `isu_condition`
                (`jia_isu_uuid`, `timestamp`, `is_sitting`, `condition`, `warn_count`, `message`)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cur.executemany(query, BUFFER)
            BUFFER = []
        cnx.commit()
    except:
        cnx.rollback()
        raise
    finally:
        cnx.close()

    return "", 202
