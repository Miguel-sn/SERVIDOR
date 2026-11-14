import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image

from app import app
from routes.jwt_auth import criar_token_acesso


def imagem_valida(formato):
    buffer = BytesIO()
    Image.new("RGB", (2, 2), "white").save(buffer, format=formato)
    buffer.seek(0)
    return buffer


class ClienteFotosApiTests(unittest.TestCase):
    def setUp(self):
        self.uploads = tempfile.TemporaryDirectory()
        self.upload_folder_anterior = app.config.get("UPLOAD_FOLDER")
        app.config["UPLOAD_FOLDER"] = self.uploads.name
        self.client = app.test_client()
        with app.app_context():
            self.headers = {
                "Authorization": f"Bearer {criar_token_acesso(41, 'cliente')}"
            }

    def tearDown(self):
        self.uploads.cleanup()
        if self.upload_folder_anterior is None:
            app.config.pop("UPLOAD_FOLDER", None)
        else:
            app.config["UPLOAD_FOLDER"] = self.upload_folder_anterior

    def test_guarda_as_tres_fotos_na_pasta_do_cliente(self):
        resposta = self.client.post(
            "/auth/fotos/41",
            data={
                "foto_frente_cnh": (imagem_valida("JPEG"), "frente.jpg"),
                "foto_verso_cnh": (imagem_valida("PNG"), "verso.png"),
                "foto_rosto": (imagem_valida("WEBP"), "rosto.webp"),
            },
            headers=self.headers,
        )

        self.assertEqual(resposta.status_code, 201)
        pasta_cliente = Path(self.uploads.name) / "clientes" / "41"
        self.assertTrue((pasta_cliente / "frente_cnh.jpg").exists())
        self.assertTrue((pasta_cliente / "verso_cnh.png").exists())
        self.assertTrue((pasta_cliente / "rosto.webp").exists())

    def test_rejeita_envio_sem_as_tres_fotos(self):
        resposta = self.client.post(
            "/auth/fotos/41",
            data={"foto_frente_cnh": (BytesIO(b"frente"), "frente.jpg")},
            headers=self.headers,
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("foto_verso_cnh", resposta.json["campos"])
        self.assertIn("foto_rosto", resposta.json["campos"])
        self.assertFalse((Path(self.uploads.name) / "clientes").exists())

    def test_rejeita_extensao_que_nao_e_de_imagem(self):
        resposta = self.client.post(
            "/auth/fotos/41",
            data={
                "foto_frente_cnh": (BytesIO(b"frente"), "frente.exe"),
                "foto_verso_cnh": (BytesIO(b"verso"), "verso.jpg"),
                "foto_rosto": (BytesIO(b"rosto"), "rosto.jpg"),
            },
            headers=self.headers,
        )

        self.assertEqual(resposta.status_code, 400)

    def test_exige_token_jwt(self):
        resposta = self.client.post("/auth/fotos/41")

        self.assertEqual(resposta.status_code, 401)

if __name__ == "__main__":
    unittest.main()
