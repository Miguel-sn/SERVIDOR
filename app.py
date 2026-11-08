import os

from flask import Flask, jsonify, request
from flask_cors import CORS

from routes.aut import aut_bp
from routes.aut_fotos import aut_fotos_bp
from routes.clientes import clientes_bp
from routes.devolucao import devolucao_bp
from routes.funcionarios import funcionarios_bp
from routes.locacoes import locacoes_bp
from routes.manutencao import manutencao_bp
from routes.modelo_M import modelo_motocicleta_bp
from routes.motocicleta import motocicleta_bp
from routes.multas import multas_bp
from routes.pagamentos import pagamentos_bp
from routes.reservas import reservas_bp
from routes.sinistros import sinistros_bp

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
origins = [
    origem.strip()
    for origem in os.getenv(
        "CORS_ORIGINS",
        "https://locajaveiculos.com.br,https://teste-a9bbe.web.app",
    ).split(",")
    if origem.strip()
]
origins.extend([r"https?://(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?"])
CORS(
    app,
    resources={
        r"/*": {
            "origins": origins,
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Authorization", "Content-Type"],
        }
    },
)
app.register_blueprint(aut_bp)
app.register_blueprint(aut_fotos_bp)
app.register_blueprint(clientes_bp)
app.register_blueprint(funcionarios_bp)
app.register_blueprint(modelo_motocicleta_bp)
app.register_blueprint(motocicleta_bp)
app.register_blueprint(reservas_bp)
app.register_blueprint(locacoes_bp)
app.register_blueprint(pagamentos_bp)
app.register_blueprint(devolucao_bp)
app.register_blueprint(sinistros_bp)
app.register_blueprint(manutencao_bp)
app.register_blueprint(multas_bp)


@app.before_request
def registrar_requisicao_recebida():
    app.logger.info("Requisição recebida: %s %s", request.method, request.path)


@app.after_request
def normalizar_cabecalhos_cors(resposta):
    cabecalhos = resposta.headers.get("Access-Control-Allow-Headers")
    if cabecalhos:
        nomes = {cabecalho.strip().lower(): cabecalho.strip() for cabecalho in cabecalhos.split(",")}
        resposta.headers["Access-Control-Allow-Headers"] = ", ".join(
            nomes.get(nome, nome) for nome in ("authorization", "content-type")
            if nome in nomes
        )
    return resposta


@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "message": "API funcionando"})


@app.route("/api/exemplo", methods=["GET"])
def exemplo():
    return jsonify({"status": "sucesso", "mensagem": "Conectado ao backend!"})


if __name__ == "__main__":
    app.run(debug=True)