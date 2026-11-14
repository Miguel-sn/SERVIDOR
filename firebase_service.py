import json
import logging
import os

logger = logging.getLogger(__name__)


def _criar_cliente_firestore():
    credenciais = os.getenv("FIREBASE_CREDENCIAIS")
    if not credenciais:
        logger.info("Firebase desabilitado: FIREBASE_CREDENCIAIS não foi definida.")
        return None

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ModuleNotFoundError:
        logger.warning(
            "Firebase desabilitado: instale as dependências de requirements.txt."
        )
        return None

    try:
        configuracao = json.loads(credenciais)
        if not isinstance(configuracao, dict):
            raise ValueError("FIREBASE_CREDENCIAIS deve conter um objeto JSON.")

        try:
            aplicativo = firebase_admin.get_app()
        except ValueError:
            opcoes = {}
            bucket = os.getenv("FIREBASE_STORAGE_BUCKET")
            if bucket:
                opcoes["storageBucket"] = bucket
            aplicativo = firebase_admin.initialize_app(
                credentials.Certificate(configuracao),
                opcoes,
            )
        return firestore.client(app=aplicativo)
    except (TypeError, ValueError, json.JSONDecodeError) as erro:
        logger.warning("Firebase desabilitado: credenciais inválidas (%s).", erro)
        return None


db = _criar_cliente_firestore()
