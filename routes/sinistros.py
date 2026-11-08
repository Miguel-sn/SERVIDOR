from flask import Blueprint, jsonify, request

from database import execute_query, fetch_all, fetch_one

sinistros_bp = Blueprint("sinistros", __name__, url_prefix="/sinistros")


@sinistros_bp.route("", methods=["GET"])
def listar_sinistros():
    try:
        sinistros = fetch_all("SELECT * FROM sinistro ORDER BY id_sinistro DESC")
        return jsonify(sinistros), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sinistros_bp.route("", methods=["POST"])
def criar_sinistro():
    dados = request.get_json(silent=True) or {}
    campos = ["id_locacao", "id_motocicleta", "tipo_sinistro", "descricao"]
    faltando = [campo for campo in campos if dados.get(campo) in (None, "")]
    if faltando:
        return jsonify({"error": f"Campos obrigatórios faltando: {faltando}"}), 400

    try:
        sinistro_id = execute_query(
            """
            INSERT INTO sinistro (
                id_locacao, id_motocicleta, tipo_sinistro, descricao,
                local_ocorrencia, valor_prejuizo, valor_franquia, status, observacoes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'ABERTO', %s)
            """,
            (
                dados["id_locacao"],
                dados["id_motocicleta"],
                dados["tipo_sinistro"],
                dados["descricao"],
                dados.get("local_ocorrencia"),
                dados.get("valor_prejuizo", 0),
                dados.get("valor_franquia", 0),
                dados.get("observacoes"),
            ),
        )
        return jsonify({"id_sinistro": sinistro_id, "message": "Sinistro registrado"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
