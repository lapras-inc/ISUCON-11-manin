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

from constants import *
from common import *

def set_isu_to_redis(cnxpool, r):
    query = """
            SELECT jia_isu_uuid FROM `isu`
        """
    for row in select_all(cnxpool, query, ()):
        # redisにisuを登録
        r.set(REDIS_ISU_PREFIX + row['jia_isu_uuid'], 1)

def _post_initialize(cnxpool, r):
    """
        ベンチマーク最初に叩かれるAPI
        """
    if "jia_service_url" not in request.json:
        raise BadRequest("bad request body")

    call(APP_ROUTE + "sql/init.sh")
    set_isu_to_redis(cnxpool, r)

    cnx = cnxpool.connect()
    try:
        cur = cnx.cursor()
        query = """
                INSERT INTO
                `isu_association_config` (`name`, `url`) VALUES (%s, %s) ON DUPLICATE KEY UPDATE `url` = VALUES(`url`)
            """
        cur.execute(query, ("jia_service_url", request.json["jia_service_url"]))
        cnx.commit()
    finally:
        cnx.close()



