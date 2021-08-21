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


def _get_isu_list(cnxpool, r):

    """ISUの一覧を取得"""
    jia_user_id = get_user_id_from_session(r)

    query = """
        SELECT * FROM `isu` WHERE `jia_user_id` = %s ORDER BY `id` DESC
    """
    isu_list = [Isu(**row) for row in select_all(cnxpool, query, (jia_user_id,))]

    isu_uuid_list = [f'\'{isu.jia_isu_uuid}\'' for isu in isu_list]
    isucon_query = """
    SELECT
        *
    FROM
        isu_condition
    where
        (`jia_isu_uuid`, timestamp) in(
            select
                `jia_isu_uuid`,
                max(timestamp)
            from
                `isu_condition`
            where
                 `jia_isu_uuid` in ({id_list})
            group by
                `jia_isu_uuid`
        )
    """.format(id_list=','.join(isu_uuid_list))
    isucon_map = {
        row['jia_isu_uuid']: IsuCondition(**row) for row in select_all(cnxpool, isucon_query)
    }

    response_list = []
    for isu in isu_list:
        last_condition = isucon_map.get(isu.jia_isu_uuid)

        formatted_condition = None
        if last_condition:
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
