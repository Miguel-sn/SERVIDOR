# Backend

API Flask do LocaJá. Execute os comandos a partir desta pasta:

```powershell
Copy-Item .env.example .env
python -m pip install -r requirements.txt
python app.py
```

O arquivo `.env` contém somente configuração local e não deve ser publicado.
O banco de dados é mantido no repositório independente em
`../database/`; o backend é o único componente que acessa suas credenciais.

O Firestore é inicializado quando `FIREBASE_CREDENCIAIS` contém o JSON das
credenciais do Firebase Admin. Essa variável é opcional: sem ela, a API
continua iniciando normalmente e `app.extensions["firebase_db"]` fica como
`None`. No Railway, configure o JSON completo diretamente nessa variável e
nunca publique arquivos de credenciais no repositório.

A API disponibiliza `GET /api/status`, que retorna `{"status": "ok"}` com
código 200 para testes de conectividade. O CORS aceita os métodos
`GET`, `POST`, `PUT`, `DELETE` e `OPTIONS`, os headers `Content-Type` e
`Authorization`, subdomínios `*.web.app` e `*.firebaseapp.com`, além de
origens locais em `localhost`.
