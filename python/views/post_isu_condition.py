import threading

from common import *
from dc import *
from constants import *


BUFFER = []
BUFFER_LIMIT = 100


# スレッド処理クラス
class InsertThread(threading.Thread):

    def __init__(self, param_list, cnxpool):
        super().__init__()
        self.daemon = True
        self.param_list = param_list
        self.cnxpool = cnxpool

    def run(self):
        cnx = self.cnxpool.connect()
        cnx.start_transaction()
        cur = cnx.cursor(dictionary=True)
        query = """
            INSERT
            INTO `isu_condition`
            (`jia_isu_uuid`, `timestamp`, `is_sitting`, `condition`, `warn_count`, `message`)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cur.executemany(query, self.param_list)
        cnx.commit()


def _post_isu_condition(app, cnxpool, jia_isu_uuid, r):

    """
    JIAから翔んでくるISUからのコンディションを受け取る

    処理自体は思いように感じないのでとても多いのかもしれない。
    キャッシュなどでいい感じにバッファしてBulkでInsertさせたい

    加点要素
    """
    global BUFFER
    try:
        req = [PostIsuConditionRequest(**row) for row in request.json]
    except:
        raise BadRequest("bad request body")

    # ISUの存在チェック
    result = r.get(REDIS_ISU_PREFIX + jia_isu_uuid)
    if result is None:
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

    if len(BUFFER) > 100:
        thread = InsertThread(BUFFER, cnxpool)
        thread.start()
        BUFFER = []

    return "", 202
