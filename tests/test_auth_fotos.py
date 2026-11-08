import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from app import app


class ClienteFotosApiTests(unittest.TestCase):
    def setUp(self):
        self.uploads = tempfile.TemporaryDirectory()
        self.upload_folder_anterior = app.config.get("UPLOAD_FOLDER")
        app.config["UPLOAD_FOLDER"] = self.uploads.name
        self.client = app.test_client()

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
                "foto_frente_cnh": (BytesIO(b"frente"), "frente.jpg"),
                "foto_verso_cnh": (BytesIO(b"verso"), "verso.png"),
                "foto_rosto": (BytesIO(b"rosto"), "rosto.webp"),
            },
        )

        self.assertEqual(resposta.status_code, 201)
        pasta_cliente = Path(self.uploads.name) / "clientes" / "41"
        self.assertEqual((pasta_cliente / "frente_cnh.jpg").read_bytes(), b"frente")
        self.assertEqual((pasta_cliente / "verso_cnh.png").read_bytes(), b"verso")
        self.assertEqual((pasta_cliente / "rosto.webp").read_bytes(), b"rosto")

    def test_rejeita_envio_sem_as_tres_fotos(self):
        resposta = self.client.post(
            "/auth/fotos/41",
            data={"foto_frente_cnh": (BytesIO(b"frente"), "frente.jpg")},
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
        )

        self.assertEqual(resposta.status_code, 400)

if __name__ == "__main__":
    unittest.main()
