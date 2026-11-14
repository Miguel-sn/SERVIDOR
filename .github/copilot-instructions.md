\# Instruções do GitHub Copilot — Projeto Loca Já



\## 1. Contexto do projeto



O Loca Já é um sistema de aluguel de motocicletas.



Tecnologias utilizadas:

\- Backend: Python com Flask.

\- Aplicativo: Flutter.

\- Banco de dados: MySQL.

\- Autenticação: JWT.

\- Comunicação entre Flutter e Flask: API REST com JSON.

\- Recuperação de senha: envio de e-mail.

\- Integrações adicionais: Firebase, quando utilizadas no código.



O objetivo é manter um sistema organizado, seguro, escalável e de fácil manutenção.



\## 2. Arquitetura do backend



O backend utiliza uma estrutura modular, com diferentes arquivos Python e Blueprints do Flask.



Não transformar o projeto em um único arquivo app.py.



Antes de criar ou modificar funcionalidades:

1\. Inspecionar a estrutura existente.

2\. Identificar os arquivos e Blueprints envolvidos.

3\. Verificar como as rotas existentes funcionam.

4\. Reutilizar funções e configurações já existentes.

5\. Evitar duplicação de código.



Preservar a arquitetura atual do projeto.



\## 3. Regras de negócio



\### Reservas

\- O cliente escolhe o modelo da motocicleta, não uma motocicleta física específica.

\- A motocicleta física será atribuída posteriormente pela equipe da locadora.

\- A reserva registra o modelo escolhido e o período pretendido.

\- A reserva deve respeitar a disponibilidade do modelo.

\- A reserva depende da confirmação do pagamento, conforme as regras implementadas.

\- O aluguel presencial na sede não exige reserva antecipada.



\### Frota

\- A administração deve controlar a quantidade de motocicletas por modelo.

\- Cada motocicleta física possui seus próprios dados de identificação.

\- Cada motocicleta possui uma franquia associada individualmente.



\### Planos

O sistema considera:

\- Diária.

\- Semanal.

\- Mensal.



\### Caução e seguro

\- A locadora trabalha com seguro total nas motocicletas.

\- A caução deve considerar a franquia da motocicleta.

\- Não confundir valor da franquia com valor da cobertura do seguro.



\### Responsabilidades

\- O cliente é responsável pelas multas ocorridas durante o período de utilização da motocicleta.



\## 4. Banco de dados



O banco de dados do projeto chama-se `loca\_ja`.



As entidades previstas incluem:



\- modelo\_motocicleta

\- motocicleta

\- franquia

\- cliente

\- funcionario

\- administrador

\- reserva

\- locacao

\- pagamento

\- caucao

\- devolucao

\- sinistro

\- pendencia\_financeira

\- manutencao

\- multa

\- log\_auditoria



Respeitar os relacionamentos e as restrições definidos no banco existente.



Não alterar tabelas, colunas, chaves estrangeiras ou regras de negócio sem explicar previamente a necessidade e os impactos.



\## 5. Autenticação e segurança



O sistema possui diferentes tipos de usuários:

\- Cliente.

\- Funcionário.

\- Administrador.



O login deve identificar o tipo de usuário e respeitar seu perfil de acesso.



Regras:

\- Utilizar hash seguro para armazenar senhas.

\- Nunca armazenar senhas em texto puro.

\- Utilizar JWT conforme a configuração existente.

\- Não expor chaves secretas, senhas ou credenciais.

\- Respeitar permissões de cada perfil.

\- Validar os dados recebidos pelo backend.



\## 6. Recuperação de senha



O projeto possui funcionalidade de recuperação de senha por e-mail.



Ao modificar essa funcionalidade:

\- Verificar as rotas existentes antes de criar novas.

\- Validar o endereço de e-mail.

\- Controlar a validade dos códigos de recuperação.

\- Limitar tentativas de validação.

\- Nunca expor códigos ou credenciais em respostas públicas ou logs.

\- Utilizar variáveis de ambiente para configurações sensíveis.



\## 7. Documentos e imagens



O sistema precisa trabalhar com documentos e imagens enviados pelos clientes.



A validação automática de documentos e imagens de pessoas é uma funcionalidade a desenvolver ou aprimorar.



Não considerar um documento válido apenas porque o Flutter conseguiu enviá-lo.



As validações devem ocorrer no backend, com atenção à segurança, integridade dos arquivos e proteção dos dados pessoais.



\## 8. Comunicação Flutter e Flask



A API deve utilizar JSON nas requisições e respostas quando apropriado.



Padrão esperado:

\- Validar os dados recebidos.

\- Retornar códigos HTTP adequados.

\- Manter respostas consistentes.

\- Tratar erros sem revelar informações internas.

\- Respeitar os contratos utilizados pelo aplicativo Flutter.



Antes de alterar uma rota, verificar se o aplicativo depende do formato atual da resposta.



\## 9. Boas práticas de desenvolvimento



Sempre:

\- Explicar o que será alterado antes de mudanças importantes.

\- Apresentar o arquivo e a localização exata do código.

\- Preservar funcionalidades existentes.

\- Evitar alterações desnecessárias.

\- Tratar exceções adequadamente.

\- Utilizar consultas parametrizadas no MySQL.

\- Separar responsabilidades entre rotas, serviços e acesso ao banco.

\- Escrever código legível e organizado.

\- Considerar segurança e escalabilidade.



Não inventar tabelas, funções, rotas ou configurações sem verificar o projeto.



\## 10. Git e branches



A branch de desenvolvimento é `desenvolvimento`.



Não realizar alterações diretamente na `main` sem autorização.



Não executar comandos destrutivos como reset, clean ou restore sem explicar os riscos e receber autorização.



Não versionar:

\- `.env`

\- Senhas e chaves secretas.

\- `venv/`

\- `\_\_pycache\_\_/`

\- Arquivos privados de clientes em `uploads/`



\## 11. Como trabalhar comigo



O desenvolvedor está aprendendo Flask, Python, MySQL e desenvolvimento de APIs.



Portanto:

\- Explicar as alterações passo a passo.

\- Utilizar linguagem clara e objetiva.

\- Não entregar apenas código sem explicar sua função.

\- Informar exatamente onde inserir cada trecho.

\- Quando corrigir um erro, explicar sua causa.

\- Não reescrever arquivos inteiros quando uma alteração pequena resolver.

\- Antes de implementar uma funcionalidade, analisar sua compatibilidade com o código existente.



\*\*Regra principal:\*\* o código e o banco de dados atuais são a referência técnica. Estas instruções registram o contexto e as regras do negócio, mas não substituem a inspeção dos arquivos reais do projeto.

