import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

from app import app
from routes.jwt_auth import criar_token_acesso


class LocacoesSchemaApiTests(unittest.TestCase):
    def setUp(self):
        self.jwt_secret_anterior = app.config.get("JWT_SECRET_KEY")
        app.config["JWT_SECRET_KEY"] = "test-jwt-secret-key-that-is-32bytes!"
        with app.app_context():
            token = criar_token_acesso(7, "funcionario")
        self.headers_jwt = {"Authorization": f"Bearer {token}"}
        self.client = app.test_client()

    def tearDown(self):
        if self.jwt_secret_anterior is None:
            app.config.pop("JWT_SECRET_KEY", None)
        else:
            app.config["JWT_SECRET_KEY"] = self.jwt_secret_anterior

    @patch(
        "routes.locacoes.fetch_all",
        return_value=[
            {
                "id_locacao": 15,
                "codigo_contrato": "LOC-20261114-ABC123",
                "id_cliente": 41,
                "id_motocicleta": 21,
                "data_hora_inicio": datetime(2026, 12, 1, 9),
                "data_hora_devolucao_prevista": datetime(2026, 12, 3, 9),
                "valor_base_locacao": Decimal("200.00"),
                "quantidade_diarias": 2,
                "status_locacao": "AGENDADA",
            }
        ],
    )
    def test_lista_locacoes_com_colunas_existentes_no_schema(self, fetch_all_mock):
        resposta = self.client.get("/locacoes", headers=self.headers_jwt)

        self.assertEqual(resposta.status_code, 200)
        locacao = resposta.json["locacoes"][0]
        self.assertEqual(locacao["codigo_contrato"], "LOC-20261114-ABC123")
        self.assertEqual(locacao["status_locacao"], "AGENDADA")
        consulta = fetch_all_mock.call_args.args[0]
        self.assertIn("l.codigo_contrato", consulta)
        self.assertIn("l.valor_base_locacao", consulta)
        self.assertNotIn("numero_locacao", consulta)
        self.assertNotIn("id_reserva", consulta)

    @patch(
        "routes.locacoes._buscar",
        return_value={"id_locacao": 15, "status": "AGENDADA"},
    )
    @patch("routes.locacoes.execute_transaction", return_value=[0, 15])
    @patch(
        "routes.locacoes.fetch_one",
        return_value={
            "id_reserva": 12,
            "data_hora_retirada_prevista": datetime(2026, 12, 1, 9),
            "data_hora_devolucao_prevista": datetime(2026, 12, 3, 9),
            "valor_diaria": Decimal("100.00"),
            "quantidade_periodos": 2,
            "valor_total_previsto": Decimal("200.00"),
            "status_reserva": "APROVADA",
            "status_cliente": "ATIVO",
            "status_modelo": "ATIVO",
            "status_motocicleta": "DISPONIVEL",
            "valor_franquia": Decimal("3000.00"),
        },
    )
    def test_cria_locacao_com_colunas_e_relacoes_do_schema(
        self, fetch_one_mock, execute_transaction_mock, buscar_mock
    ):
        resposta = self.client.post(
            "/locacoes",
            headers=self.headers_jwt,
            json={"id_reserva": 12, "id_motocicleta": 21},
        )

        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(resposta.json["locacao"]["status"], "AGENDADA")
        queries = execute_transaction_mock.call_args.args[0]
        sql, parametros = queries[1]
        self.assertIn("UPDATE motocicleta SET status = 'RESERVADA'", queries[0][0])
        self.assertIn("numero_locacao", sql)
        self.assertIn("id_reserva", sql)
        self.assertIn("id_funcionario", sql)
        self.assertIn("valor_franquia_aplicada", sql)
        self.assertNotIn("codigo_contrato", sql)
        self.assertNotIn("id_cliente,", sql)
        self.assertEqual(parametros[1:4], (12, 21, 7))
        self.assertEqual(
            execute_transaction_mock.call_args.kwargs["expected_rowcounts"],
            {0: 1},
        )
        fetch_one_mock.assert_called_once()
        buscar_mock.assert_called_once_with(15)

    @patch(
        "routes.locacoes._buscar",
        side_effect=[
            {
                "id_locacao": 15,
                "id_motocicleta": 21,
                "status": "AGENDADA",
            },
            {"id_locacao": 15, "status": "EM_ANDAMENTO"},
        ],
    )
    @patch("routes.locacoes.execute_transaction")
    def test_iniciar_locacao_atualiza_moto_e_locacao_na_mesma_transacao(
        self, execute_transaction_mock, buscar_mock
    ):
        resposta = self.client.put(
            "/locacoes/15/status",
            headers=self.headers_jwt,
            json={"status": "EM_ANDAMENTO"},
        )

        self.assertEqual(resposta.status_code, 200)
        queries = execute_transaction_mock.call_args.args[0]
        self.assertEqual(queries[0][1], ("ALUGADA", 21, "RESERVADA"))
        self.assertEqual(queries[1][1], ("EM_ANDAMENTO", 15, "AGENDADA"))
        self.assertEqual(
            execute_transaction_mock.call_args.kwargs["expected_rowcounts"],
            {0: 1, 1: 1},
        )
        self.assertEqual(buscar_mock.call_count, 2)

    def test_cliente_nao_pode_atribuir_moto_fisica_a_locacao(self):
        with app.app_context():
            token = criar_token_acesso(41, "cliente")

        resposta = self.client.post(
            "/locacoes",
            headers={"Authorization": f"Bearer {token}"},
            json={"id_reserva": 12, "id_motocicleta": 21},
        )

        self.assertEqual(resposta.status_code, 403)


if __name__ == "__main__":
    unittest.main()
