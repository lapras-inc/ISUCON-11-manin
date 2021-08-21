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


def _get_isu_list(cnxpool):

    """ISUの一覧を取得"""
    jia_user_id = get_user_id_from_session(cnxpool)

    query = """
        SELECT * FROM `isu` WHERE `jia_user_id` = %s ORDER BY `id` DESC
    """
    isu_list = [Isu(**row) for row in select_all(cnxpool, query, (jia_user_id,))]

    response_list = []
    for isu in isu_list:
        # 状態情報があるか
        found_last_condition = True
        # TODO N 1
        query = "SELECT * FROM `isu_condition` WHERE `jia_isu_uuid` = %s ORDER BY `timestamp` DESC LIMIT 1"
        row = select_row(cnxpool, query, (isu.jia_isu_uuid,))
        if row is None:
            found_last_condition = False
        last_condition = IsuCondition(**row) if found_last_condition else None

        formatted_condition = None
        if found_last_condition:
            formatted_condition = GetIsuConditionResponse(
                jia_isu_uuid=last_condition.jia_isu_uuid,
                isu_name=isu.name,
                timestamp=int(last_condition.timestamp.timestamp()),
                is_sitting=last_condition.is_sitting,
                condition=last_condition.condition,
                condition_level=calculate_condition_level(last_condition.condition),
                message=last_condition.message,
            )

        response_list.append(
            GetIsuListResponse(
                id=isu.id,
                jia_isu_uuid=isu.jia_isu_uuid,
                name=isu.name,
                character=isu.character,
                latest_isu_condition=formatted_condition,
            )
        )

    return jsonify(response_list)
