import os
from urllib.parse import urlparse
import mysql.connector

from dotenv import load_dotenv

load_dotenv()

link_banco = os.getenv(
    "MYSQL_PUBLIC_URL",
    "mysql://root:oLIRtzxiMczdiQgsdeudzgxaZHfJwMjC@ballast.proxy.rlwy.net:30074/railway",
)
url = urlparse(link_banco)

conexao = mysql.connector.connect(
    host=url.hostname,
    user=url.username,
    password=url.password,
    database=url.path[1:],
    port=url.port,
)


def _inteiro(nome, padrao):
    valor = os.getenv(nome, str(padrao))
    try:
        return int(valor)
    except ValueError as erro:
        raise RuntimeError(f"{nome} deve ser um número inteiro") from erro


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": _inteiro("DB_PORT", 3306),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "loca_ja"),
    "charset": os.getenv("DB_CHARSET", "utf8mb4"),
    "cursorclass": None,
}

# A classe do cursor é preenchida no database.py para facilitar a importação.
