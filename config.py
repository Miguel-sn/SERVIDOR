import os

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "LauNM#17%Domoney"),
    "database": os.getenv("DB_NAME", "loca_ja"),
    "charset": "utf8mb4",
    "cursorclass": None,
}

# A classe do cursor é preenchida no database.py para facilitar a importação.
