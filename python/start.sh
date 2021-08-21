#!/bin/bash
source /home/isucon/env.sh
export APP_ROUTE="/home/isucon/webapp/"
/home/isucon/local/python/bin/uwsgi --ini /home/isucon/webapp/python/uwsgi.ini