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

from python.constants import *

def _post_initialize(cnxpool):
    """
        ベンチマーク最初に叩かれるAPI
        """
    if "jia_service_url" not in request.json:
        raise BadRequest("bad request body")

    call(APP_ROUTE + "sql/init.sh")

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
