import pymysql
from config import DB_CONFIG


class TransactionConflictError(RuntimeError):
    pass


def get_db_connection():
    db_config = dict(DB_CONFIG)
    db_config["cursorclass"] = pymysql.cursors.DictCursor
    return pymysql.connect(**db_config)


def fetch_all(query, params=()):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    finally:
        conn.close()


def fetch_one(query, params=()):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()
    finally:
        conn.close()


def execute_query(query, params=()):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid
    finally:
        conn.close()


def execute_transaction(queries, expected_rowcounts=None):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            resultados = []
            for indice, (query, params) in enumerate(queries):
                cursor.execute(query, params)
                if (
                    expected_rowcounts is not None
                    and indice in expected_rowcounts
                    and cursor.rowcount != expected_rowcounts[indice]
                ):
                    raise TransactionConflictError(
                        "A operação foi alterada por outra solicitação"
                    )
                resultados.append(cursor.lastrowid)
            conn.commit()
            return resultados
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
