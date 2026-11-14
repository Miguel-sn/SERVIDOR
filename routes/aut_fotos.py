from pathlib import Path

from flask import Blueprint, current_app, g, jsonify, request
from PIL import Image, UnidentifiedImageError

from routes.jwt_auth import jwt_permitido
from storage import StorageError, save_file
aut_fotos_bp = Blueprint("aut_fotos", __name__, url_prefix="/auth")

_FOTOS_ESPERADAS = {
    "foto_frente_cnh": "frente_cnh",
    "foto_verso_cnh": "verso_cnh",
    "foto_rosto": "rosto",
}
_EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".webp"}


@aut_fotos_bp.route("/fotos/<int:id_cliente>", methods=["POST"])
@jwt_permitido("cliente", "funcionario")
def salvar_fotos_cliente(id_cliente):
    if (
        g.identidade_jwt["tipo_usuario"] == "cliente"
        and g.identidade_jwt["id"] != id_cliente
    ):
        return jsonify({"error": "Acesso não autorizado"}), 403

    faltando = [
        campo
        for campo in _FOTOS_ESPERADAS
        if campo not in request.files or not request.files[campo].filename
    ]
    if faltando:
        return jsonify({"error": "Envie as três fotos do cadastro", "campos": faltando}), 400

    arquivos = {
        campo: request.files[campo]
        for campo in _FOTOS_ESPERADAS
    }
    extensoes = {
        campo: Path(arquivo.filename).suffix.lower()
        for campo, arquivo in arquivos.items()
    }
    invalidas = [
        campo
        for campo, extensao in extensoes.items()
        if extensao not in _EXTENSOES_IMAGEM
    ]
    if invalidas:
        return jsonify({"error": "Formato de imagem inválido", "campos": invalidas}), 400

    try:
        caminhos = {}
        for campo, nome_base in _FOTOS_ESPERADAS.items():
            arquivo = arquivos[campo]
            try:
                imagem = Image.open(arquivo.stream)
                imagem.verify()
                arquivo.stream.seek(0)
            except (UnidentifiedImageError, OSError):
                return jsonify({"error": "Arquivo de imagem inválido", "campo": campo}), 400

            caminho = f"clientes/{id_cliente}/{nome_base}{extensoes[campo]}"
            caminhos[campo] = save_file(arquivo, caminho)
    except (OSError, StorageError):
        current_app.logger.exception("Falha ao salvar fotos do cliente %s", id_cliente)
        return jsonify({"error": "Não foi possível salvar as fotos"}), 500

    return jsonify({"message": "Fotos armazenadas", "arquivos": caminhos}), 201