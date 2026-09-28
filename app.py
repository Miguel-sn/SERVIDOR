from flask import Flask, jsonify

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


@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "message": "API funcionando"})


if __name__ == "__main__":
    app.run(debug=True)