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
        with latest_condition as (
            SELECT *
            FROM isu_condition
            where (`jia_isu_uuid`, timestamp) in
                  (select `jia_isu_uuid`, max(timestamp) from `isu_condition` group by `jia_isu_uuid`)
        )
        SELECT `isu`.id,
                `isu`.jia_user_id,
               `isu`.jia_isu_uuid,
               `isu`.name,
               `isu`.`character`,
               `isu`.`created_at`,
               `isu`.`updated_at`,
               `isu`.`image`,
               ic.id as ic_id,
               ic.timestamp,
               ic.is_sitting,
               ic.`condition`,
               ic.warn_count,
               ic.message
        FROM `isu`
                 left outer join latest_condition ic on isu.jia_isu_uuid = ic.jia_isu_uuid
        WHERE `jia_user_id` = %s
        ORDER BY `isu`.`id` DESC
    """

    response_list = []
    for row in select_all(cnxpool, query, (jia_user_id,)):
        isu = Isu(**{
            'id': row['id'],
            'jia_isu_uuid': row['jia_isu_uuid'],
            'name': row['name'],
            'image': row['image'],
            'character': row['character'],
            'jia_user_id': row['jia_user_id'],
            'created_at': row['created_at'],
            'updated_at': row['updated_at']
        })
        # 状態情報があるか
        found_last_condition = row['ic_id'] is None
        last_condition = IsuCondition(**{
            'id': row['ic_id'],
            'jia_isu_uuid': row['jia_isu_uuid'],
            'timestamp': row['timestamp'],
            'is_sitting': row['is_sitting'],
            'condition': row['condition'],
            'message': row['message'],
            'warn_count': row['warn_count'],
            'created_at': row['created_at'],
        }) if found_last_condition else None

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
