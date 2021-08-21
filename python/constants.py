from os import getenv
from subprocess import call
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import urllib.request
from random import random
from enum import Enum


TZ = ZoneInfo("Asia/Tokyo")
CONDITION_LIMIT = 20
APP_ROUTE = getenv("APP_ROUTE", "../")
FRONTEND_CONTENTS_PATH = APP_ROUTE + "public"
JIA_JWT_SIGNING_KEY_PATH = APP_ROUTE + "ec256-public.pem"
DEFAULT_ICON_FILE_PATH = APP_ROUTE + "NoImage.jpg"
DEFAULT_JIA_SERVICE_URL = "http://localhost:5000"
MYSQL_ERR_NUM_DUPLICATE_ENTRY = 1062

REDIS_USER_PREFIX = "user-"
REDIS_TREND_PREFIX = 'trend-'

REDIS_ISU_PREFIX = "isu-"

class CONDITION_LEVEL(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class SCORE_CONDITION_LEVEL(int, Enum):
    INFO = 3
    WARNING = 2
    CRITICAL = 1
