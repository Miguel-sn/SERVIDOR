from flask import Blueprint, jsonify, request

from database import execute_query, fetch_all, fetch_one

pagamentos_bp = Blueprint("pagamentos", __name__, url_prefix="/pagamentos")


@pagamentos_bp.route("", methods=["GET"])
def listar_pagamentos():
    try:
        pagamentos = fetch_all("SELECT * FROM pagamento ORDER BY id_pagamento DESC")
        return jsonify(pagamentos), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@pagamentos_bp.route("", methods=["POST"])
def criar_pagamento():
    dados = request.get_json(silent=True) or {}
    campos = ["id_locacao", "valor", "forma_pagamento"]
    faltando = [campo for campo in campos if dados.get(campo) in (None, "")]
    if faltando:
        return jsonify({"error": f"Campos obrigatórios faltando: {faltando}"}), 400

    try:
        pagamento_id = execute_query(
            """
            INSERT INTO pagamento (
                id_locacao, valor, forma_pagamento, status, codigo_transacao, descricao
            ) VALUES (%s, %s, %s, 'PENDENTE', %s, %s)
            """,
            (
                dados["id_locacao"],
                dados["valor"],
                dados["forma_pagamento"],
                dados.get("codigo_transacao"),
                dados.get("descricao"),
            ),
        )
        return jsonify({"id_pagamento": pagamento_id, "message": "Pagamento registrado"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
