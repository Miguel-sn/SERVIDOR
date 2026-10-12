import hmac

from flask import Blueprint, current_app, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from database import execute_query, fetch_one

aut_bp = Blueprint("aut", __name__, url_prefix="/auth")


def _verificar_senha(senha, senha_armazenada):
	try:
		if check_password_hash(senha_armazenada, senha):
			return True, False
	except (TypeError, ValueError):
		pass

	senha_legada_valida = isinstance(senha_armazenada, str) and hmac.compare_digest(
		senha_armazenada.encode("utf-8"), senha.encode("utf-8")
	)
	return senha_legada_valida, senha_legada_valida

@aut_bp.route("/cadastro", methods=["POST"])
def cadastrar_cliente():
	dados = request.get_json(silent=True) or {}
	campos_obrigatorios = [
		"nome",
		"cpf",
		"rg",
		"data_nascimento",
		"endereco",
		"telefone",
		"email",
		"senha",
	]
	faltando = [campo for campo in campos_obrigatorios if not dados.get(campo)]
	if faltando:
		return jsonify({"error": "Campos obrigatórios faltando", "campos": faltando}), 400

	email = dados["email"].strip().lower()
	if "@" not in email or len(dados["senha"]) < 8:
		return jsonify({"error": "E-mail ou senha inválidos; use uma senha com ao menos 8 caracteres"}), 400

	try:
		existente = fetch_one(
			"SELECT id_cliente FROM cliente WHERE email = %s UNION "
			"SELECT id_funcionario FROM funcionario WHERE email = %s LIMIT 1",
			(email, email),
		)
		if existente:
			return jsonify({"error": "E-mail já cadastrado"}), 409

		cliente_id = execute_query(
			"""
			INSERT INTO cliente (
				nome, cpf, rg, data_nascimento, endereco, telefone, email, senha_hash
			) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
			""",
			(
				dados["nome"].strip(),
				dados["cpf"].strip(),
				dados["rg"].strip(),
				dados["data_nascimento"],
				dados["endereco"].strip(),
				dados["telefone"].strip(),
				email,
				generate_password_hash(dados["senha"]),
			),
		)
		return jsonify({"id_cliente": cliente_id, "message": "Cliente cadastrado"}), 201
	except Exception:
		current_app.logger.exception("Falha ao cadastrar cliente")
		return jsonify({"error": "Não foi possível cadastrar o cliente"}), 500


@aut_bp.route("/login", methods=["POST"])
def login():
	dados = request.get_json(silent=True) or {}
	email = dados.get("email", "")
	senha = dados.get("senha", "")
	if not isinstance(email, str) or not isinstance(senha, str) or not email or not senha:
		return jsonify({"error": "Informe e-mail e senha"}), 400

	try:
		email = email.strip().lower()
		usuario = fetch_one(
			"SELECT id_cliente AS id, nome, email, senha_hash FROM cliente WHERE email = %s",
			(email,),
		)
		tabela = "cliente"
		tipo = "cliente"

		if not usuario:
			usuario = fetch_one(
				"SELECT id_funcionario AS id, nome, email, senha_hash, status "
				"FROM funcionario WHERE email = %s",
				(email,),
			)
			tabela = "funcionario"
			tipo = "funcionario"

		if not usuario:
			return jsonify({"error": "E-mail ou senha inválidos"}), 401

		if tipo == "funcionario" and usuario.get("status") not in (None, "ATIVO", "ativo", 1):
			return jsonify({"error": "E-mail ou senha inválidos"}), 401

		senha_valida, senha_legada = _verificar_senha(senha, usuario.get("senha_hash"))
		if not senha_valida:
			return jsonify({"error": "E-mail ou senha inválidos"}), 401

		if senha_legada:
			coluna_id = "id_cliente" if tipo == "cliente" else "id_funcionario"
			execute_query(
				f"UPDATE {tabela} SET senha_hash = %s WHERE {coluna_id} = %s",
				(generate_password_hash(senha), usuario["id"]),
			)

		return jsonify(
			{
				"message": "Login realizado com sucesso",
				"tipo_usuario": tipo,
				"usuario": {
					"id": usuario["id"],
					"nome": usuario["nome"],
					"email": usuario["email"],
				},
			}
		), 200
	except Exception:
		current_app.logger.exception("Falha ao autenticar usuário")
		return jsonify({"error": "Não foi possível concluir o login"}), 500


@aut_bp.route("/recuperacao", methods=["POST"])
def solicitar_recuperacao():
	return jsonify({"error": "Recuperação de senha ainda não configurada"}), 501


@aut_bp.route("/recuperacao/confirmar", methods=["POST"])
def confirmar_recuperacao():
	return jsonify({"error": "Recuperação de senha ainda não configurada"}), 501
