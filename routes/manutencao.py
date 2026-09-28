from flask import Blueprint, jsonify, request

from database import execute_query, fetch_all

manutencao_bp = Blueprint("manutencao", __name__, url_prefix="/manutencoes")


@manutencao_bp.route("", methods=["GET"])
def listar_manutencoes():
    try:
        manutencoes = fetch_all("SELECT * FROM manutencao ORDER BY id_manutencao DESC")
        return jsonify(manutencoes), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@manutencao_bp.route("", methods=["POST"])
def criar_manutencao():
    dados = request.get_json(silent=True) or {}
    campos = ["id_motocicleta", "tipo_manutencao", "descricao", "data_inicio", "quilometragem"]
    faltando = [campo for campo in campos if dados.get(campo) in (None, "")]
    if faltando:
        return jsonify({"error": f"Campos obrigatórios faltando: {faltando}"}), 400

    try:
        manutencao_id = execute_query(
            """
            INSERT INTO manutencao (
                id_motocicleta, id_funcionario, tipo_manutencao, descricao,
                data_inicio, data_conclusao, quilometragem, valor, oficina, status, observacoes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'AGENDADA', %s)
            """,
            (
                dados["id_motocicleta"],
                dados.get("id_funcionario"),
                dados["tipo_manutencao"],
                dados["descricao"],
                dados["data_inicio"],
                dados.get("data_conclusao"),
                dados["quilometragem"],
                dados.get("valor", 0),
                dados.get("oficina"),
                dados.get("observacoes"),
            ),
        )
        return jsonify({"id_manutencao": manutencao_id, "message": "Manutenção registrada"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
