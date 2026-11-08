from datetime import date

from flask import Blueprint, current_app, jsonify, request

from database import execute_query, execute_transaction, fetch_all, fetch_one
from routes.jwt_auth import jwt_obrigatorio

clientes_bp = Blueprint("clientes", __name__, url_prefix="/clientes")

_CLIENTE_COM_RELACIONAMENTOS = """
    SELECT
        c.id_cliente, c.nome, c.cpf, c.rg, c.data_nascimento, c.telefone,
        c.email, c.nome_contato_emergencia, c.telefone_contato_emergencia,
        c.status, c.data_cadastro,
        e.id_endereco, e.cep, e.logradouro, e.numero, e.complemento,
        e.cidade, e.uf,
        h.id_habilitacao, h.numero_registro, h.categoria, h.data_validade
    FROM cliente c
    LEFT JOIN endereco e ON e.id_cliente = c.id_cliente
    LEFT JOIN registro_habilitacao h ON h.id_cliente = c.id_cliente
"""


def _serializar_cliente(registro):
    cliente = {
        chave: registro[chave]
        for chave in (
            "id_cliente",
            "nome",
            "cpf",
            "rg",
            "data_nascimento",
            "telefone",
            "email",
            "nome_contato_emergencia",
            "telefone_contato_emergencia",
            "status",
            "data_cadastro",
        )
    }
    if registro["id_endereco"] is not None:
        cliente["endereco"] = {
            "id_endereco": registro["id_endereco"],
            "cep": registro["cep"],
            "logradouro": registro["logradouro"],
            "numero": registro["numero"],
            "complemento": registro["complemento"],
            "cidade": registro["cidade"],
            "uf": registro["uf"],
        }
    if registro["id_habilitacao"] is not None:
        cliente["registro_habilitacao"] = {
            "id_habilitacao": registro["id_habilitacao"],
            "numero_registro": registro["numero_registro"],
            "categoria": registro["categoria"],
            "data_validade": registro["data_validade"],
        }
    return cliente


@clientes_bp.route("", methods=["GET"])
@jwt_obrigatorio
def listar_clientes():
    try:
        registros = fetch_all(
            f"{_CLIENTE_COM_RELACIONAMENTOS} ORDER BY c.id_cliente DESC"
        )
        return jsonify([_serializar_cliente(registro) for registro in registros]), 200
    except Exception:
        current_app.logger.exception("Falha ao listar clientes")
        return jsonify({"error": "Não foi possível listar os clientes"}), 500


@clientes_bp.route("/<int:id>", methods=["GET"])
@jwt_obrigatorio
def buscar_cliente(id):
    try:
        registro = fetch_one(
            f"{_CLIENTE_COM_RELACIONAMENTOS} WHERE c.id_cliente = %s", (id,)
        )
        if not registro:
            return jsonify({"error": "Cliente não encontrado"}), 404
        return jsonify([_serializar_cliente(registro)]), 200
    except Exception:
        current_app.logger.exception("Falha ao buscar cliente")
        return jsonify({"error": "Não foi possível buscar o cliente"}), 500


@clientes_bp.route("/<int:id>", methods=["PUT"])
@jwt_obrigatorio
def atualizar_cliente(id):
    dados = request.get_json(silent=True) or {}
    if not isinstance(dados, dict) or not dados:
        return jsonify({"error": "Nenhum dado para atualizar"}), 400

    campos_cliente = []
    valores_cliente = []

    for campo in (
        "nome",
        "cpf",
        "rg",
        "data_nascimento",
        "telefone",
        "email",
        "nome_contato_emergencia",
        "telefone_contato_emergencia",
        "senha_hash",
        "status",
    ):
        if campo in dados:
            valor = dados[campo]
            if campo == "cpf":
                valor = "".join(caractere for caractere in str(valor) if caractere.isdigit())
                if len(valor) != 11:
                    return jsonify({"error": "O CPF deve conter 11 dígitos"}), 400
            elif campo in (
                "nome_contato_emergencia",
                "telefone_contato_emergencia",
            ):
                if valor is not None and not isinstance(valor, str):
                    return jsonify({"error": f"O campo {campo} deve ser texto"}), 400
                valor = valor.strip() or None if isinstance(valor, str) else None
            campos_cliente.append(f"{campo} = %s")
            valores_cliente.append(valor)

    endereco = dados.get("endereco")
    if endereco is not None and not isinstance(endereco, dict):
        return jsonify({"error": "O endereço deve ser um objeto JSON"}), 400
    habilitacao = dados.get("registro_habilitacao")
    if habilitacao is not None and not isinstance(habilitacao, dict):
        return jsonify({"error": "A habilitação deve ser um objeto JSON"}), 400

    queries = []
    if campos_cliente:
        valores_cliente.append(id)
        queries.append(
            (
                f"UPDATE cliente SET {', '.join(campos_cliente)} WHERE id_cliente = %s",
                tuple(valores_cliente),
            )
        )

    try:
        if not fetch_one("SELECT id_cliente FROM cliente WHERE id_cliente = %s", (id,)):
            return jsonify({"error": "Cliente não encontrado"}), 404

        campos_endereco = {
            "cep": "cep",
            "logradouro": "logradouro",
            "numero": "numero",
            "complemento": "complemento",
            "cidade": "cidade",
            "uf": "uf",
        }
        if endereco:
            faltando = [campo for campo in ("cep", "logradouro", "numero", "cidade", "uf") if not endereco.get(campo)]
            invalidos = set(endereco) - set(campos_endereco)
            if (
                faltando
                or invalidos
                or any(
                    not isinstance(endereco.get(campo), str)
                    for campo in ("cep", "logradouro", "numero", "cidade", "uf")
                )
                or (
                    endereco.get("complemento") is not None
                    and not isinstance(endereco["complemento"], str)
                )
            ):
                return jsonify({
                    "error": "Informe todos os campos obrigatórios do endereço",
                    "campos": faltando,
                }), 400
            queries.append(
                (
                    """
                    INSERT INTO endereco (
                        id_cliente, cep, logradouro, numero, complemento, cidade, uf
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        cep = VALUES(cep), logradouro = VALUES(logradouro),
                        numero = VALUES(numero), complemento = VALUES(complemento),
                        cidade = VALUES(cidade), uf = VALUES(uf)
                    """,
                    (
                        id,
                        endereco["cep"],
                        endereco["logradouro"],
                        str(endereco["numero"]),
                        endereco.get("complemento") or None,
                        endereco["cidade"],
                        endereco["uf"],
                    ),
                )
            )

        campos_habilitacao = {
            "numero_registro": "numero_registro",
            "categoria": "categoria",
            "data_validade": "data_validade",
        }
        if habilitacao:
            obrigatorios = ("numero_registro", "categoria", "data_validade")
            faltando = [campo for campo in obrigatorios if not habilitacao.get(campo)]
            invalidos = set(habilitacao) - set(campos_habilitacao)
            if (
                faltando
                or invalidos
                or any(not isinstance(habilitacao.get(campo), str) for campo in obrigatorios)
            ):
                return jsonify({
                    "error": "Informe todos os campos obrigatórios da habilitação",
                    "campos": faltando,
                }), 400
            categoria = habilitacao["categoria"].upper()
            if categoria not in {"A", "B", "AB", "AC", "AD", "AE"}:
                return jsonify({"error": "Categoria de habilitação inválida"}), 400
            try:
                data_validade = date.fromisoformat(habilitacao["data_validade"])
            except (TypeError, ValueError):
                return jsonify({"error": "Informe a validade no formato AAAA-MM-DD"}), 400
            if data_validade.isoformat() != habilitacao["data_validade"]:
                return jsonify({"error": "Informe a validade no formato AAAA-MM-DD"}), 400
            queries.append(
                (
                    """
                    INSERT INTO registro_habilitacao (
                        id_cliente, numero_registro, categoria, data_validade
                    ) VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        numero_registro = VALUES(numero_registro),
                        categoria = VALUES(categoria),
                        data_validade = VALUES(data_validade)
                    """,
                    (
                        id,
                        habilitacao["numero_registro"],
                        categoria,
                        data_validade,
                    ),
                )
            )

        if not queries:
            return jsonify({"error": "Nenhum campo válido para atualizar"}), 400
        execute_transaction(queries)
        return jsonify({"message": "Cliente atualizado com sucesso"}), 200
    except Exception:
        current_app.logger.exception("Falha ao atualizar cliente")
        return jsonify({"error": "Não foi possível atualizar o cliente"}), 500


@clientes_bp.route("/<int:id>", methods=["DELETE"])
@jwt_obrigatorio
def excluir_cliente(id):
    try:
        execute_query("DELETE FROM cliente WHERE id_cliente = %s", (id,))
        return jsonify({"message": "Cliente removido com sucesso"}), 200
    except Exception:
        current_app.logger.exception("Falha ao excluir cliente")
        return jsonify({"error": "Não foi possível excluir o cliente"}), 500
