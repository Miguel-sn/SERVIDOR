import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from dotenv import load_dotenv

import jwt
from flask import current_app, g, jsonify, request
load_dotenv()

_TEMPO_EXPIRACAO_TOKEN = timedelta(hours=1)


class JWTConfiguracaoError(RuntimeError):
    pass


def _chave_jwt():
    chave = (
        current_app.config.get("JWT_SECRET_KEY")
        or current_app.config.get("SECRET_KEY")
        or os.getenv("JWT_SECRET_KEY")
        or os.getenv("FLASK_SECRET_KEY")
    )
    if not isinstance(chave, str) or not chave:
        raise JWTConfiguracaoError(
            "Configure JWT_SECRET_KEY ou FLASK_SECRET_KEY para habilitar JWT"
        )
    return chave


def criar_token_acesso(usuario_id, tipo_usuario):
    agora = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(usuario_id),
            "tipo_usuario": tipo_usuario,
            "iat": agora,
            "exp": agora + _TEMPO_EXPIRACAO_TOKEN,
        },
        _chave_jwt(),
        algorithm="HS256",
    )


def jwt_obrigatorio(funcao):
    @wraps(funcao)
    def decorada(*args, **kwargs):
        try:
            chave = _chave_jwt()
        except JWTConfiguracaoError:
            current_app.logger.error("JWT não configurado no servidor")
            return jsonify({"error": "Autenticação indisponível"}), 503

        esquema, separador, token = request.headers.get(
            "Authorization", ""
        ).partition(" ")
        if esquema.lower() != "bearer" or not separador or not token.strip():
            return jsonify({"error": "Token Bearer obrigatório"}), 401

        try:
            identidade = jwt.decode(
                token.strip(),
                chave,
                algorithms=["HS256"],
                options={"require": ["exp", "iat", "sub", "tipo_usuario"]},
            )
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token inválido ou expirado"}), 401

        usuario_id = identidade["sub"]
        tipo_usuario = identidade["tipo_usuario"]
        if (
            not isinstance(usuario_id, str)
            or not usuario_id.isdigit()
            or tipo_usuario not in {"cliente", "funcionario"}
        ):
            return jsonify({"error": "Token inválido ou expirado"}), 401

        g.identidade_jwt = {
            "id": int(usuario_id),
            "tipo_usuario": tipo_usuario,
        }
        return funcao(*args, **kwargs)

    return decorada
