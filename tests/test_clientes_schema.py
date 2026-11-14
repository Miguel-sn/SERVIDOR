import unittest
from datetime import date
from unittest.mock import patch

import jwt
from werkzeug.security import check_password_hash, generate_password_hash

from app import app
from database import TransactionConflictError, execute_transaction
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
        cabecalhos_permitidos = resposta.headers["Access-Control-Allow-Headers"].lower()
        self.assertIn("content-type", cabecalhos_permitidos)
        self.assertIn("authorization", cabecalhos_permitidos)

    def test_cors_nao_permite_origem_remota(self):
        resposta = self.client.options(
            "/auth/cadastro",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertNotIn("Access-Control-Allow-Origin", resposta.headers)

    @patch(
        "routes.aut.fetch_one",
        return_value={
            "id_cliente": 41,
            "nome": "Ana Exemplo",
            "cpf": "12345678901",
            "numero_registro": "12345678901",
            "telefone": "11999990000",
            "cidade": "Sao Paulo",
        },
    )
    def test_perfil_cliente_usa_colunas_existentes_no_schema(self, fetch_one_mock):
        with app.app_context():
            token = criar_token_acesso(41, "cliente")

        resposta = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["nome"], "Ana Exemplo")
        consulta = fetch_one_mock.call_args.args[0]
        self.assertIn("c.nome_cliente AS nome", consulta)
        self.assertIn("c.status_cliente = 'ATIVO'", consulta)
        self.assertNotIn("c.nome,", consulta)
        self.assertNotIn("c.status =", consulta)

    def test_todas_as_rotas_clientes_exigem_token_jwt(self):
        respostas = (
            self.client.get("/clientes"),
            self.client.get("/clientes/41"),
            self.client.put("/clientes/41", json={"nome": "Ana"}),
            self.client.delete("/clientes/41"),
        )

        self.assertTrue(all(resposta.status_code == 401 for resposta in respostas))

    @patch("routes.clientes.fetch_all", return_value=[])
    def test_rota_protegida_aceita_token_jwt_valido(self, fetch_all_mock):
        resposta = self.client.get("/clientes", headers=self.headers_jwt)

        self.assertEqual(resposta.status_code, 200)
        fetch_all_mock.assert_called_once()

    @patch("routes.aut._verificar_senha", return_value=(True, False))
    @patch(
        "routes.aut.fetch_one",
        return_value={
            "id": 41,
            "nome": "Ana Exemplo",
            "email": "ana@example.com",
            "senha_hash": "hash-de-teste",
            "status": "ATIVO",
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

    @patch("routes.aut._verificar_senha", return_value=(True, False))
    @patch(
        "routes.aut.fetch_one",
        side_effect=[
            None,
            {
                "id": 7,
                "nome": "Funcionario Exemplo",
                "email": "funcionario@example.com",
                "senha_hash": "hash-de-teste",
                "status": "ATIVO",
                "perfil": "ADMINISTRADOR",
            },
        ],
    )
    def test_login_funcionario_usa_colunas_do_schema_e_retorna_perfil(
        self, fetch_one_mock, verificar_senha_mock
    ):
        resposta = self.client.post(
            "/auth/login",
            json={"email": "funcionario@example.com", "senha": "SenhaSegura123"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["tipo_usuario"], "funcionario")
        self.assertEqual(resposta.json["usuario"]["perfil"], "ADMINISTRADOR")
        self.assertEqual(fetch_one_mock.call_count, 2)
        consulta_funcionario = fetch_one_mock.call_args_list[1].args[0]
        self.assertIn(
            "nome_funcionario AS nome, email, senha_hash, "
            "status_funcionario AS status, perfil",
            consulta_funcionario,
        )
        verificar_senha_mock.assert_called_once()

    def test_login_verifica_hash_para_cliente_funcionario_e_administrador(self):
        senha = "SenhaSegura123"
        casos = (
            ("cliente", 41, "cliente", None),
            ("funcionario", 7, "funcionario", "FUNCIONARIO"),
            ("administrador", 8, "funcionario", "ADMINISTRADOR"),
        )

        for identificador, usuario_id, tipo_jwt, perfil in casos:
            with self.subTest(perfil=identificador):
                usuario = {
                    "id": usuario_id,
                    "nome": "Usuario de Teste",
                    "email": f"{identificador}@example.com",
                    "senha_hash": generate_password_hash(senha),
                    "status": "ATIVO",
                }
                if perfil is not None:
                    usuario["perfil"] = perfil

                with patch("routes.aut.fetch_one") as fetch_one_mock:
                    fetch_one_mock.side_effect = (
                        [usuario] if perfil is None else [None, usuario]
                    )
                    resposta = self.client.post(
                        "/auth/login",
                        json={"email": usuario["email"], "senha": senha},
                    )

                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(resposta.json["tipo_usuario"], tipo_jwt)
                if perfil is not None:
                    self.assertEqual(resposta.json["usuario"]["perfil"], perfil)
                identidade = jwt.decode(
                    resposta.json["access_token"],
                    app.config["JWT_SECRET_KEY"],
                    algorithms=["HS256"],
                )
                self.assertEqual(identidade["sub"], str(usuario_id))
                self.assertEqual(identidade["tipo_usuario"], tipo_jwt)

    @patch("routes.aut.execute_transaction", return_value=[41, 0, 0, 0])
    @patch("routes.aut.fetch_one", return_value=None)
    def test_cadastro_insere_cliente_endereco_e_habilitacao_em_transacao(
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
        self.assertEqual(len(queries), 3)
        self.assertIn("senha_hash", queries[0][0])
        self.assertIn("nome, cpf, rg, data_nascimento", queries[0][0])
        self.assertNotIn("nome_contato_emergencia", queries[0][0])
        self.assertEqual(queries[0][1][1:4], ("12345678901", "12.345.678-9", date(1990, 5, 17)))
        self.assertTrue(check_password_hash(queries[0][1][6], "SenhaSegura123"))
        self.assertIn("INSERT INTO endereco", queries[1][0])
        self.assertIn("FROM cliente WHERE email = %s", queries[1][0])
        self.assertEqual(
            queries[1][1],
            ("01000-000", "Rua de Teste", "15", "Apto 2", "Sao Paulo", "SP", "ana@example.com"),
        )
        self.assertIn("INSERT INTO registro_habilitacao", queries[2][0])
        self.assertEqual(
            queries[2][1],
            ("12345678901", "AB", date(2030, 5, 17), "ana@example.com"),
        )

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
    def test_cadastro_persiste_apenas_campos_presentes_no_schema(
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
        queries = execute_transaction_mock.call_args.args[0]
        self.assertEqual(len(queries), 3)
        self.assertNotIn("nome_contato_emergencia", queries[0][0])

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
        self.assertNotIn("nome_contato_emergencia", cliente)
        self.assertNotIn("telefone_contato_emergencia", cliente)
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
            },
        )

        self.assertEqual(resposta.status_code, 200)
        fetch_one_mock.assert_called_once()
        queries = execute_transaction_mock.call_args.args[0]
        self.assertEqual(len(queries), 2)
        self.assertIn("INSERT INTO endereco", queries[0][0])
        self.assertIn("ON DUPLICATE KEY UPDATE", queries[0][0])
        self.assertIn("INSERT INTO registro_habilitacao", queries[1][0])


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

    @patch("database.get_db_connection")
    def test_rolls_back_if_expected_rowcount_does_not_match(self, connection_mock):
        class Cursor:
            rowcount = 0

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def execute(self, query, params):
                self.last_query = query
                self.last_params = params

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
        connection_mock.return_value = connection

        with self.assertRaises(TransactionConflictError):
            execute_transaction(
                [("UPDATE motocicleta SET status = %s", ("RESERVADA",))],
                expected_rowcounts={0: 1},
            )

        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
