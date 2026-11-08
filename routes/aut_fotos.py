from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

aut_fotos_bp = Blueprint("aut_fotos", __name__, url_prefix="/auth")

_FOTOS_ESPERADAS = {
    "foto_frente_cnh": "frente_cnh",
    "foto_verso_cnh": "verso_cnh",
    "foto_rosto": "rosto",
}
_EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".webp"}


@aut_fotos_bp.route("/fotos/<int:id_cliente>", methods=["POST"])
def salvar_fotos_cliente(id_cliente):
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

    pasta_cliente = Path(
        current_app.config.get(
            "UPLOAD_FOLDER",
            Path(current_app.root_path) / "uploads",
        )
    ) / "clientes" / str(id_cliente)

    try:
        pasta_cliente.mkdir(parents=True, exist_ok=True)
        caminhos = {}
        for campo, nome_base in _FOTOS_ESPERADAS.items():
            caminho = pasta_cliente / f"{nome_base}{extensoes[campo]}"
            arquivos[campo].save(caminho)
            caminhos[campo] = caminho.name
    except OSError:
        current_app.logger.exception("Falha ao salvar fotos do cliente %s", id_cliente)
        return jsonify({"error": "Não foi possível salvar as fotos"}), 500

    return jsonify({"message": "Fotos armazenadas", "arquivos": caminhos}), 201