# 汎用クエリ
# fetch allは少し気になる
def select_all(cnxpool, query, *args, dictionary=True):
    cnx = cnxpool.connect()
    try:
        cur = cnx.cursor(dictionary=dictionary)
        cur.execute(query, *args)
        return cur.fetchall()
    finally:
        cnx.close()

# 1行だけ期待しているが全件とってる
def select_row(cnxpool, *args, **kwargs):
    rows = select_all(cnxpool, *args, **kwargs)
    return rows[0] if len(rows) > 0 else None
