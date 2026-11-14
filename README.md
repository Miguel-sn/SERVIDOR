# Backend LocaJá

Esta é a única fonte oficial do backend Flask. O frontend Flutter está no
repositório separado `aplicacao_loca_ja/frontend`.

## Configuração local

```powershell
Copy-Item .env.example .env
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Preencha `.env` com valores locais reais. O arquivo não deve ser versionado.
O backend falha explicitamente ao abrir uma conexão se as variáveis de banco ou
as chaves JWT não estiverem configuradas.

## Execução

Desenvolvimento:

```powershell
python app.py
```

Produção:

```powershell
gunicorn -c gunicorn.conf.py app:app
```

O Railway fornece `PORT`. O processo usa pool PyMySQL, timeouts explícitos e
logs em stdout/stderr. O banco nunca é acessado pelo frontend.

## Variáveis obrigatórias

`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`,
`JWT_SECRET_KEY` e `FLASK_SECRET_KEY`.

Em produção, `CORS_ORIGINS` também é obrigatório e deve conter somente as
origens HTTPS oficiais. `APP_ENV=production` ativa a validação fail-closed.

Para Firebase, configure `FIREBASE_CREDENCIAIS` e
`FIREBASE_STORAGE_BUCKET` como variáveis de ambiente. Não copie arquivos JSON
de credenciais para o projeto.

## Health check

`GET /api/status` executa `SELECT 1` no MySQL. Retorna `200` somente quando a
API e o banco estão disponíveis; caso contrário retorna `503`.

## Testes e auditoria

```powershell
python -m unittest discover -s tests -v
python -m pip install pip-audit
pip-audit
```

Uploads exigem JWT, possuem limite de tamanho e devem usar Firebase Storage em
produção. O armazenamento local é reservado aos testes.

O rate limit padrão é local ao processo. Em múltiplos workers, mantenha também
um rate limit compartilhado no gateway/API platform ou substitua o armazenamento
em memória por Redis antes de escalar horizontalmente.
