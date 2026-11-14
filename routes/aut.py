import hashlib
import hmac
import os
import re
import secrets
import smtplib
import threading
import time
from datetime import date
from email.message import EmailMessage

from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from database import (
	TransactionConflictError,
	execute_query,
	execute_transaction,
	fetch_one,
)
from routes.jwt_auth import JWTConfiguracaoError, criar_token_acesso, jwt_obrigatorio

aut_bp = Blueprint("aut", __name__, url_prefix="/auth")
_solicitacoes_recuperacao_por_ip = {}
_lock_rate_limit_recuperacao = threading.Lock()
_MENSAGEM_RECUPERACAO = (
	"Se o e-mail estiver cadastrado, você receberá as instruções para recuperar sua senha."
)


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
	mail_server = os.getenv("MAIL_SERVER")
	mail_username = os.getenv("MAIL_USERNAME")
	mail_password = os.getenv("MAIL_PASSWORD")
	mail_sender = os.getenv("MAIL_DEFAULT_SENDER") or mail_username
	try:
		mail_port = int(os.getenv("MAIL_PORT", "587"))
	except ValueError:
		return None

	mail_use_tls = os.getenv("MAIL_USE_TLS", "true").lower() in ("1", "true", "yes")
	mail_use_ssl = os.getenv("MAIL_USE_SSL", "false").lower() in ("1", "true", "yes")
	if (
		not all((mail_server, mail_username, mail_password, mail_sender))
		or mail_use_tls and mail_use_ssl
		or not mail_use_tls and not mail_use_ssl
	):
		return None

	return {
		"mail_server": mail_server,
		"mail_port": mail_port,
		"mail_username": mail_username,
		"mail_password": mail_password,
		"mail_sender": mail_sender,
		"mail_use_tls": mail_use_tls,
		"mail_use_ssl": mail_use_ssl,
	}


def _hash_token_recuperacao(token):
	chave = (
		current_app.config.get("JWT_SECRET_KEY")
		or current_app.config.get("SECRET_KEY")
		or os.getenv("JWT_SECRET_KEY")
		or os.getenv("FLASK_SECRET_KEY")
	)
	if not isinstance(chave, str) or not chave:
		raise RuntimeError("Chave de aplicação não configurada")
	return hmac.new(
		chave.encode("utf-8"), token.encode("utf-8"), hashlib.sha256
	).hexdigest()


def _enviar_email_recuperacao(email, token, configuracao):
	mensagem = EmailMessage()
	mensagem["Subject"] = "Recuperação de senha"
	mensagem["From"] = configuracao["mail_sender"]
	mensagem["To"] = email
	mensagem.set_content(
		"Use o código de 6 dígitos abaixo no aplicativo Loca Já para redefinir "
		"sua senha. Ele expira em 15 minutos e só pode ser utilizado uma vez.\n\n"
		f"{token}\n\n"
		"Se você não solicitou esta alteração, ignore esta mensagem."
	)

	tipo_smtp = smtplib.SMTP_SSL if configuracao["mail_use_ssl"] else smtplib.SMTP
	with tipo_smtp(
		configuracao["mail_server"], configuracao["mail_port"], timeout=10
	) as servidor:
		if configuracao["mail_use_tls"]:
			servidor.starttls()
		servidor.login(
			configuracao["mail_username"], configuracao["mail_password"]
		)
		servidor.send_message(mensagem)


def _permitir_requisicao_recuperacao(chave, limite, janela_segundos):
	agora = time.monotonic()
	with _lock_rate_limit_recuperacao:
		for chave_existente, horarios in list(_solicitacoes_recuperacao_por_ip.items()):
			horarios_validos = [
				horario
				for horario in horarios
				if agora - horario < janela_segundos
			]
			if horarios_validos:
				_solicitacoes_recuperacao_por_ip[chave_existente] = horarios_validos
			else:
				_solicitacoes_recuperacao_por_ip.pop(chave_existente, None)

		horarios = _solicitacoes_recuperacao_por_ip.setdefault(chave, [])
		if len(horarios) >= limite:
			return False
		horarios.append(agora)
		return True


def _token_recuperacao_valido(token):
	return (
		isinstance(token, str)
		and re.fullmatch(r"[0-9]{6}", token) is not None
	)


def _buscar_token_recuperacao(token):
	registro = fetch_one(
		"""
		SELECT id_token, id_cliente, id_funcionario
		FROM token_recuperacao
		WHERE token_hash = %s
			AND utilizado_em IS NULL
			AND expira_em > CURRENT_TIMESTAMP
		""",
		(_hash_token_recuperacao(token),),
	)
	if not registro:
		return None

	if registro["id_cliente"] is not None:
		usuario = fetch_one(
			"SELECT id_cliente AS id FROM cliente "
			"WHERE id_cliente = %s AND status_cliente = 'ATIVO'",
			(registro["id_cliente"],),
		)
		tipo = "cliente"
		coluna_usuario = "id_cliente"
		coluna_status_usuario = "status_cliente"
		tabela_usuario = "cliente"
	else:
		usuario = fetch_one(
			"SELECT id_funcionario AS id FROM funcionario "
			"WHERE id_funcionario = %s AND status_funcionario = 'ATIVO'",
			(registro["id_funcionario"],),
		)
		tipo = "funcionario"
		coluna_usuario = "id_funcionario"
		coluna_status_usuario = "status_funcionario"
		tabela_usuario = "funcionario"

	if not usuario:
		return None

	return {
		"id_token": registro["id_token"],
		"id_usuario": usuario["id"],
		"coluna_usuario": coluna_usuario,
		"coluna_status_usuario": coluna_status_usuario,
		"tabela_usuario": tabela_usuario,
		"tipo_usuario": tipo,
	}

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
	campos_contato_nao_persistidos = [
		campo
		for campo in ("nome_contato_emergencia", "telefone_contato_emergencia")
		if dados.get(campo) not in (None, "")
	]
	if campos_contato_nao_persistidos:
		return jsonify(
			{
				"error": "O schema atual não armazena contato de emergência",
				"campos": campos_contato_nao_persistidos,
			}
		), 400
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
					nome, cpf, rg, data_nascimento, telefone, email, senha_hash
				) VALUES (%s, %s, %s, %s, %s, %s, %s)
				""",
				(
					dados["nome"].strip(),
					cpf,
					dados["rg"].strip(),
					data_nascimento,
					dados["telefone"].strip(),
					email,
					generate_password_hash(senha),
				),
			),
			(
				"""
				INSERT INTO endereco (
					id_cliente, cep, logradouro, numero, complemento, cidade, uf
				)
				SELECT id_cliente, %s, %s, %s, %s, %s, %s
				FROM cliente WHERE email = %s
				""",
				(*endereco_valores, email),
			),
			(
				"""
				INSERT INTO registro_habilitacao (
					id_cliente, numero_registro, categoria, data_validade
				)
				SELECT id_cliente, %s, %s, %s
				FROM cliente WHERE email = %s
				""",
				(
					habilitacao["numero_registro"].strip(),
					categoria,
					data_validade,
					email,
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
			"SELECT id_cliente AS id, nome_cliente AS nome, email, senha_hash, "
			"status_cliente AS status "
			"FROM cliente WHERE email = %s",
			(email,),
		)
		tabela = "cliente"
		tipo = "cliente"

		if not usuario:
			usuario = fetch_one(
				"SELECT id_funcionario AS id, nome_funcionario AS nome, email, "
				"senha_hash, status_funcionario AS status, perfil "
				"FROM funcionario WHERE email = %s",
				(email,),
			)
			tabela = "funcionario"
			tipo = "funcionario"

		if not usuario:
			return jsonify({"error": "E-mail ou senha inválidos"}), 401

		if usuario.get("status") != "ATIVO":
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

		try:
			token = criar_token_acesso(usuario["id"], tipo)
		except JWTConfiguracaoError:
			current_app.logger.error("JWT não configurado no servidor")
			return jsonify({"error": "Autenticação indisponível"}), 503

		return jsonify(
			{
				"message": "Login realizado com sucesso",
				"access_token": token,
				"token_type": "Bearer",
				"expires_in": 3600,
				"tipo_usuario": tipo,
				"usuario": {
					"id": usuario["id"],
					"nome": usuario["nome"],
					"email": usuario["email"],
					**(
						{"perfil": usuario["perfil"]}
						if tipo == "funcionario"
						else {}
					),
				},
			}
		), 200
	except Exception:
		current_app.logger.exception("Falha ao autenticar usuário")
		return jsonify({"error": "Não foi possível concluir o login"}), 500


@aut_bp.route("/me", methods=["GET"])
@jwt_obrigatorio
def perfil_autenticado():
	if g.identidade_jwt["tipo_usuario"] != "cliente":
		return jsonify({"error": "O perfil de condutor está disponível para clientes"}), 403
	try:
		cliente = fetch_one(
			"""
			SELECT c.id_cliente, c.nome_cliente AS nome, c.cpf,
				h.numero_registro,
				c.telefone, e.cidade
			FROM cliente c
			LEFT JOIN registro_habilitacao h ON h.id_cliente = c.id_cliente
			LEFT JOIN endereco e ON e.id_cliente = c.id_cliente
			WHERE c.id_cliente = %s AND c.status_cliente = 'ATIVO'
			""",
			(g.identidade_jwt["id"],),
		)
		if not cliente:
			return jsonify({"error": "Cliente não encontrado"}), 404
		return jsonify(
			{
				"id": cliente["id_cliente"],
				"nome": cliente["nome"],
				"cpf": cliente["cpf"],
				"cnh": cliente["numero_registro"] or "",
				"telefone": cliente["telefone"],
				"cidade": cliente["cidade"] or "",
			}
		), 200
	except Exception:
		current_app.logger.exception("Falha ao carregar perfil autenticado")
		return jsonify({"error": "Não foi possível carregar o perfil"}), 500


@aut_bp.route("/recuperacao", methods=["POST"])
def recuperar_senha():
	dados = request.get_json(silent=True) or {}
	if not isinstance(dados, dict):
		return jsonify({"error": "O corpo da solicitação deve ser um objeto JSON"}), 400

	email = dados.get("email", "")
	if (
		not isinstance(email, str)
		or len(email.strip()) > 254
		or re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()) is None
	):
		return jsonify({"error": "Informe um e-mail válido"}), 400

	configuracao = _configuracao_recuperacao()
	if not configuracao:
		return jsonify({"error": "Serviço de recuperação temporariamente indisponível"}), 503

	email = email.strip().lower()
	chave_ip = f"solicitacao:{request.remote_addr or 'desconhecido'}"
	if not _permitir_requisicao_recuperacao(chave_ip, 5, 15 * 60):
		return jsonify({"message": _MENSAGEM_RECUPERACAO}), 200

	try:
		usuario = fetch_one(
			"SELECT id_cliente AS id, email, status_cliente AS status "
			"FROM cliente WHERE email = %s",
			(email,),
		)
		tipo = "cliente"
		if not usuario:
			usuario = fetch_one(
				"SELECT id_funcionario AS id, email, "
				"status_funcionario AS status "
				"FROM funcionario WHERE email = %s",
				(email,),
			)
			tipo = "funcionario"

		if usuario and usuario.get("status") == "ATIVO":
			coluna_usuario = "id_cliente" if tipo == "cliente" else "id_funcionario"
			solicitacoes_recentes = fetch_one(
				f"""
				SELECT COUNT(*) AS total FROM token_recuperacao
				WHERE {coluna_usuario} = %s
					AND criado_em >= DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 1 HOUR)
				""",
				(usuario["id"],),
			)
			if solicitacoes_recentes["total"] < 3:
				token = f"{secrets.randbelow(1_000_000):06d}"
				token_hash = _hash_token_recuperacao(token)
				execute_transaction(
					[
						(
							f"""
							UPDATE token_recuperacao
							SET utilizado_em = CURRENT_TIMESTAMP
							WHERE {coluna_usuario} = %s AND utilizado_em IS NULL
							""",
							(usuario["id"],),
						),
						(
							"""
							INSERT INTO token_recuperacao (
								id_cliente, id_funcionario, token_hash, expira_em
							) VALUES (
								%s, %s, %s,
								DATE_ADD(CURRENT_TIMESTAMP, INTERVAL 15 MINUTE)
							)
							""",
							(
								usuario["id"] if tipo == "cliente" else None,
								usuario["id"] if tipo == "funcionario" else None,
								token_hash,
							),
						),
					]
				)
				try:
					_enviar_email_recuperacao(email, token, configuracao)
				except Exception:
					current_app.logger.error("Falha ao enviar e-mail de recuperação")
					try:
						execute_query(
							"""
							UPDATE token_recuperacao
							SET utilizado_em = CURRENT_TIMESTAMP
							WHERE token_hash = %s AND utilizado_em IS NULL
							""",
							(token_hash,),
						)
					except Exception:
						current_app.logger.error(
							"Falha ao invalidar token de recuperação não enviado"
						)

		return jsonify({"message": _MENSAGEM_RECUPERACAO}), 200
	except Exception:
		current_app.logger.exception("Falha ao solicitar recuperação de senha")
		return jsonify({"error": "Não foi possível solicitar a recuperação"}), 500


@aut_bp.route("/recuperacao/validar", methods=["POST"])
def validar_token_recuperacao():
	dados = request.get_json(silent=True) or {}
	if not isinstance(dados, dict):
		return jsonify({"error": "O corpo da solicitação deve ser um objeto JSON"}), 400

	token = dados.get("token", "")
	if not _token_recuperacao_valido(token):
		return jsonify({"error": "Token inválido ou expirado"}), 400

	chave_ip = f"tentativa:{request.remote_addr or 'desconhecido'}"
	if not _permitir_requisicao_recuperacao(chave_ip, 5, 15 * 60):
		return jsonify({"error": "Muitas tentativas. Tente novamente mais tarde."}), 429

	try:
		if not _buscar_token_recuperacao(token):
			return jsonify({"error": "Token inválido ou expirado"}), 400
		return jsonify({"message": "Token validado com sucesso"}), 200
	except Exception:
		current_app.logger.exception("Falha ao validar token de recuperação")
		return jsonify({"error": "Não foi possível validar o token"}), 500


@aut_bp.route("/atualizaSenha", methods=["PUT"])
@aut_bp.route("/recuperacao/confirmar", methods=["POST"])
def atualizar_senha():
	dados = request.get_json(silent=True) or {}
	if not isinstance(dados, dict):
		return jsonify({"error": "O corpo da solicitação deve ser um objeto JSON"}), 400

	token = dados.get("token", "")
	nova_senha = dados.get("nova_senha", dados.get("novaSenha", ""))
	if (
		not _token_recuperacao_valido(token)
		or not isinstance(nova_senha, str)
		or len(nova_senha) < 8
	):
		return jsonify({"error": "Informe um token válido e uma senha com ao menos 8 caracteres"}), 400

	chave_ip = f"tentativa:{request.remote_addr or 'desconhecido'}"
	if not _permitir_requisicao_recuperacao(chave_ip, 5, 15 * 60):
		return jsonify({"error": "Muitas tentativas. Tente novamente mais tarde."}), 429

	try:
		registro = _buscar_token_recuperacao(token)
		if not registro:
			return jsonify({"error": "Token inválido ou expirado"}), 400

		execute_transaction(
			[
				(
					"""
					UPDATE token_recuperacao
					SET utilizado_em = CURRENT_TIMESTAMP
					WHERE id_token = %s
						AND utilizado_em IS NULL
						AND expira_em > CURRENT_TIMESTAMP
					""",
					(registro["id_token"],),
				),
				(
					f"UPDATE {registro['tabela_usuario']} SET senha_hash = %s "
					f"WHERE {registro['coluna_usuario']} = %s "
					f"AND {registro['coluna_status_usuario']} = 'ATIVO'",
					(generate_password_hash(nova_senha), registro["id_usuario"]),
				),
			],
			expected_rowcounts={0: 1, 1: 1},
		)
		return jsonify({"message": "Senha atualizada com sucesso"}), 200
	except TransactionConflictError:
		return jsonify({"error": "Token inválido ou expirado"}), 400
	except Exception:
		current_app.logger.exception("Falha ao atualizar senha")
		return jsonify({"error": "Não foi possível atualizar a senha"}), 500
