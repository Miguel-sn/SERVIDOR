from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename


class StorageError(RuntimeError):
    pass


def save_file(file_storage, relative_path):
    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    if upload_folder:
        destination = Path(upload_folder) / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        file_storage.save(destination)
        return destination.name

    try:
        from firebase_admin import storage

        bucket = storage.bucket()
    except Exception as erro:
        raise StorageError("Storage externo não configurado") from erro

    blob = bucket.blob(relative_path.replace("\\", "/"))
    blob.upload_from_file(
        file_storage.stream,
        content_type=file_storage.mimetype or "application/octet-stream",
    )
    return secure_filename(Path(relative_path).name)
