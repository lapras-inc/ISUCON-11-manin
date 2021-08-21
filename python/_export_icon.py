from dc import *
from sqlalchemy.pool import QueuePool
import mysql.connector
import os

mysql_connection_env = {
    "host": getenv("MYSQL_HOST", "127.0.0.1"),
    "port": getenv("MYSQL_PORT", 3306),
    "user": getenv("MYSQL_USER", "isucon"),
    "password": getenv("MYSQL_PASS", "isucon"),
    "database": getenv("MYSQL_DBNAME", "isucondition"),
    "time_zone": "+09:00",
}
def select_all(cnxpool, query, *args, dictionary=True):
    cnx = cnxpool.connect()
    try:
        cur = cnx.cursor(dictionary=dictionary)
        cur.execute(query, *args)
        return cur.fetchall()
    finally:
        cnx.close()


# コネクションプール サイズ10
cnxpool = QueuePool(lambda: mysql.connector.connect(**mysql_connection_env), pool_size=10)

query = """
    SELECT * FROM `isu` ORDER BY `id` DESC
"""
isu_list = [Isu(**row) for row in select_all(cnxpool, query, ())]

for isu in isu_list:
    image = isu.image
    filepath = APP_ROUTE + f"api/isu/{isu.jia_isu_uuid}/icon"
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(image)
