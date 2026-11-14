import os

from dotenv import load_dotenv

load_dotenv()


_VARIAVEIS_BANCO_OBRIGATORIAS = (
    "DB_HOST",
    "DB_PORT",
    "DB_USER",
    "DB_PASSWORD",
    "DB_NAME",
)


def _inteiro(nome, valor):
    try:
        return int(valor)
    except ValueError as erro:
        raise RuntimeError(f"{nome} deve ser um número inteiro") from erro


def get_db_config():
    ausentes = [
        nome for nome in _VARIAVEIS_BANCO_OBRIGATORIAS if not os.getenv(nome)
    ]
    if ausentes:
        raise RuntimeError(
            "Variáveis obrigatórias do banco ausentes: " + ", ".join(ausentes)
        )

    return {
        "host": os.environ["DB_HOST"],
        "port": _inteiro("DB_PORT", os.environ["DB_PORT"]),
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
        "database": os.environ["DB_NAME"],
        "charset": os.getenv("DB_CHARSET", "utf8mb4"),
    }
    