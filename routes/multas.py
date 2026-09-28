from flask import Blueprint, jsonify, request

from database import execute_query, fetch_all

multas_bp = Blueprint("multas", __name__, url_prefix="/multas")


@multas_bp.route("", methods=["GET"])
def listar_multas():
    try:
        multas = fetch_all("SELECT * FROM multa ORDER BY id_multa DESC")
        return jsonify(multas), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@multas_bp.route("", methods=["POST"])
def criar_multa():
    dados = request.get_json(silent=True) or {}
    campos = ["id_locacao", "id_motocicleta", "descricao", "data_infracao", "valor"]
    faltando = [campo for campo in campos if dados.get(campo) in (None, "")]
    if faltando:
        return jsonify({"error": f"Campos obrigatórios faltando: {faltando}"}), 400

    try:
        multa_id = execute_query(
            """
            INSERT INTO multa (
                id_locacao, id_motocicleta, codigo_infracao, descricao,
                data_infracao, local_infracao, valor, pontos, data_vencimento, status, observacoes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDENTE', %s)
            """,
            (
                dados["id_locacao"],
                dados["id_motocicleta"],
                dados.get("codigo_infracao"),
                dados["descricao"],
                dados["data_infracao"],
                dados.get("local_infracao"),
                dados["valor"],
                dados.get("pontos", 0),
                dados.get("data_vencimento"),
                dados.get("observacoes"),
            ),
        )
        return jsonify({"id_multa": multa_id, "message": "Multa registrada"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
