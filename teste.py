import os
from urllib.parse import urlparse
import mysql.connector

# Link público do seu banco no Railway
link_banco = os.getenv(
    "MYSQL_PUBLIC_URL",
    "mysql://root:oLIRtzxiMczdiQgsdeudzgxaZHfJwMjC@ballast.proxy.rlwy.net:30074/railway",
)
url = urlparse(link_banco)

try:
    conexao = mysql.connector.connect(
        host=url.hostname,
        user=url.username,
        password=url.password,
        database=url.path[1:],
        port=url.port,
    )

    cursor = conexao.cursor()
    cursor.execute("SHOW TABLES;")
    tabelas = cursor.fetchall()

    print("✅ Conectado ao Railway com sucesso!")
    print("📋 Tabelas encontradas no banco:", [t[0] for t in tabelas])

    cursor.close()
    conexao.close()

except Exception as erro:
    print("❌ Erro ao conectar:", erro)