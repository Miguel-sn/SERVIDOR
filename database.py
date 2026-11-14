import os
import queue
import threading

import pymysql

from config import get_db_config


class TransactionConflictError(RuntimeError):
    pass


class _PooledConnection:
    def __init__(self, pool, connection):
        self._pool = pool
        self._connection = connection
        self._released = False

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def close(self):
        if not self._released:
            self._released = True
            self._pool.release(self._connection)


class _ConnectionPool:
    def __init__(self):
        self._connections = queue.LifoQueue(maxsize=self._pool_size)
        self._slots = threading.BoundedSemaphore(self._pool_size)

    @property
    def _pool_size(self):
        try:
            return max(1, int(os.getenv("DB_POOL_SIZE", "5")))
        except ValueError as erro:
            raise RuntimeError("DB_POOL_SIZE deve ser um número inteiro") from erro

    def acquire(self):
        if not self._slots.acquire(timeout=self._connect_timeout):
            raise TimeoutError("Tempo limite para obter conexão com o banco excedido")

        try:
            connection = self._get_available()
            if connection is None:
                connection = self._create()
            connection.ping(reconnect=True)
            return _PooledConnection(self, connection)
        except Exception:
            self._slots.release()
            raise

    def _get_available(self):
        try:
            return self._connections.get_nowait()
        except queue.Empty:
            return None

    @property
    def _connect_timeout(self):
        try:
            return max(1, int(os.getenv("DB_CONNECT_TIMEOUT", "5")))
        except ValueError as erro:
            raise RuntimeError("DB_CONNECT_TIMEOUT deve ser um número inteiro") from erro

    def _create(self):
        configuracao = get_db_config()
        return pymysql.connect(
            **configuracao,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=self._connect_timeout,
            read_timeout=max(1, int(os.getenv("DB_READ_TIMEOUT", "5"))),
            write_timeout=max(1, int(os.getenv("DB_WRITE_TIMEOUT", "5"))),
            autocommit=False,
        )

    def release(self, connection):
        try:
            connection.ping(reconnect=False)
            self._connections.put_nowait(connection)
        except (queue.Full, pymysql.MySQLError):
            connection.close()
        finally:
            self._slots.release()


_pool = _ConnectionPool()


def get_db_connection():
    return _pool.acquire()


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
