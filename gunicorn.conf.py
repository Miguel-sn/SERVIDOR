import multiprocessing
import os


bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"
workers = max(2, multiprocessing.cpu_count() * 2 + 1)
timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")
