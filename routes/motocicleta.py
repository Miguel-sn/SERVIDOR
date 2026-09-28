from flask import Blueprint, jsonify, request

from database import execute_query, fetch_all, fetch_one

motocicleta_bp = Blueprint("motocicleta", __name__, url_prefix="/motocicletas")


@motocicleta_bp.route("", methods=["GET"])
def listar_motocicletas():
    try:
        motos = fetch_all("SELECT * FROM motocicleta ORDER BY id_motocicleta DESC")
        return jsonify(motos), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@motocicleta_bp.route("/<int:id>", methods=["GET"])
def buscar_motocicleta(id):
    try:
        moto = fetch_one("SELECT * FROM motocicleta WHERE id_motocicleta = %s", (id,))
        if not moto:
            return jsonify({"error": "Motocicleta não encontrada"}), 404
        return jsonify(moto), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@motocicleta_bp.route("", methods=["POST"])
def criar_motocicleta():
    dados = request.get_json(silent=True) or {}
    campos = ["id_modelo", "placa", "renavam", "chassi", "ano_fabricacao"]
    faltando = [campo for campo in campos if dados.get(campo) in (None, "")]
    if faltando:
        return jsonify({"error": f"Campos obrigatórios faltando: {faltando}"}), 400

    try:
        moto_id = execute_query(
            """
            INSERT INTO motocicleta (
                id_modelo, placa, renavam, chassi, ano_fabricacao,
                quilometragem_atual, status, data_aquisicao
            ) VALUES (%s, %s, %s, %s, %s, %s, 'DISPONIVEL', %s)
            """,
            (
                dados["id_modelo"],
                dados["placa"],
                dados["renavam"],
                dados["chassi"],
                dados["ano_fabricacao"],
                dados.get("quilometragem_atual", 0),
                dados.get("data_aquisicao"),
            ),
        )
        return jsonify({"id_motocicleta": moto_id, "message": "Motocicleta cadastrada"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
