from flask import Blueprint, jsonify, request

from database import execute_query, fetch_all, fetch_one

locacoes_bp = Blueprint("locacoes", __name__, url_prefix="/locacoes")


@locacoes_bp.route("", methods=["GET"])
def listar_locacoes():
    try:
        locacoes = fetch_all("SELECT * FROM locacao ORDER BY id_locacao DESC")
        return jsonify(locacoes), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@locacoes_bp.route("/<int:id>", methods=["GET"])
def buscar_locacao(id):
    try:
        locacao = fetch_one("SELECT * FROM locacao WHERE id_locacao = %s", (id,))
        if not locacao:
            return jsonify({"error": "Locação não encontrada"}), 404
        return jsonify(locacao), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@locacoes_bp.route("", methods=["POST"])
def criar_locacao():
    dados = request.get_json(silent=True) or {}
    campos = [
        "numero_locacao",
        "id_reserva",
        "id_motocicleta",
        "id_funcionario",
        "data_hora_inicio",
        "data_hora_devolucao_prevista",
        "valor_diaria",
        "quantidade_periodos",
        "valor_locacao",
        "valor_franquia_aplicada",
    ]
    faltando = [campo for campo in campos if dados.get(campo) in (None, "")]
    if faltando:
        return jsonify({"error": f"Campos obrigatórios faltando: {faltando}"}), 400

    try:
        locacao_id = execute_query(
            """
            INSERT INTO locacao (
                numero_locacao, id_reserva, id_motocicleta, id_funcionario,
                data_hora_inicio, data_hora_devolucao_prevista, valor_diaria,
                quantidade_periodos, valor_locacao, valor_franquia_aplicada, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'AGENDADA')
            """,
            (
                dados["numero_locacao"],
                dados["id_reserva"],
                dados["id_motocicleta"],
                dados["id_funcionario"],
                dados["data_hora_inicio"],
                dados["data_hora_devolucao_prevista"],
                dados["valor_diaria"],
                dados["quantidade_periodos"],
                dados["valor_locacao"],
                dados["valor_franquia_aplicada"],
            ),
        )
        return jsonify({"id_locacao": locacao_id, "message": "Locação criada"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@locacoes_bp.route("/<int:id>/finalizar", methods=["PUT"])
def finalizar_locacao(id):
    try:
        execute_query("UPDATE locacao SET status = 'FINALIZADA' WHERE id_locacao = %s", (id,))
        return jsonify({"message": "Locação finalizada"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@locacoes_bp.route("/<int:id>/cancelar", methods=["PUT"])
def cancelar_locacao(id):
    try:
        execute_query("UPDATE locacao SET status = 'CANCELADA' WHERE id_locacao = %s", (id,))
        return jsonify({"message": "Locação cancelada"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
