import secrets
from datetime import datetime

from flask import Blueprint, current_app, g, jsonify, request

from database import execute_query, fetch_all, fetch_one
from routes.jwt_auth import jwt_obrigatorio, jwt_permitido

locacoes_bp = Blueprint("locacoes", __name__, url_prefix="/locacoes")

_COLUNAS = """
    id_locacao, codigo_contrato, id_cliente, id_motocicleta,
    id_funcionario_abertura, data_hora_inicio,
    data_hora_devolucao_prevista, valor_diaria_contratada,
    quantidade_diarias, valor_base_locacao, valor_franquia_contratada,
    status_locacao
"""


def _buscar(id_locacao):
    return fetch_one(f"SELECT {_COLUNAS} FROM locacao WHERE id_locacao = %s", (id_locacao,))


@locacoes_bp.route("", methods=["GET"])
@jwt_obrigatorio
def listar_locacoes():
    identidade = g.identidade_jwt
    try:
        if identidade["tipo_usuario"] == "cliente":
            registros = fetch_all(
                f"SELECT {_COLUNAS} FROM locacao WHERE id_cliente = %s "
                "ORDER BY id_locacao DESC",
                (identidade["id"],),
            )
        else:
            registros = fetch_all(f"SELECT {_COLUNAS} FROM locacao ORDER BY id_locacao DESC")
        return jsonify({"locacoes": registros}), 200
    except Exception:
        current_app.logger.exception("Falha ao listar locações")
        return jsonify({"error": "Não foi possível listar os contratos"}), 500


@locacoes_bp.route("", methods=["POST"])
@jwt_permitido("cliente", "funcionario")
def criar_locacao():
    dados = request.get_json(silent=True) or {}
    obrigatorios = (
        "id_cliente",
        "id_motocicleta",
        "data_hora_inicio",
        "data_hora_devolucao_prevista",
        "valor_diaria_contratada",
        "quantidade_diarias",
    )
    faltando = [campo for campo in obrigatorios if dados.get(campo) in (None, "")]
    if faltando:
        return jsonify({"error": "Campos obrigatórios faltando", "campos": faltando}), 400

    identidade = g.identidade_jwt
    cliente_id = identidade["id"] if identidade["tipo_usuario"] == "cliente" else dados["id_cliente"]
    try:
        inicio = datetime.fromisoformat(str(dados["data_hora_inicio"]))
        devolucao = datetime.fromisoformat(str(dados["data_hora_devolucao_prevista"]))
    except ValueError:
        return jsonify({"error": "Datas devem estar no formato ISO 8601"}), 400
    if devolucao <= inicio:
        return jsonify({"error": "A devolução deve ocorrer após o início"}), 400
    try:
        cliente = fetch_one(
            "SELECT id_cliente FROM cliente WHERE id_cliente = %s AND status_cliente = 'ATIVO'",
            (cliente_id,),
        )
        moto = fetch_one(
            "SELECT valor_diaria_padrao, valor_franquia_padrao FROM motocicleta "
            "WHERE id_motocicleta = %s AND status_motocicleta = 'DISPONIVEL'",
            (dados["id_motocicleta"],),
        )
        if not cliente or not moto:
            return jsonify({"error": "Cliente ou motocicleta indisponível"}), 409
        quantidade = int(dados["quantidade_diarias"])
        if quantidade <= 0:
            return jsonify({"error": "A quantidade de diárias deve ser positiva"}), 400
        valor_diaria = float(dados["valor_diaria_contratada"])
        valor_base = valor_diaria * quantidade
        codigo = f"LOC-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
        funcionario_id = identidade["id"] if identidade["tipo_usuario"] == "funcionario" else None
        id_locacao = execute_query(
            """
            INSERT INTO locacao (
                codigo_contrato, id_cliente, id_motocicleta,
                id_funcionario_abertura, data_hora_inicio,
                data_hora_devolucao_prevista, valor_diaria_contratada,
                quantidade_diarias, valor_base_locacao,
                valor_franquia_contratada, status_locacao
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'RESERVA_PENDENTE')
            """,
            (
                codigo, cliente_id, dados["id_motocicleta"], funcionario_id,
                inicio, devolucao, valor_diaria, quantidade, valor_base,
                float(dados.get("valor_franquia_contratada", moto["valor_franquia_padrao"])),
            ),
        )
        registro = _buscar(id_locacao)
        return jsonify({"locacao": registro}), 201
    except (TypeError, ValueError):
        return jsonify({"error": "Valores numéricos inválidos"}), 400
    except Exception:
        current_app.logger.exception("Falha ao criar contrato")
        return jsonify({"error": "Não foi possível criar o contrato"}), 500


@locacoes_bp.route("/<int:id>/status", methods=["PUT"])
@jwt_permitido("funcionario")
def atualizar_status(id):
    dados = request.get_json(silent=True) or {}
    status = dados.get("status")
    permitidos = {"RESERVA_PENDENTE", "CONFIRMADA", "EM_ANDAMENTO", "FINALIZADA", "CANCELADA"}
    if status not in permitidos:
        return jsonify({"error": "Status de contrato inválido"}), 400
    try:
        if not _buscar(id):
            return jsonify({"error": "Contrato não encontrado"}), 404
        execute_query(
            "UPDATE locacao SET status_locacao = %s WHERE id_locacao = %s",
            (status, id),
        )
        return jsonify({"locacao": _buscar(id)}), 200
    except Exception:
        current_app.logger.exception("Falha ao atualizar contrato")
        return jsonify({"error": "Não foi possível atualizar o contrato"}), 500
