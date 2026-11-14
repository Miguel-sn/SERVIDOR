import json
import os
import time
import uuid

from flask import Flask, g, jsonify, request
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
from routes.pagamentos import pagamentos_bp
from routes.reservas import reservas_bp
from routes.sinistros import sinistros_bp
from firebase_service import db as firebase_db
from database import fetch_one
from config import get_db_config

app = Flask(__name__)
app.extensions["firebase_db"] = firebase_db
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_BYTES", str(30 * 1024 * 1024)))

if os.getenv("APP_ENV", "development").lower() == "production":
    configuracoes_ausentes = [
        nome
        for nome in ("FLASK_SECRET_KEY", "JWT_SECRET_KEY", "CORS_ORIGINS")
        if not os.getenv(nome)
    ]
    if configuracoes_ausentes:
        raise RuntimeError(
            "Configurações obrigatórias de produção ausentes: "
            + ", ".join(configuracoes_ausentes)
        )
    get_db_config()

origins_configurados = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:54321,http://localhost:5000",
)
origins = [
    origin.strip().rstrip("/")
    for origin in origins_configurados.split(",")
    if origin.strip()
]

CORS(
    app,
    resources={
        r"/*": {
            "origins": origins,
            "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            "allow_headers": ["content-type", "authorization"],
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


@app.before_request
def iniciar_rastreamento_requisicao():
    g.request_id = str(uuid.uuid4())
    g.request_started_at = time.perf_counter()


@app.after_request
def registrar_requisicao(resposta):
    inicio = getattr(g, "request_started_at", time.perf_counter())
    request_id = getattr(g, "request_id", "unknown")
    duracao_ms = round((time.perf_counter() - inicio) * 1000, 2)
    app.logger.info(
        "Requisição recebida: %s %s %s",
        request.method,
        request.path,
        json.dumps(
            {
                "request_id": request_id,
                "method": request.method,
                "route": request.path,
                "status_code": resposta.status_code,
                "duration_ms": duracao_ms,
            },
            ensure_ascii=False,
        ),
    )
    resposta.headers["X-Request-ID"] = request_id
    return resposta


@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "message": "API funcionando"})


@app.route("/api/status", methods=["GET"])
def status():
    try:
        resultado = fetch_one("SELECT 1 AS health")
    except Exception:
        app.logger.exception("Health check do banco falhou")
        return jsonify({"status": "degraded", "database": "unavailable"}), 503

    if not resultado or resultado.get("health") != 1:
        return jsonify({"status": "degraded", "database": "unavailable"}), 503
    return jsonify({"status": "ok", "database": "ok"}), 200


@app.route("/api/exemplo", methods=["GET"])
def exemplo():
    return jsonify({"status": "sucesso", "mensagem": "Conectado ao backend!"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)