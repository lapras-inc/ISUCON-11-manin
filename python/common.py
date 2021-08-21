from flask import Flask, request, session, send_file, jsonify, abort, make_response
from werkzeug.exceptions import (
    Forbidden,
    HTTPException,
    BadRequest,
    Unauthorized,
    NotFound,
    InternalServerError,
)
from constants import *
from dc import *

# 汎用クエリ
# fetch allは少し気になる
def select_all(cnxpool, query, *args, dictionary=True):
    cnx = cnxpool.connect()
    try:
        cur = cnx.cursor(dictionary=dictionary)
        cur.execute(query, *args)
        return cur.fetchall()
    finally:
        cnx.close()

# 1行だけ期待しているが全件とってる
def select_row(cnxpool, *args, **kwargs):
    rows = select_all(cnxpool, *args, **kwargs)
    return rows[0] if len(rows) > 0 else None


def calculate_condition_level(condition: str) -> CONDITION_LEVEL:
    """ISUのコンディションの文字列からコンディションレベルを計算"""
    warn_count = condition.count("=true")

    if warn_count == 0:
        condition_level = CONDITION_LEVEL.INFO
    elif warn_count in (1, 2):
        condition_level = CONDITION_LEVEL.WARNING
    elif warn_count == 3:
        condition_level = CONDITION_LEVEL.CRITICAL
    else:
        raise Exception("unexpected warn count")

    return condition_level


def get_user_id_from_session(cnxpool):
    jia_user_id = session.get("jia_user_id")

    if jia_user_id is None:
        raise Unauthorized("you are not signed in")
    # TODO
    # セッションがないときにクエリ飛んでる
    # sessionにjia_user_idが入ってるならuserからそれがあるかをみてあれば認可済
    query = "SELECT COUNT(*) FROM `user` WHERE `jia_user_id` = %s"
    (count,) = select_row(cnxpool, query, (jia_user_id,), dictionary=False)

    if count == 0:
        raise Unauthorized("you are not signed in")

    return jia_user_id


def is_valid_condition_format(condition_str: str) -> bool:
    """ISUのコンディションの文字列がcsv形式になっているか検証"""
    keys = ["is_dirty=", "is_overweight=", "is_broken="]
    value_true = "true"
    value_false = "false"

    idx_cond_str = 0
    for idx_keys, key in enumerate(keys):
        if not condition_str[idx_cond_str:].startswith(key):
            return False
        idx_cond_str += len(key)

        if condition_str[idx_cond_str:].startswith(value_true):
            idx_cond_str += len(value_true)
        elif condition_str[idx_cond_str:].startswith(value_false):
            idx_cond_str += len(value_false)
        else:
            return False

        if idx_keys < (len(keys) - 1):
            if condition_str[idx_cond_str] != ",":
                return False
            idx_cond_str += 1

    return idx_cond_str == len(condition_str)



def get_isu_conditions_from_db(
    jia_isu_uuid: str,
    end_time: datetime,
    condition_level: set,
    start_time: datetime,
    limit: int,
    isu_name: str,
) -> list[GetIsuConditionResponse]:
    """ISUのコンディションをDBから取得"""
    if start_time is None:
        query = """
            SELECT *
            FROM `isu_condition`
            WHERE `jia_isu_uuid` = %s AND `timestamp` < %s
            ORDER BY `timestamp` DESC
            """
        conditions = [IsuCondition(**row) for row in select_all(cnxpool, query, (jia_isu_uuid, end_time))]
    else:
        query = """
            SELECT *
            FROM `isu_condition`
            WHERE `jia_isu_uuid` = %s AND `timestamp` < %s AND %s <= `timestamp`
            ORDER BY `timestamp` DESC
            """
        conditions = [IsuCondition(**row) for row in select_all(cnxpool, query, (jia_isu_uuid, end_time, start_time))]

    condition_response = []
    for c in conditions:
        try:
            # 状態とレベルの変換
            c_level = calculate_condition_level(c.condition)
        except:
            continue
        # 検索条件に外うとうするかの比較
        # TODO ciriticalとかはエラー数できまってるのでSQLで処理できそう
        if c_level.value in condition_level:
            condition_response.append(
                GetIsuConditionResponse(
                    jia_isu_uuid=jia_isu_uuid,
                    isu_name=isu_name,
                    timestamp=int(c.timestamp.timestamp()),
                    is_sitting=c.is_sitting,
                    condition=c.condition,
                    condition_level=c_level,
                    message=c.message,
                )
            )
    #TODO 上のTODO を処理できるとSQLのLimitで処理できるようになる
    if len(condition_response) > limit:
        condition_response = condition_response[:limit]

    return condition_response




def calculate_graph_data_point(isu_conditions: list[IsuCondition]) -> GraphDataPoint:
    """複数のISUのコンディションからグラフの一つのデータ点を計算"""
    conditions_count = {"is_broken": 0, "is_dirty": 0, "is_overweight": 0}
    raw_score = 0
    for condition in isu_conditions:
        bad_conditions_count = 0
        # no sql
        if not is_valid_condition_format(condition.condition):
            raise Exception("invalid condition format")

        for cond_str in condition.condition.split(","):
            key_value = cond_str.split("=")

            condition_name = key_value[0]
            if key_value[1] == "true":
                conditions_count[condition_name] += 1
                bad_conditions_count += 1

        if bad_conditions_count >= 3:
            raw_score += SCORE_CONDITION_LEVEL.CRITICAL
        elif bad_conditions_count >= 1:
            raw_score += SCORE_CONDITION_LEVEL.WARNING
        else:
            raw_score += SCORE_CONDITION_LEVEL.INFO

    sitting_count = 0
    for condition in isu_conditions:
        if condition.is_sitting:
            sitting_count += 1

    isu_conditions_length = len(isu_conditions)

    return GraphDataPoint(
        score=int(raw_score * 100 / 3 / isu_conditions_length),
        percentage=ConditionsPercentage(
            sitting=int(sitting_count * 100 / isu_conditions_length),
            is_broken=int(conditions_count["is_broken"] * 100 / isu_conditions_length),
            is_overweight=int(conditions_count["is_overweight"] * 100 / isu_conditions_length),
            is_dirty=int(conditions_count["is_dirty"] * 100 / isu_conditions_length),
        ),
    )
