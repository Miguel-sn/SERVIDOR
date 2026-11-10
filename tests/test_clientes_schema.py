import unittest
from datetime import date
from unittest.mock import patch

import jwt
from werkzeug.security import check_password_hash

from app import app
from database import execute_transaction
from routes.jwt_auth import criar_token_acesso


class ClienteSchemaApiTests(unittest.TestCase):
    def setUp(self):
        self.jwt_secret_anterior = app.config.get("JWT_SECRET_KEY")
        app.config["JWT_SECRET_KEY"] = "test-jwt-secret-key-that-is-32bytes!"
        self.client = app.test_client()
        with app.app_context():
            self.headers_jwt = {
                "Authorization": f"Bearer {criar_token_acesso(41, 'funcionario')}"
            }

    def tearDown(self):
        if self.jwt_secret_anterior is None:
            app.config.pop("JWT_SECRET_KEY", None)
        else:
            app.config["JWT_SECRET_KEY"] = self.jwt_secret_anterior

    def test_loga_requisicao_antes_de_responder(self):
        with self.assertLogs(app.logger, level="INFO") as registros:
            resposta = self.client.get("/")

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(
            any(
                "Requisição recebida: GET /" in registro
                for registro in registros.output
            )
        )

    def test_preflight_cors_permite_origem_local_do_flutter_web(self):
        resposta = self.client.options(
            "/auth/cadastro",
            headers={
                "Origin": "http://localhost:54321",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,authorization",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            resposta.headers["Access-Control-Allow-Origin"],
            "http://localhost:54321",
        )
        self.assertIn("POST", resposta.headers["Access-Control-Allow-Methods"])
        self.assertIn("Content-Type", resposta.headers["Access-Control-Allow-Headers"])
        self.assertIn("Authorization", resposta.headers["Access-Control-Allow-Headers"])

    def test_cors_nao_permite_origem_remota(self):
        resposta = self.client.options(
            "/auth/cadastro",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertNotIn("Access-Control-Allow-Origin", resposta.headers)

    def test_todas_as_rotas_clientes_exigem_token_jwt(self):
        respostas = (
            self.client.get("/clientes"),
            self.client.get("/clientes/41"),
            self.client.put("/clientes/41", json={"nome": "Ana"}),
            self.client.delete("/clientes/41"),
        )

        self.assertTrue(all(resposta.status_code == 401 for resposta in respostas))

    @patch("routes.aut._verificar_senha", return_value=(True, False))
    @patch(
        "routes.aut.fetch_one",
        return_value={
            "id": 41,
            "nome": "Ana Exemplo",
            "email": "ana@example.com",
            "senha_hash": "hash-de-teste",
        },
    )
    def test_login_emite_token_jwt(self, fetch_one_mock, verificar_senha_mock):
        resposta = self.client.post(
            "/auth/login",
            json={"email": "ana@example.com", "senha": "SenhaSegura123"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["token_type"], "Bearer")
        self.assertEqual(resposta.json["expires_in"], 3600)
        fetch_one_mock.assert_called_once()
        verificar_senha_mock.assert_called_once()
        identidade = jwt.decode(
            resposta.json["access_token"],
            app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"],
        )
        self.assertEqual(identidade["sub"], "41")
        self.assertEqual(identidade["tipo_usuario"], "cliente")

    @patch("routes.aut.execute_transaction", return_value=[41, 0, 0, 0])
    @patch("routes.aut.fetch_one", return_value=None)
    def test_cadastro_insere_cliente_endereco_habilitacao_e_contato_emergencia(
        self, fetch_one, execute_transaction_mock
    ):
        resposta = self.client.post(
            "/auth/cadastro",
            json={
                "nome": "Ana Exemplo",
                "cpf": "123.456.789-01",
                "rg": "12.345.678-9",
                "data_nascimento": "1990-05-17",
                "telefone": "(11) 99999-0000",
                "nome_contato_emergencia": "Maria Exemplo",
                "telefone_contato_emergencia": "(11) 98888-0000",
                "email": "ANA@example.com",
                "senha": "SenhaSegura123",
                "endereco": {
                    "cep": "01000-000",
                    "logradouro": "Rua de Teste",
                    "numero": "15",
                    "complemento": "Apto 2",
                    "cidade": "Sao Paulo",
                    "uf": "sp",
                },
                "registro_habilitacao": {
                    "numero_registro": "12345678901",
                    "categoria": "ab",
                    "data_validade": "2030-05-17",
                },
            },
        )

        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(resposta.json["id_cliente"], 41)
        fetch_one.assert_called_once()
        queries = execute_transaction_mock.call_args.args[0]
        self.assertEqual(len(queries), 4)
        self.assertIn("senha_hash", queries[0][0])
        self.assertIn("nome_contato_emergencia", queries[0][0])
        self.assertEqual(queries[0][1][-2:], ("Maria Exemplo", "(11) 98888-0000"))
        self.assertEqual(queries[0][1][1:4], ("12345678901", "12.345.678-9", date(1990, 5, 17)))
        self.assertTrue(check_password_hash(queries[0][1][6], "SenhaSegura123"))
        self.assertIn("INSERT INTO endereco", queries[2][0])
        self.assertIn("INSERT INTO registro_habilitacao", queries[3][0])
        self.assertEqual(queries[2][1], ("01000-000", "Rua de Teste", "15", "Apto 2", "Sao Paulo", "SP"))

    @patch("routes.aut.execute_transaction")
    @patch("routes.aut.fetch_one", return_value=None)
    def test_cadastro_exige_endereco_e_habilitacao_normalizados(
        self, fetch_one, execute_transaction_mock
    ):
        resposta = self.client.post(
            "/auth/cadastro",
            json={
                "nome": "Ana Exemplo",
                "cpf": "12345678901",
                "rg": "123456789",
                "data_nascimento": "1990-05-17",
                "telefone": "11999990000",
                "email": "ana@example.com",
                "senha": "SenhaSegura123",
                "endereco": "Rua antiga, 15",
            },
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("endereco.cep", resposta.json["campos"])
        self.assertIn("registro_habilitacao.numero_registro", resposta.json["campos"])
        fetch_one.assert_not_called()
        execute_transaction_mock.assert_not_called()

    @patch("routes.aut.execute_transaction", return_value=[42, 0, 0, 0])
    @patch("routes.aut.fetch_one", return_value=None)
    def test_cadastro_aceita_contatos_de_emergencia_ausentes(
        self, fetch_one, execute_transaction_mock
    ):
        resposta = self.client.post(
            "/auth/cadastro",
            json={
                "nome": "Ana Exemplo",
                "cpf": "12345678901",
                "rg": "123456789",
                "data_nascimento": "1990-05-17",
                "telefone": "11999990000",
                "email": "ana@example.com",
                "senha": "SenhaSegura123",
                "endereco": {
                    "cep": "01000-000",
                    "logradouro": "Rua de Teste",
                    "numero": "15",
                    "cidade": "Sao Paulo",
                    "uf": "SP",
                },
                "registro_habilitacao": {
                    "numero_registro": "12345678901",
                    "categoria": "AB",
                    "data_validade": "2030-05-17",
                },
            },
        )

        self.assertEqual(resposta.status_code, 201)
        fetch_one.assert_called_once()
        cliente_insert = execute_transaction_mock.call_args.args[0][0]
        self.assertEqual(cliente_insert[1][-2:], (None, None))

    @patch("routes.clientes.fetch_all")
    def test_listagem_retorna_endereco_e_habilitacao_relacionados(self, fetch_all_mock):
        fetch_all_mock.return_value = [
            {
                "id_cliente": 41,
                "nome": "Ana Exemplo",
                "cpf": "12345678901",
                "rg": "12.345.678-9",
                "data_nascimento": date(1990, 5, 17),
                "telefone": "11999990000",
                "email": "ana@example.com",
                "nome_contato_emergencia": "Maria Exemplo",
                "telefone_contato_emergencia": "11988880000",
                "status": "ATIVO",
                "data_cadastro": None,
                "id_endereco": 3,
                "cep": "01000-000",
                "logradouro": "Rua de Teste",
                "numero": "15",
                "complemento": None,
                "cidade": "Sao Paulo",
                "uf": "SP",
                "id_habilitacao": 4,
                "numero_registro": "12345678901",
                "categoria": "AB",
                "data_validade": date(2030, 5, 17),
            }
        ]

        resposta = self.client.get(
            "/clientes",
            headers=self.headers_jwt,
        )

        self.assertEqual(resposta.status_code, 200)
        cliente = resposta.json[0]
        self.assertEqual(cliente["endereco"]["logradouro"], "Rua de Teste")
        self.assertEqual(cliente["registro_habilitacao"]["categoria"], "AB")
        self.assertEqual(cliente["nome_contato_emergencia"], "Maria Exemplo")
        self.assertEqual(cliente["telefone_contato_emergencia"], "11988880000")
        self.assertNotIn("senha_hash", cliente)

    @patch("routes.clientes.execute_transaction")
    @patch("routes.clientes.fetch_one", return_value={"id_cliente": 41})
    def test_atualizacao_grava_endereco_e_habilitacao_em_suas_tabelas(
        self, fetch_one_mock, execute_transaction_mock
    ):
        resposta = self.client.put(
            "/clientes/41",
            headers=self.headers_jwt,
            json={
                "endereco": {
                    "cep": "01000-000",
                    "logradouro": "Rua Nova",
                    "numero": "20",
                    "complemento": "",
                    "cidade": "Sao Paulo",
                    "uf": "SP",
                },
                "registro_habilitacao": {
                    "numero_registro": "12345678901",
                    "categoria": "A",
                    "data_validade": "2031-06-01",
                },
                "nome_contato_emergencia": "Maria Atualizada",
                "telefone_contato_emergencia": "(11) 97777-0000",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        fetch_one_mock.assert_called_once()
        queries = execute_transaction_mock.call_args.args[0]
        self.assertEqual(len(queries), 3)
        self.assertIn("nome_contato_emergencia = %s", queries[0][0])
        self.assertIn("telefone_contato_emergencia = %s", queries[0][0])
        self.assertIn("INSERT INTO endereco", queries[1][0])
        self.assertIn("ON DUPLICATE KEY UPDATE", queries[1][0])
        self.assertIn("INSERT INTO registro_habilitacao", queries[2][0])


class DatabaseTransactionTests(unittest.TestCase):
    def test_rolls_back_if_any_statement_fails(self):
        class Cursor:
            lastrowid = 41

            def __init__(self):
                self.calls = 0

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def execute(self, *_args):
                if len(_args) != 2:
                    raise AssertionError("execute must receive query and params")
                self.calls += 1
                if self.calls == 2:
                    raise RuntimeError("statement failed")

        class Connection:
            def __init__(self):
                self.fake_cursor = Cursor()
                self.committed = False
                self.rolled_back = False
                self.closed = False

            def cursor(self):
                return self.fake_cursor

            def commit(self):
                self.committed = True

            def rollback(self):
                self.rolled_back = True

            def close(self):
                self.closed = True

        connection = Connection()
        with patch("database.get_db_connection", return_value=connection):
            with self.assertRaisesRegex(RuntimeError, "statement failed"):
                execute_transaction([("INSERT", ()), ("INSERT", ())])

        self.assertFalse(connection.committed)
        self.assertTrue(connection.rolled_back)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
