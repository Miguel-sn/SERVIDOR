import os

from dotenv import load_dotenv

load_dotenv()


def _inteiro(nome, padrao):
    valor = os.getenv(nome, str(padrao))
    try:
        return int(valor)
    except ValueError as erro:
        raise RuntimeError(f"{nome} deve ser um número inteiro") from erro


DB_CONFIG = {
    "host": os.getenv("DB_HOST", ""),
    "port": _inteiro("DB_PORT", 3306),
    "user": os.getenv("DB_USER", ""),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", ""),
    "charset": os.getenv("DB_CHARSET", "utf8mb4"),
    "cursorclass": None,
}
    