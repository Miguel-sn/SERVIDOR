from flask import Blueprint, jsonify, request

from database import execute_query, fetch_all, fetch_one

funcionarios_bp = Blueprint("funcionarios", __name__, url_prefix="/funcionarios")


@funcionarios_bp.route("", methods=["GET"])
def listar_funcionarios():
    try:
        funcionarios = fetch_all("SELECT * FROM funcionario ORDER BY id_funcionario DESC")
        return jsonify(funcionarios), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@funcionarios_bp.route("/<int:id>", methods=["GET"])
def buscar_funcionario(id):
    try:
        funcionario = fetch_one("SELECT * FROM funcionario WHERE id_funcionario = %s", (id,))
        if not funcionario:
            return jsonify({"error": "Funcionário não encontrado"}), 404
        return jsonify(funcionario), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@funcionarios_bp.route("", methods=["POST"])
def criar_funcionario():
    dados = request.get_json(silent=True) or {}
    campos = ["nome", "cpf", "email", "senha_hash"]
    faltando = [campo for campo in campos if not dados.get(campo)]
    if faltando:
        return jsonify({"error": f"Campos obrigatórios faltando: {faltando}"}), 400

    try:
        funcionario_id = execute_query(
            """
            INSERT INTO funcionario (
                nome, cpf, email, senha_hash, telefone, cargo, perfil, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'ATIVO')
            """,
            (
                dados["nome"],
                dados["cpf"],
                dados["email"],
                dados["senha_hash"],
                dados.get("telefone"),
                dados.get("cargo"),
                dados.get("perfil", "FUNCIONARIO"),
            ),
        )
        return jsonify({"id_funcionario": funcionario_id, "message": "Funcionário cadastrado"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
