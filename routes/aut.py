import hashlib
import hmac
import os
import secrets
import smtplib
import threading
import time
from datetime import date
from email.message import EmailMessage

from flask import Blueprint, current_app, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from database import execute_query, execute_transaction, fetch_one

aut_bp = Blueprint("aut", __name__, url_prefix="/auth")
_codigos_recuperacao = {}
_lock_codigos_recuperacao = threading.Lock()


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


def _configuracao_recuperacao():
	secret_key = current_app.config.get("SECRET_KEY") or os.getenv("FLASK_SECRET_KEY")
	smtp_host = os.getenv("SMTP_HOST")
	smtp_username = os.getenv("SMTP_USERNAME")
	smtp_password = os.getenv("SMTP_PASSWORD")
	smtp_sender = os.getenv("SMTP_FROM") or smtp_username
	try:
		smtp_port = int(os.getenv("SMTP_PORT", "587"))
	except ValueError:
		return None

	if not all((secret_key, smtp_host, smtp_username, smtp_password, smtp_sender)):
		return None

	return {
		"secret_key": secret_key,
		"smtp_host": smtp_host,
		"smtp_port": smtp_port,
		"smtp_username": smtp_username,
		"smtp_password": smtp_password,
		"smtp_sender": smtp_sender,
		"smtp_tls": os.getenv("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes"),
	}


def _hash_codigo_recuperacao(secret_key, email, codigo):
	return hmac.new(
		secret_key.encode("utf-8"),
		f"{email}:{codigo}".encode("utf-8"),
		hashlib.sha256,
	).hexdigest()


def _enviar_email_recuperacao(email, codigo, configuracao):
	mensagem = EmailMessage()
	mensagem["Subject"] = "Recuperação de senha"
	mensagem["From"] = configuracao["smtp_sender"]
	mensagem["To"] = email
	mensagem.set_content(
		"Use o código abaixo para redefinir sua senha. Ele expira em 15 minutos.\n\n"
		f"{codigo}\n\n"
		"Se você não solicitou esta alteração, ignore esta mensagem."
	)

	with smtplib.SMTP(
		configuracao["smtp_host"], configuracao["smtp_port"], timeout=10
	) as servidor:
		if configuracao["smtp_tls"]:
			servidor.starttls()
		servidor.login(configuracao["smtp_username"], configuracao["smtp_password"])
		servidor.send_message(mensagem)

@aut_bp.route("/cadastro", methods=["POST"])
def cadastrar_cliente():
	dados = request.get_json(silent=True) or {}
	if not isinstance(dados, dict):
		return jsonify({"error": "O corpo da solicitação deve ser um objeto JSON"}), 400

	endereco = dados.get("endereco")
	habilitacao = dados.get("registro_habilitacao")
	campos_obrigatorios = {
		"nome": dados.get("nome"),
		"cpf": dados.get("cpf"),
		"rg": dados.get("rg"),
		"data_nascimento": dados.get("data_nascimento"),
		"telefone": dados.get("telefone"),
		"email": dados.get("email"),
		"senha": dados.get("senha"),
		"endereco.cep": endereco.get("cep") if isinstance(endereco, dict) else None,
		"endereco.logradouro": endereco.get("logradouro") if isinstance(endereco, dict) else None,
		"endereco.numero": endereco.get("numero") if isinstance(endereco, dict) else None,
		"endereco.cidade": endereco.get("cidade") if isinstance(endereco, dict) else None,
		"endereco.uf": endereco.get("uf") if isinstance(endereco, dict) else None,
		"registro_habilitacao.numero_registro": (
			habilitacao.get("numero_registro") if isinstance(habilitacao, dict) else None
		),
		"registro_habilitacao.categoria": (
			habilitacao.get("categoria") if isinstance(habilitacao, dict) else None
		),
		"registro_habilitacao.data_validade": (
			habilitacao.get("data_validade") if isinstance(habilitacao, dict) else None
		),
	}
	faltando = [
		campo for campo, valor in campos_obrigatorios.items()
		if valor is None or (isinstance(valor, str) and not valor.strip())
	]
	if faltando:
		return jsonify({"error": "Campos obrigatórios faltando", "campos": faltando}), 400

	campos_texto = ("nome", "cpf", "rg", "telefone", "email", "senha")
	if any(not isinstance(dados.get(campo), str) for campo in campos_texto):
		return jsonify({"error": "Os campos pessoais devem ser textos"}), 400
	for campo in ("nome_contato_emergencia", "telefone_contato_emergencia"):
		if campo in dados and dados[campo] is not None and not isinstance(dados[campo], str):
			return jsonify({"error": f"O campo {campo} deve ser texto"}), 400
	if not isinstance(endereco, dict) or not isinstance(habilitacao, dict):
		return jsonify({"error": "Endereço e habilitação devem ser objetos JSON"}), 400
	if any(
		not isinstance(endereco.get(campo), str)
		for campo in ("cep", "logradouro", "numero", "cidade", "uf")
	) or any(
		not isinstance(habilitacao.get(campo), str)
		for campo in ("numero_registro", "categoria", "data_validade")
	):
		return jsonify({"error": "Os campos de endereço e habilitação devem ser textos"}), 400

	email = dados["email"].strip().lower()
	senha = dados["senha"]
	if not isinstance(senha, str) or "@" not in email or len(senha) < 8:
		return jsonify({"error": "E-mail ou senha inválidos; use uma senha com ao menos 8 caracteres"}), 400

	cpf = "".join(caractere for caractere in dados["cpf"] if caractere.isdigit())
	if len(cpf) != 11:
		return jsonify({"error": "O CPF deve conter 11 dígitos"}), 400

	try:
		data_nascimento = date.fromisoformat(dados["data_nascimento"])
		data_validade = date.fromisoformat(habilitacao["data_validade"])
	except (TypeError, ValueError):
		return jsonify({"error": "Informe as datas no formato AAAA-MM-DD"}), 400
	if (
		data_nascimento.isoformat() != dados["data_nascimento"]
		or data_validade.isoformat() != habilitacao["data_validade"]
	):
		return jsonify({"error": "Informe as datas no formato AAAA-MM-DD"}), 400

	categoria = habilitacao["categoria"].upper()
	if categoria not in {"A", "B", "AB", "AC", "AD", "AE"}:
		return jsonify({"error": "Categoria de habilitação inválida"}), 400

	endereco_valores = (
		endereco["cep"].strip(),
		endereco["logradouro"].strip(),
		str(endereco["numero"]).strip(),
		(endereco.get("complemento") or "").strip() or None,
		endereco["cidade"].strip(),
		endereco["uf"].strip().upper(),
	)
	if len(endereco_valores[5]) != 2:
		return jsonify({"error": "A UF deve conter duas letras"}), 400

	try:
		existente = fetch_one(
			"""
			SELECT email AS valor FROM cliente WHERE email = %s
			UNION SELECT email FROM funcionario WHERE email = %s
			UNION SELECT cpf FROM cliente WHERE cpf = %s
			UNION SELECT numero_registro FROM registro_habilitacao
				WHERE numero_registro = %s
			LIMIT 1
			""",
			(email, email, cpf, habilitacao["numero_registro"].strip()),
		)
		if existente:
			return jsonify({"error": "E-mail, CPF ou CNH já cadastrados"}), 409

		queries = [
			(
				"""
				INSERT INTO cliente (
					nome, cpf, rg, data_nascimento, telefone, email, senha_hash,
					nome_contato_emergencia, telefone_contato_emergencia
				) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
				""",
				(
					dados["nome"].strip(),
					cpf,
					dados["rg"].strip(),
					data_nascimento,
					dados["telefone"].strip(),
					email,
					generate_password_hash(senha),
					(dados.get("nome_contato_emergencia") or "").strip() or None,
					(dados.get("telefone_contato_emergencia") or "").strip() or None,
				),
			),
			("SET @id_cliente_cadastro = LAST_INSERT_ID()", ()),
			(
				"""
				INSERT INTO endereco (
					id_cliente, cep, logradouro, numero, complemento, cidade, uf
				) VALUES (@id_cliente_cadastro, %s, %s, %s, %s, %s, %s)
				""",
				endereco_valores,
			),
			(
				"""
				INSERT INTO registro_habilitacao (
					id_cliente, numero_registro, categoria, data_validade
				) VALUES (@id_cliente_cadastro, %s, %s, %s)
				""",
				(
					habilitacao["numero_registro"].strip(),
					categoria,
					data_validade,
				),
			),
		]
		cliente_id = execute_transaction(queries)[0]
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
def recuperar_senha():
	dados = request.get_json(silent=True) or {}
	email = dados.get("email", "")
	if not isinstance(email, str) or "@" not in email:
		return jsonify({"error": "Informe um e-mail válido"}), 400

	configuracao = _configuracao_recuperacao()
	if not configuracao:
		return jsonify({"error": "Recuperação indisponível: configure o serviço de e-mail"}), 503

	email = email.strip().lower()
	try:
		usuario = fetch_one(
			"SELECT id_cliente AS id, email, senha_hash FROM cliente WHERE email = %s",
			(email,),
		)
		tipo = "cliente"
		if not usuario:
			usuario = fetch_one(
				"SELECT id_funcionario AS id, email, senha_hash, status "
				"FROM funcionario WHERE email = %s",
				(email,),
			)
			tipo = "funcionario"

		if usuario and usuario.get("senha_hash") and (
			tipo != "funcionario"
			or usuario.get("status") in (None, "ATIVO", "ativo", 1)
		):
			codigo = str(secrets.randbelow(900000) + 100000)
			registro = {
				"id": usuario["id"],
				"tipo": tipo,
				"codigo_hash": _hash_codigo_recuperacao(
					configuracao["secret_key"], email, codigo
				),
				"expira_em": time.time() + 900,
				"tentativas": 0,
			}
			with _lock_codigos_recuperacao:
				_codigos_recuperacao[email] = registro
			try:
				_enviar_email_recuperacao(email, codigo, configuracao)
			except Exception:
				current_app.logger.exception("Falha ao enviar e-mail de recuperação")
				with _lock_codigos_recuperacao:
					if _codigos_recuperacao.get(email) is registro:
						_codigos_recuperacao.pop(email, None)

		return jsonify(
			{"message": "Se o e-mail estiver cadastrado, você receberá as instruções de recuperação"}
		), 200
	except Exception:
		current_app.logger.exception("Falha ao solicitar recuperação de senha")
		return jsonify({"error": "Não foi possível solicitar a recuperação"}), 500


@aut_bp.route("/atualizaSenha", methods=["PUT"])
@aut_bp.route("/recuperacao/confirmar", methods=["POST"])
def atualizar_senha():
	dados = request.get_json(silent=True) or {}
	email = dados.get("email", dados.get("emailUsuario", ""))
	codigo = dados.get("codigo", dados.get("codigoRecuperacao", ""))
	nova_senha = dados.get("nova_senha", dados.get("novaSenha", ""))
	if (
		not isinstance(email, str)
		or not isinstance(codigo, str)
		or not isinstance(nova_senha, str)
		or "@" not in email
		or len(codigo) != 6
		or not codigo.isdigit()
		or len(nova_senha) < 8
	):
		return jsonify({"error": "Informe e-mail, código e senha com ao menos 8 caracteres"}), 400

	configuracao = _configuracao_recuperacao()
	if not configuracao:
		return jsonify({"error": "Recuperação indisponível: configure o serviço de e-mail"}), 503

	email = email.strip().lower()

	try:
		with _lock_codigos_recuperacao:
			registro = _codigos_recuperacao.get(email)
			if not registro or registro["expira_em"] < time.time():
				_codigos_recuperacao.pop(email, None)
				return jsonify({"error": "Código inválido ou expirado"}), 400

			hash_informado = _hash_codigo_recuperacao(
				configuracao["secret_key"], email, codigo
			)
			if not hmac.compare_digest(registro["codigo_hash"], hash_informado):
				registro["tentativas"] += 1
				if registro["tentativas"] >= 5:
					_codigos_recuperacao.pop(email, None)
				return jsonify({"error": "Código inválido ou expirado"}), 400

			if registro["tipo"] == "cliente":
				usuario = fetch_one(
					"SELECT id_cliente AS id, email FROM cliente WHERE id_cliente = %s",
					(registro["id"],),
				)
				tabela = "cliente"
				coluna_id = "id_cliente"
			elif registro["tipo"] == "funcionario":
				usuario = fetch_one(
					"SELECT id_funcionario AS id, email, status "
					"FROM funcionario WHERE id_funcionario = %s",
					(registro["id"],),
				)
				tabela = "funcionario"
				coluna_id = "id_funcionario"
			else:
				_codigos_recuperacao.pop(email, None)
				return jsonify({"error": "Código inválido ou expirado"}), 400

			if (
				not usuario
				or usuario.get("email", "").strip().lower() != email
				or (
					registro["tipo"] == "funcionario"
					and usuario.get("status") not in (None, "ATIVO", "ativo", 1)
				)
			):
				_codigos_recuperacao.pop(email, None)
				return jsonify({"error": "Código inválido ou expirado"}), 400

			execute_query(
				f"UPDATE {tabela} SET senha_hash = %s WHERE {coluna_id} = %s",
				(generate_password_hash(nova_senha), usuario["id"]),
			)
			_codigos_recuperacao.pop(email, None)
			return jsonify({"message": "Senha atualizada com sucesso"}), 200
	except Exception:
		current_app.logger.exception("Falha ao atualizar senha")
		return jsonify({"error": "Não foi possível atualizar a senha"}), 500
