from flask import Blueprint, jsonify, request

from database import execute_query, fetch_all, fetch_one

modelo_motocicleta_bp = Blueprint("modelo_motocicleta", __name__, url_prefix="/modelos")


@modelo_motocicleta_bp.route("", methods=["GET"])
def listar_modelos():
    try:
        modelos = fetch_all("SELECT * FROM modelo_motocicleta ORDER BY id_modelo DESC")
        return jsonify(modelos), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@modelo_motocicleta_bp.route("/<int:id>", methods=["GET"])
def buscar_modelo(id):
    try:
        modelo = fetch_one("SELECT * FROM modelo_motocicleta WHERE id_modelo = %s", (id,))
        if not modelo:
            return jsonify({"error": "Modelo não encontrado"}), 404
        return jsonify(modelo), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@modelo_motocicleta_bp.route("", methods=["POST"])
def criar_modelo():
    dados = request.get_json(silent=True) or {}
    campos = ["marca", "modelo", "categoria", "cilindrada", "ano_modelo", "valor_diaria", "valor_semanal", "valor_mensal"]
    faltando = [campo for campo in campos if dados.get(campo) in (None, "")]
    if faltando:
        return jsonify({"error": f"Campos obrigatórios faltando: {faltando}"}), 400

    try:
        modelo_id = execute_query(
            """
            INSERT INTO modelo_motocicleta (
                marca, modelo, categoria, cilindrada, ano_modelo,
                valor_diaria, valor_semanal, valor_mensal, descricao, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'ATIVO')
            """,
            (
                dados["marca"],
                dados["modelo"],
                dados["categoria"],
                dados["cilindrada"],
                dados["ano_modelo"],
                dados["valor_diaria"],
                dados["valor_semanal"],
                dados["valor_mensal"],
                dados.get("descricao"),
            ),
        )
        return jsonify({"id_modelo": modelo_id, "message": "Modelo cadastrado"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
