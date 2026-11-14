import threading
import time
import os
from collections import defaultdict, deque
from functools import wraps

from flask import jsonify, request


_tentativas = defaultdict(deque)
_lock = threading.Lock()


def rate_limit(limite, janela_segundos):
    def decorador(funcao):
        @wraps(funcao)
        def protegida(*args, **kwargs):
            from flask import current_app

            if current_app.config.get("TESTING") or os.getenv("APP_ENV") == "test":
                return funcao(*args, **kwargs)
            chave = f"{request.remote_addr or 'unknown'}:{request.endpoint}"
            agora = time.monotonic()
            with _lock:
                tentativas = _tentativas[chave]
                while tentativas and agora - tentativas[0] >= janela_segundos:
                    tentativas.popleft()
                if len(tentativas) >= limite:
                    return jsonify({"error": "Muitas tentativas; tente novamente mais tarde"}), 429
                tentativas.append(agora)
            return funcao(*args, **kwargs)

        return protegida

    return decorador


def clear_rate_limits():
    with _lock:
        _tentativas.clear()
