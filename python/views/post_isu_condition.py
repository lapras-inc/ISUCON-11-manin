from os import getenv
from subprocess import call
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import urllib.request
from random import random
from enum import Enum
from flask import Flask, request, session, send_file, jsonify, abort, make_response
from flask.json import JSONEncoder
from werkzeug.exceptions import (
    Forbidden,
    HTTPException,
    BadRequest,
    Unauthorized,
    NotFound,
    InternalServerError,
)
import mysql.connector
from sqlalchemy.pool import QueuePool
import jwt

from common import *
from dc import *


def _post_isu_condition(app, cnxpool, jia_isu_uuid):

    """
    JIAから翔んでくるISUからのコンディションを受け取る

    処理自体は思いように感じないのでとても多いのかもしれない。
    キャッシュなどでいい感じにバッファしてBulkでInsertさせたい

    加点要素
    """
    # TODO: 一定割合リクエストを落としてしのぐようにしたが、本来は全量さばけるようにすべき
    # 1/10になってる！
    drop_probability = 0.9
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
        query = "SELECT COUNT(*) AS cnt FROM `isu` WHERE `jia_isu_uuid` = %s"
        cur.execute(query, (jia_isu_uuid,))
        count = cur.fetchone()["cnt"]
        if count == 0:
            raise NotFound("not found: isu")

        for cond in req:
            # no sql
            if not is_valid_condition_format(cond.condition):
                raise BadRequest("bad request body")

            query = """
                INSERT
                INTO `isu_condition` (`jia_isu_uuid`, `timestamp`, `is_sitting`, `condition`, `message`)
                VALUES (%s, %s, %s, %s, %s)
                """
            cur.execute(
                query,
                (
                    jia_isu_uuid,
                    datetime.fromtimestamp(cond.timestamp, tz=TZ),
                    cond.is_sitting,
                    cond.condition,
                    cond.message,
                ),
            )

        cnx.commit()
    except:
        cnx.rollback()
        raise
    finally:
        cnx.close()

    return "", 202
