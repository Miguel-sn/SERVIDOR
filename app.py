from urllib.parse import urlsplit

from flask import Flask, jsonify, request

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
def permitir_cors_local(response):
    origem = request.headers.get("Origin")
    if origem:
        url_origem = urlsplit(origem)
        if (
            url_origem.scheme in {"http", "https"}
            and url_origem.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            response.headers["Access-Control-Allow-Origin"] = origem
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            )
            response.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, Authorization"
            )
            response.headers.add("Vary", "Origin")
    return response


@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "message": "API funcionando"})


if __name__ == "__main__":
    app.run(debug=True)