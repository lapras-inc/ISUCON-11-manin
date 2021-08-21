export MYSQL_HOST="127.0.0.1"
export MYSQL_PORT=3306
export MYSQL_USER=isucon
export MYSQL_DBNAME=isucondition
export MYSQL_PASS=isucon
export JIA_JWT_SIGNING_KEY_PATH=
export POST_ISUCONDITION_TARGET_BASE_URL="https://isucondition-1.t.isucon.dev"
export APP_ROUTE="/home/isucon/webapp"
/home/isucon/local/python/bin/ddtrace-run /home/isucon/local/python/bin/uwsgi --ini /home/isucon/webapp/python/uwsgi.ini
