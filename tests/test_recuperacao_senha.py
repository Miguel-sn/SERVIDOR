import unittest
import os
from unittest.mock import patch

from werkzeug.security import check_password_hash

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-that-is-32bytes!")
os.environ.setdefault("FLASK_SECRET_KEY", "test-flask-secret-key-that-is-32bytes!")
os.environ.setdefault("APP_ENV", "test")

from app import app
from routes.aut import (
    _MENSAGEM_RECUPERACAO,
    _hash_token_recuperacao,
    _solicitacoes_recuperacao_por_ip,
)


class RecuperacaoSenhaApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.email = "ana@example.com"
        self.token = "012345"
        with app.app_context():
            self.token_hash = _hash_token_recuperacao(self.token)
        self.usuario_cliente = {
            "id": 41,
            "email": self.email,
            "status": "ATIVO",
        }
        _solicitacoes_recuperacao_por_ip.clear()

    def tearDown(self):
        _solicitacoes_recuperacao_por_ip.clear()

    @patch(
        "routes.aut._configuracao_recuperacao",
        return_value={
            "mail_server": "smtp.example.test",
            "mail_port": 587,
            "mail_username": "sender@example.test",
            "mail_password": "not-a-real-password",
            "mail_sender": "sender@example.test",
            "mail_use_tls": True,
            "mail_use_ssl": False,
        },
    )
    @patch("routes.aut._enviar_email_recuperacao")
    @patch("routes.aut.execute_transaction", return_value=[0, 15])
    @patch("routes.aut.fetch_one")
    def test_request_persists_only_random_token_hash_and_emails_token(
        self,
        fetch_one_mock,
        execute_transaction_mock,
        send_email_mock,
        _config_mock,
    ):
        fetch_one_mock.side_effect = [
            self.usuario_cliente,
            {"total": 0},
        ]

        with patch("routes.aut.secrets.randbelow", return_value=42):
            response = self.client.post(
                "/auth/recuperacao",
                json={"email": "ANA@example.com"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["message"], _MENSAGEM_RECUPERACAO)
        self.assertIn(
            "status_cliente AS status",
            fetch_one_mock.call_args_list[0].args[0],
        )
        queries = execute_transaction_mock.call_args.args[0]
        self.assertIn("UPDATE token_recuperacao", queries[0][0])
        self.assertIn("id_cliente = %s", queries[0][0])
        self.assertIn("INSERT INTO token_recuperacao", queries[1][0])
        self.assertIn("DATE_ADD(CURRENT_TIMESTAMP, INTERVAL 15 MINUTE)", queries[1][0])

        email, token, configuracao = send_email_mock.call_args.args
        self.assertEqual(email, self.email)
        self.assertEqual(token, "000042")
        self.assertRegex(token, r"^[0-9]{6}$")
        with app.app_context():
            token_hash = _hash_token_recuperacao(token)
        self.assertEqual(queries[1][1], (41, None, token_hash))
        self.assertNotIn(token, queries[1][0])
        self.assertNotIn(token, repr(queries[1][1]))
        self.assertIsNotNone(configuracao)
        _config_mock.assert_called_once()

    @patch(
        "routes.aut._configuracao_recuperacao",
        return_value={
            "mail_server": "smtp.example.test",
            "mail_port": 587,
            "mail_username": "sender@example.test",
            "mail_password": "not-a-real-password",
            "mail_sender": "sender@example.test",
            "mail_use_tls": True,
            "mail_use_ssl": False,
        },
    )
    @patch("routes.aut._enviar_email_recuperacao")
    @patch("routes.aut.execute_transaction", return_value=[0, 15])
    @patch("routes.aut.fetch_one")
    def test_request_uses_employee_status_column(
        self,
        fetch_one_mock,
        execute_transaction_mock,
        send_email_mock,
        _config_mock,
    ):
        fetch_one_mock.side_effect = [
            None,
            {
                "id": 77,
                "email": "admin@example.com",
                "status": "ATIVO",
            },
            {"total": 0},
        ]

        with patch("routes.aut.secrets.randbelow", return_value=42):
            response = self.client.post(
                "/auth/recuperacao",
                json={"email": "admin@example.com"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "status_funcionario AS status",
            fetch_one_mock.call_args_list[1].args[0],
        )
        self.assertIn(
            "id_funcionario = %s",
            execute_transaction_mock.call_args.args[0][0][0],
        )
        self.assertEqual(send_email_mock.call_args.args[1], "000042")

    @patch.dict(
        "os.environ",
        {
            "MAIL_SERVER": "smtp.example.test",
            "MAIL_PORT": "465",
            "MAIL_USERNAME": "sender@example.test",
            "MAIL_PASSWORD": "fake-secret-for-test",
            "MAIL_DEFAULT_SENDER": "sender@example.test",
            "MAIL_USE_TLS": "false",
            "MAIL_USE_SSL": "true",
        },
        clear=False,
    )
    def test_mail_configuration_uses_existing_mail_environment_variables(self):
        from routes.aut import _configuracao_recuperacao

        config = _configuracao_recuperacao()

        self.assertEqual(config["mail_server"], "smtp.example.test")
        self.assertEqual(config["mail_port"], 465)
        self.assertTrue(config["mail_use_ssl"])
        self.assertFalse(config["mail_use_tls"])

    @patch.dict(
        "os.environ",
        {
            "MAIL_SERVER": "smtp.example.test",
            "MAIL_PORT": "587",
            "MAIL_USERNAME": "sender@example.test",
            "MAIL_PASSWORD": "fake-secret-for-test",
            "MAIL_DEFAULT_SENDER": "sender@example.test",
            "MAIL_USE_TLS": "true",
            "MAIL_USE_SSL": "false",
        },
        clear=False,
    )
    @patch("routes.aut.smtplib.SMTP")
    def test_smtp_email_is_composed_and_tls_login_are_simulated(
        self, smtp_mock
    ):
        from routes.aut import _configuracao_recuperacao, _enviar_email_recuperacao

        smtp_context = smtp_mock.return_value.__enter__.return_value
        token = "012345"
        _enviar_email_recuperacao(
            self.email,
            token,
            _configuracao_recuperacao(),
        )

        smtp_mock.assert_called_once_with("smtp.example.test", 587, timeout=10)
        smtp_context.starttls.assert_called_once()
        smtp_context.login.assert_called_once_with(
            "sender@example.test",
            "fake-secret-for-test",
        )
        message = smtp_context.send_message.call_args.args[0]
        self.assertEqual(message["To"], self.email)
        self.assertIn("código de 6 dígitos", message.get_content())
        self.assertIn(token, message.get_content())

    @patch("routes.aut._configuracao_recuperacao", return_value={"configured": True})
    @patch("routes.aut._enviar_email_recuperacao")
    @patch("routes.aut.fetch_one", side_effect=[None, None])
    def test_unknown_email_gets_same_generic_response_without_sending_email(
        self, _fetch_one_mock, send_email_mock, _config_mock
    ):
        response = self.client.post(
            "/auth/recuperacao",
            json={"email": "nao-existe@example.com"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["message"], _MENSAGEM_RECUPERACAO)
        self.assertEqual(_fetch_one_mock.call_count, 2)
        send_email_mock.assert_not_called()
        _config_mock.assert_called_once()

    @patch("routes.aut._configuracao_recuperacao", return_value={"configured": True})
    @patch("routes.aut._enviar_email_recuperacao")
    @patch("routes.aut.fetch_one", side_effect=[None, None] * 5)
    def test_request_ip_rate_limit_keeps_the_generic_response(
        self, fetch_one_mock, _send_email_mock, _config_mock
    ):
        responses = [
            self.client.post(
                "/auth/recuperacao",
                json={"email": "nao-existe@example.com"},
            )
            for _ in range(6)
        ]

        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertTrue(
            all(response.json["message"] == _MENSAGEM_RECUPERACAO for response in responses)
        )
        self.assertEqual(fetch_one_mock.call_count, 10)
        self.assertEqual(_send_email_mock.call_count, 0)
        self.assertEqual(_config_mock.call_count, 6)

    @patch("routes.aut._configuracao_recuperacao", return_value={"configured": True})
    @patch("routes.aut._enviar_email_recuperacao")
    @patch("routes.aut.execute_transaction")
    @patch("routes.aut.fetch_one", side_effect=[{"id": 41, "status": "ATIVO"}, {"total": 3}])
    def test_account_rate_limit_does_not_create_or_send_more_tokens(
        self,
        _fetch_one_mock,
        transaction_mock,
        send_email_mock,
        _config_mock,
    ):
        response = self.client.post(
            "/auth/recuperacao",
            json={"email": self.email},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["message"], _MENSAGEM_RECUPERACAO)
        self.assertEqual(_fetch_one_mock.call_count, 2)
        transaction_mock.assert_not_called()
        send_email_mock.assert_not_called()
        _config_mock.assert_called_once()

    @patch("routes.aut._configuracao_recuperacao", return_value={"configured": True})
    @patch("routes.aut._enviar_email_recuperacao", side_effect=RuntimeError("SMTP error"))
    @patch("routes.aut.execute_query")
    @patch("routes.aut.execute_transaction", return_value=[0, 15])
    @patch("routes.aut.fetch_one", side_effect=[{"id": 41, "status": "ATIVO"}, {"total": 0}])
    def test_smtp_failure_invalidates_token_without_exposing_internal_error(
        self,
        _fetch_one_mock,
        _transaction_mock,
        execute_query_mock,
        _send_email_mock,
        _config_mock,
    ):
        response = self.client.post(
            "/auth/recuperacao",
            json={"email": self.email},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["message"], _MENSAGEM_RECUPERACAO)
        self.assertEqual(_fetch_one_mock.call_count, 2)
        _transaction_mock.assert_called_once()
        _send_email_mock.assert_called_once()
        _config_mock.assert_called_once()
        self.assertIn("token_hash = %s", execute_query_mock.call_args.args[0])

    @patch("routes.aut.fetch_one")
    def test_validation_accepts_active_unexpired_customer_token(self, fetch_one_mock):
        fetch_one_mock.side_effect = [
            {"id_token": 15, "id_cliente": 41, "id_funcionario": None},
            {"id": 41},
        ]

        response = self.client.post(
            "/auth/recuperacao/validar",
            json={"token": self.token},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["message"], "Token validado com sucesso")
        self.assertEqual(fetch_one_mock.call_args_list[0].args[1], (self.token_hash,))
        self.assertIn(
            "status_cliente = 'ATIVO'",
            fetch_one_mock.call_args_list[1].args[0],
        )

    @patch("routes.aut.fetch_one", return_value=None)
    def test_validation_rejects_unknown_or_expired_token(self, fetch_one_mock):
        response = self.client.post(
            "/auth/recuperacao/validar",
            json={"token": self.token},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"], "Token inválido ou expirado")
        fetch_one_mock.assert_called_once()
        self.assertIn("utilizado_em IS NULL", fetch_one_mock.call_args.args[0])
        self.assertIn("expira_em > CURRENT_TIMESTAMP", fetch_one_mock.call_args.args[0])

    @patch("routes.aut.fetch_one", return_value=None)
    def test_token_validation_ip_limit_stops_repeated_database_checks(
        self, fetch_one_mock
    ):
        responses = [
            self.client.post(
                "/auth/recuperacao/validar",
                json={"token": self.token},
            )
            for _ in range(21)
        ]

        self.assertTrue(all(response.status_code == 400 for response in responses[:5]))
        self.assertEqual(responses[-1].status_code, 429)
        self.assertEqual(fetch_one_mock.call_count, 5)

    @patch("routes.aut.fetch_one")
    def test_confirmation_hashes_new_password_and_updates_customer_atomically(
        self, fetch_one_mock
    ):
        fetch_one_mock.side_effect = [
            {"id_token": 15, "id_cliente": 41, "id_funcionario": None},
            {"id": 41},
        ]
        with patch("routes.aut.execute_transaction", return_value=[0, 0]) as transaction:
            response = self.client.post(
                "/auth/recuperacao/confirmar",
                json={"token": self.token, "nova_senha": "SenhaNova123"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["message"], "Senha atualizada com sucesso")
        queries = transaction.call_args.args[0]
        self.assertIn("utilizado_em IS NULL", queries[0][0])
        self.assertIn("UPDATE cliente SET senha_hash", queries[1][0])
        self.assertIn("status_cliente = 'ATIVO'", queries[1][0])
        self.assertEqual(queries[0][1], (15,))
        self.assertEqual(queries[1][1][1], 41)
        self.assertTrue(check_password_hash(queries[1][1][0], "SenhaNova123"))
        self.assertFalse(check_password_hash(queries[1][1][0], "SenhaAntiga123"))
        self.assertEqual(
            transaction.call_args.kwargs["expected_rowcounts"],
            {0: 1, 1: 1},
        )
        stored_hash = queries[1][1][0]

        with (
            patch(
                "routes.aut.fetch_one",
                return_value={
                    "id": 41,
                    "nome": "Ana",
                    "email": self.email,
                    "senha_hash": stored_hash,
                    "status": "ATIVO",
                },
            ),
            patch("routes.aut.criar_token_acesso", return_value="jwt-test"),
        ):
            login_nova_senha = self.client.post(
                "/auth/login",
                json={"email": self.email, "senha": "SenhaNova123"},
            )
            login_senha_antiga = self.client.post(
                "/auth/login",
                json={"email": self.email, "senha": "SenhaAntiga123"},
            )

        self.assertEqual(login_nova_senha.status_code, 200)
        self.assertEqual(login_senha_antiga.status_code, 401)

    @patch("routes.aut.fetch_one")
    def test_confirmation_updates_the_function_account_not_a_customer(
        self, fetch_one_mock
    ):
        fetch_one_mock.side_effect = [
            {"id_token": 22, "id_cliente": None, "id_funcionario": 77},
            {"id": 77},
        ]
        with patch("routes.aut.execute_transaction", return_value=[0, 0]) as transaction:
            response = self.client.post(
                "/auth/recuperacao/confirmar",
                json={"token": self.token, "nova_senha": "SenhaNova123"},
            )

        self.assertEqual(response.status_code, 200)
        update_password = transaction.call_args.args[0][1][0]
        self.assertIn("UPDATE funcionario SET senha_hash", update_password)
        self.assertIn("status_funcionario = 'ATIVO'", update_password)
        self.assertEqual(transaction.call_args.args[0][1][1][1], 77)
        stored_hash = transaction.call_args.args[0][1][1][0]
        self.assertTrue(check_password_hash(stored_hash, "SenhaNova123"))
        self.assertFalse(check_password_hash(stored_hash, "SenhaAntiga123"))

        email_funcionario = "admin@example.com"
        with (
            patch(
                "routes.aut.fetch_one",
                side_effect=[
                    None,
                    {
                        "id": 77,
                        "nome": "Admin",
                        "email": email_funcionario,
                        "senha_hash": stored_hash,
                        "status": "ATIVO",
                        "perfil": "ADMINISTRADOR",
                    },
                    None,
                    {
                        "id": 77,
                        "nome": "Admin",
                        "email": email_funcionario,
                        "senha_hash": stored_hash,
                        "status": "ATIVO",
                        "perfil": "ADMINISTRADOR",
                    },
                ],
            ),
            patch("routes.aut.criar_token_acesso", return_value="jwt-admin-test"),
        ):
            login_nova_senha = self.client.post(
                "/auth/login",
                json={"email": email_funcionario, "senha": "SenhaNova123"},
            )
            login_senha_antiga = self.client.post(
                "/auth/login",
                json={"email": email_funcionario, "senha": "SenhaAntiga123"},
            )

        self.assertEqual(login_nova_senha.status_code, 200)
        self.assertEqual(login_nova_senha.json["tipo_usuario"], "funcionario")
        self.assertEqual(login_senha_antiga.status_code, 401)

    @patch("routes.aut.fetch_one")
    def test_used_token_cannot_be_reused(self, fetch_one_mock):
        fetch_one_mock.side_effect = [
            {"id_token": 15, "id_cliente": 41, "id_funcionario": None},
            {"id": 41},
            None,
        ]
        with patch("routes.aut.execute_transaction", return_value=[0, 0]) as transaction:
            primeira = self.client.post(
                "/auth/recuperacao/confirmar",
                json={"token": self.token, "nova_senha": "SenhaNova123"},
            )
            segunda = self.client.post(
                "/auth/recuperacao/confirmar",
                json={"token": self.token, "nova_senha": "OutraSenha456"},
            )

        self.assertEqual(primeira.status_code, 200)
        self.assertEqual(segunda.status_code, 400)
        self.assertEqual(transaction.call_count, 1)

    @patch("routes.aut.fetch_one")
    def test_missing_or_malformed_token_is_rejected_without_database_access(
        self, fetch_one_mock
    ):
        for body in (
            {"nova_senha": "SenhaNova123"},
            {"token": "12345", "nova_senha": "SenhaNova123"},
            {"token": "12a456", "nova_senha": "SenhaNova123"},
            {"token": self.token, "nova_senha": "curta"},
        ):
            response = self.client.post("/auth/recuperacao/confirmar", json=body)
            self.assertEqual(response.status_code, 400)
        fetch_one_mock.assert_not_called()

if __name__ == "__main__":
    unittest.main()
