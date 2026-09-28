from flask import Blueprint, jsonify, request

from database import execute_query, fetch_all, fetch_one

devolucao_bp = Blueprint("devolucao", __name__, url_prefix="/devolucoes")


@devolucao_bp.route("", methods=["GET"])
def listar_devolucoes():
    try:
        devolucoes = fetch_all("SELECT * FROM devolucao ORDER BY id_devolucao DESC")
        return jsonify(devolucoes), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@devolucao_bp.route("", methods=["POST"])
def criar_devolucao():
    dados = request.get_json(silent=True) or {}
    campos = ["id_locacao", "id_funcionario", "quilometragem_final"]
    faltando = [campo for campo in campos if dados.get(campo) in (None, "")]
    if faltando:
        return jsonify({"error": f"Campos obrigatórios faltando: {faltando}"}), 400

    try:
        devolucao_id = execute_query(
            """
            INSERT INTO devolucao (
                id_locacao, id_funcionario, quilometragem_final,
                avarias_identificadas, observacoes, valor_avarias,
                valor_total_adicional, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'REALIZADA')
            """,
            (
                dados["id_locacao"],
                dados["id_funcionario"],
                dados["quilometragem_final"],
                bool(dados.get("avarias_identificadas", False)),
                dados.get("observacoes"),
                dados.get("valor_avarias", 0),
                dados.get("valor_total_adicional", 0),
            ),
        )
        return jsonify({"id_devolucao": devolucao_id, "message": "Devolução registrada"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
