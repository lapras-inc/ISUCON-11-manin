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
from constants import *
from dc import *


def _get_trend(cnxpool):
    """ISUの性格毎の最新のコンディション情報"""

    """
    先にDBにあるキャラクター一覧を取って
    キャラクターごとに
    最新のコンディションを取得し、そのコンディションごとの椅子の数を求めている

    キャラクター: {
        critical: [{isu_id, last_condition_timestamp}],
        info: [],
        warn: [],
    }


    """
    # TODO 採点基準にあるか微妙なので切り捨てることもあり得るかもしれない
    query = "SELECT `character` FROM `isu` GROUP BY `character`"
    character_list = [row["character"] for row in select_all(cnxpool, query)]

    res = []

    for character in character_list:
        query = "SELECT * FROM `isu` WHERE `character` = %s"
        isu_list = [Isu(**row) for row in select_all(cnxpool, query, (character,))]

        character_info_isu_conditions = []
        character_warning_isu_conditions = []
        character_critical_isu_conditions = []
        for isu in isu_list:
            query = "SELECT * FROM `isu_condition` WHERE `jia_isu_uuid` = %s ORDER BY timestamp DESC"
            conditions = [IsuCondition(**row) for row in select_all(cnxpool, query, (isu.jia_isu_uuid,))]

            if len(conditions) > 0:
                isu_last_condition = conditions[0]
                condition_level = calculate_condition_level(isu_last_condition.condition)

                trend_condition = TrendCondition(isu_id=isu.id, timestamp=int(isu_last_condition.timestamp.timestamp()))

                if condition_level == "info":
                    character_info_isu_conditions.append(trend_condition)
                elif condition_level == "warning":
                    character_warning_isu_conditions.append(trend_condition)
                elif condition_level == "critical":
                    character_critical_isu_conditions.append(trend_condition)

        character_info_isu_conditions.sort(key=lambda c: c.timestamp, reverse=True)
        character_warning_isu_conditions.sort(key=lambda c: c.timestamp, reverse=True)
        character_critical_isu_conditions.sort(key=lambda c: c.timestamp, reverse=True)

        res.append(
            TrendResponse(
                character=character,
                info=character_info_isu_conditions,
                warning=character_warning_isu_conditions,
                critical=character_critical_isu_conditions,
            )
        )

    return jsonify(res)