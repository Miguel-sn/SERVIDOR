from flask import Blueprint, jsonify, request

from database import execute_query, fetch_all, fetch_one

clientes_bp = Blueprint("clientes", __name__, url_prefix="/clientes")


@clientes_bp.route("", methods=["GET"])
def listar_clientes():
    try:
        clientes = fetch_all("SELECT * FROM cliente ORDER BY id_cliente DESC")
        return jsonify(clientes), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@clientes_bp.route("/<int:id>", methods=["GET"])
def buscar_cliente(id):
    try:
        cliente = fetch_one("SELECT * FROM cliente WHERE id_cliente = %s", (id,))
        if not cliente:
            return jsonify({"error": "Cliente não encontrado"}), 404
        return jsonify(cliente), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@clientes_bp.route("", methods=["POST"])
def criar_cliente():
    dados = request.get_json(silent=True) or {}

    campos = [
        "nome",
        "cpf",
        "rg",
        "data_nascimento",
        "endereco",
        "telefone",
        "email",
        "senha_hash",
    ]
    faltando = [campo for campo in campos if not dados.get(campo)]

    if faltando:
        return jsonify({"error": f"Campos obrigatórios faltando: {faltando}"}), 400

    try:
        cliente_id = execute_query(
            """
            INSERT INTO cliente (
                nome, cpf, rg, data_nascimento, endereco, telefone, email, senha_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                dados["nome"],
                dados["cpf"],
                dados["rg"],
                dados["data_nascimento"],
                dados["endereco"],
                dados["telefone"],
                dados["email"],
                dados["senha_hash"],
            ),
        )
        return jsonify({"id_cliente": cliente_id, "message": "Cliente cadastrado"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@clientes_bp.route("/<int:id>", methods=["PUT"])
def atualizar_cliente(id):
    dados = request.get_json(silent=True) or {}
    if not dados:
        return jsonify({"error": "Nenhum dado para atualizar"}), 400

    campos = []
    valores = []

    for campo in ["nome", "cpf", "rg", "data_nascimento", "endereco", "telefone", "email", "senha_hash", "status"]:
        if campo in dados:
            campos.append(f"{campo} = %s")
            valores.append(dados[campo])

    if not campos:
        return jsonify({"error": "Nenhum campo válido para atualizar"}), 400

    valores.append(id)

    try:
        execute_query(
            f"UPDATE cliente SET {', '.join(campos)} WHERE id_cliente = %s",
            tuple(valores),
        )
        return jsonify({"message": "Cliente atualizado com sucesso"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@clientes_bp.route("/<int:id>", methods=["DELETE"])
def excluir_cliente(id):
    try:
        execute_query("DELETE FROM cliente WHERE id_cliente = %s", (id,))
        return jsonify({"message": "Cliente removido com sucesso"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
