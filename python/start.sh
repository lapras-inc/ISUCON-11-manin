export MYSQL_HOST="127.0.0.1"
export MYSQL_PORT=3306
export MYSQL_USER=isucon
export MYSQL_DBNAME=isucondition
export MYSQL_PASS=isucon
export POST_ISUCONDITION_TARGET_BASE_URL="https://isucondition-1.t.isucon.dev"
ddtrace-run uwsgi --ini uwsgi.ini
