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
