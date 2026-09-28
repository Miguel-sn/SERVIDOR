from flask import Blueprint, jsonify, request

from database import execute_query, fetch_all, fetch_one

reservas_bp = Blueprint("reservas", __name__, url_prefix="/reservas")


@reservas_bp.route("", methods=["GET"])
def listar_reservas():
    try:
        reservas = fetch_all("SELECT * FROM reserva ORDER BY id_reserva DESC")
        return jsonify(reservas), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reservas_bp.route("/<int:id>", methods=["GET"])
def buscar_reserva(id):
    try:
        reserva = fetch_one("SELECT * FROM reserva WHERE id_reserva = %s", (id,))
        if not reserva:
            return jsonify({"error": "Reserva não encontrada"}), 404
        return jsonify(reserva), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reservas_bp.route("", methods=["POST"])
def criar_reserva():
    dados = request.get_json(silent=True) or {}
    campos = [
        "numero_reserva",
        "id_cliente",
        "id_modelo",
        "data_hora_retirada_prevista",
        "data_hora_devolucao_prevista",
        "valor_diaria",
        "quantidade_periodos",
        "valor_total_previsto",
    ]

    faltando = [campo for campo in campos if dados.get(campo) in (None, "")]
    if faltando:
        return jsonify({"error": f"Campos obrigatórios faltando: {faltando}"}), 400

    try:
        reserva_id = execute_query(
            """
            INSERT INTO reserva (
                numero_reserva, id_cliente, id_modelo, data_hora_retirada_prevista,
                data_hora_devolucao_prevista, valor_diaria, quantidade_periodos,
                valor_total_previsto, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'PENDENTE')
            """,
            (
                dados["numero_reserva"],
                dados["id_cliente"],
                dados["id_modelo"],
                dados["data_hora_retirada_prevista"],
                dados["data_hora_devolucao_prevista"],
                dados["valor_diaria"],
                dados["quantidade_periodos"],
                dados["valor_total_previsto"],
            ),
        )
        return jsonify({"id_reserva": reserva_id, "message": "Reserva criada"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reservas_bp.route("/<int:id>/aprovar", methods=["PUT"])
def aprovar_reserva(id):
    try:
        execute_query("UPDATE reserva SET status = 'APROVADA' WHERE id_reserva = %s", (id,))
        return jsonify({"message": "Reserva aprovada"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reservas_bp.route("/<int:id>/cancelar", methods=["PUT"])
def cancelar_reserva(id):
    try:
        execute_query("UPDATE reserva SET status = 'CANCELADA' WHERE id_reserva = %s", (id,))
        return jsonify({"message": "Reserva cancelada"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
