import secrets
from datetime import datetime

from flask import Blueprint, current_app, g, jsonify, request

from database import (
    TransactionConflictError,
    execute_transaction,
    fetch_all,
    fetch_one,
)
from routes.jwt_auth import jwt_obrigatorio, jwt_permitido

locacoes_bp = Blueprint("locacoes", __name__, url_prefix="/locacoes")

_COLUNAS = """
    l.id_locacao, l.codigo_contrato, l.id_cliente, l.id_motocicleta,
    l.data_hora_inicio, l.data_hora_devolucao_prevista,
    l.valor_base_locacao, l.quantidade_diarias, l.status_locacao
"""


def _buscar(id_locacao):
    return fetch_one(
        f"SELECT {_COLUNAS} FROM locacao l WHERE l.id_locacao = %s",
        (id_locacao,),
    )


@locacoes_bp.route("", methods=["GET"])
@jwt_obrigatorio
def listar_locacoes():
    identidade = g.identidade_jwt
    try:
        if identidade["tipo_usuario"] == "cliente":
            registros = fetch_all(
                f"SELECT {_COLUNAS} FROM locacao l "
                "WHERE l.id_cliente = %s ORDER BY l.id_locacao DESC",
                (identidade["id"],),
            )
        else:
            registros = fetch_all(
                f"SELECT {_COLUNAS} FROM locacao l "
                "ORDER BY l.id_locacao DESC"
            )
        return jsonify({"locacoes": registros}), 200
    except Exception:
        current_app.logger.exception("Falha ao listar locações")
        return jsonify({"error": "Não foi possível listar os contratos"}), 500


@locacoes_bp.route("", methods=["POST"])
@jwt_permitido("funcionario")
def criar_locacao():
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify({"error": "O corpo da solicitação deve ser um objeto JSON"}), 400

    obrigatorios = ("id_reserva", "id_motocicleta")
    faltando = [campo for campo in obrigatorios if dados.get(campo) in (None, "")]
    if faltando:
        return jsonify({"error": "Campos obrigatórios faltando", "campos": faltando}), 400

    try:
        reserva = fetch_one(
            """
            SELECT
                r.id_reserva, r.data_hora_retirada_prevista,
                r.data_hora_devolucao_prevista, r.valor_diaria,
                r.quantidade_periodos, r.valor_total_previsto,
                r.status AS status_reserva, c.status AS status_cliente,
                m.status AS status_modelo, moto.status AS status_motocicleta,
                f.valor_franquia
            FROM reserva r
            JOIN cliente c ON c.id_cliente = r.id_cliente
            JOIN modelo_motocicleta m ON m.id_modelo = r.id_modelo
            JOIN motocicleta moto ON moto.id_modelo = r.id_modelo
            LEFT JOIN franquia f ON f.id_motocicleta = moto.id_motocicleta
            WHERE r.id_reserva = %s AND moto.id_motocicleta = %s
            """,
            (dados["id_reserva"], dados["id_motocicleta"]),
        )
        if (
            not reserva
            or reserva["status_reserva"] != "APROVADA"
            or reserva["status_cliente"] != "ATIVO"
            or reserva["status_modelo"] != "ATIVO"
            or reserva["status_motocicleta"] != "DISPONIVEL"
            or reserva["valor_franquia"] is None
        ):
            return jsonify({"error": "Reserva, cliente ou motocicleta indisponível"}), 409

        numero = (
            f"LOC-{datetime.now().strftime('%Y%m%d')}-"
            f"{secrets.token_hex(3).upper()}"
        )
        resultados = execute_transaction(
            [
                (
                    """
                    UPDATE motocicleta SET status = 'RESERVADA'
                    WHERE id_motocicleta = %s AND status = 'DISPONIVEL'
                    """,
                    (dados["id_motocicleta"],),
                ),
                (
                    """
                    INSERT INTO locacao (
                        numero_locacao, id_reserva, id_motocicleta, id_funcionario,
                        data_hora_inicio, data_hora_devolucao_prevista,
                        valor_diaria, quantidade_periodos, valor_locacao,
                        valor_franquia_aplicada, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'AGENDADA')
                    """,
                    (
                        numero,
                        reserva["id_reserva"],
                        dados["id_motocicleta"],
                        g.identidade_jwt["id"],
                        reserva["data_hora_retirada_prevista"],
                        reserva["data_hora_devolucao_prevista"],
                        reserva["valor_diaria"],
                        reserva["quantidade_periodos"],
                        reserva["valor_total_previsto"],
                        reserva["valor_franquia"],
                    ),
                ),
            ],
            expected_rowcounts={0: 1},
        )
        id_locacao = resultados[1]
        return jsonify({"locacao": _buscar(id_locacao)}), 201
    except TransactionConflictError:
        return jsonify({"error": "A motocicleta não está mais disponível"}), 409
    except Exception:
        current_app.logger.exception("Falha ao criar contrato")
        return jsonify({"error": "Não foi possível criar o contrato"}), 500


@locacoes_bp.route("/<int:id>/status", methods=["PUT"])
@jwt_permitido("funcionario")
def atualizar_status(id):
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify({"error": "O corpo da solicitação deve ser um objeto JSON"}), 400

    status = dados.get("status")
    transicoes = {
        "AGENDADA": {"EM_ANDAMENTO", "CANCELADA"},
        "EM_ANDAMENTO": {"FINALIZADA", "COM_PENDENCIA"},
    }
    permitidos = {
        proximo_status
        for proximos in transicoes.values()
        for proximo_status in proximos
    }
    estados_motocicleta = {
        ("AGENDADA", "EM_ANDAMENTO"): ("RESERVADA", "ALUGADA"),
        ("AGENDADA", "CANCELADA"): ("RESERVADA", "DISPONIVEL"),
        ("EM_ANDAMENTO", "FINALIZADA"): ("ALUGADA", "DISPONIVEL"),
        ("EM_ANDAMENTO", "COM_PENDENCIA"): ("ALUGADA", "DISPONIVEL"),
    }
    if not isinstance(status, str):
        return jsonify({"error": "Status de contrato inválido"}), 400
    if status not in permitidos:
        return jsonify({"error": "Status de contrato inválido"}), 400
    try:
        locacao = _buscar(id)
        if not locacao:
            return jsonify({"error": "Contrato não encontrado"}), 404
        status_atual = locacao["status"]
        if status not in transicoes.get(status_atual, set()):
            return jsonify({"error": "Transição de status não permitida"}), 409
        status_moto_atual, status_moto_novo = estados_motocicleta[
            (status_atual, status)
        ]
        execute_transaction(
            [
                (
                    """
                    UPDATE motocicleta SET status = %s
                    WHERE id_motocicleta = %s AND status = %s
                    """,
                    (status_moto_novo, locacao["id_motocicleta"], status_moto_atual),
                ),
                (
                    """
                    UPDATE locacao SET status = %s
                    WHERE id_locacao = %s AND status = %s
                    """,
                    (status, id, status_atual),
                ),
            ],
            expected_rowcounts={0: 1, 1: 1},
        )
        return jsonify({"locacao": _buscar(id)}), 200
    except TransactionConflictError:
        return jsonify({"error": "O contrato ou a motocicleta foi alterado por outra solicitação"}), 409
    except Exception:
        current_app.logger.exception("Falha ao atualizar contrato")
        return jsonify({"error": "Não foi possível atualizar o contrato"}), 500
