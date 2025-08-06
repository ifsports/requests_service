# Requests Service

## Descrição

O **Requests Service** é um serviço FastAPI responsável por gerenciar solicitações de adição, exclusão e edição de equipes e seus membros no sistema IFSports. O serviço processa aprovações e rejeições dessas solicitações e comunica os resultados para outros serviços interessados através de mensageria (RabbitMQ).

## Funcionalidades Principais

- 🏈 **Gerenciamento de Equipes**: Solicitações de criação, aprovação e exclusão de equipes
- 👥 **Gerenciamento de Membros**: Adição e remoção de membros das equipes
- ✅ **Sistema de Aprovação**: Processamento de aprovações e rejeições de solicitações
- 📨 **Mensageria**: Comunicação assíncrona com outros serviços via RabbitMQ
- 🔐 **Autenticação JWT**: Sistema de autenticação baseado em tokens JWT
- 🏫 **Multi-campus**: Suporte a diferentes campus do IF

## Tecnologias Utilizadas

- **FastAPI**: Framework web para Python
- **SQLAlchemy**: ORM para banco de dados
- **Alembic**: Migrations de banco de dados
- **RabbitMQ**: Sistema de mensageria
- **JWT**: Autenticação via tokens
- **PostgreSQL**: Banco de dados relacional
- **Docker**: Containerização

## Estrutura do Projeto

```
├── alembic/                 # Migrations do banco de dados
├── messaging/               # Consumidores e produtores de mensagens
├── requests/                # Módulo principal de requests
│   ├── models/             # Modelos de dados
│   └── routers/            # Rotas da API
├── services/               # Serviços e lógica de negócio
├── shared/                 # Utilitários compartilhados
├── auth.py                 # Sistema de autenticação
├── main.py                 # Aplicação principal
└── Dockerfile              # Configuração do container
```

## Endpoints Principais

- `GET /health` - Verificação de saúde do serviço
- Rotas de requests (definidas em `requests/routers/`)

## Configuração

### Variáveis de Ambiente

- `JWT_SECRET_KEY`: Chave secreta para validação de tokens JWT
- `SQLALCHEMY_DATABASE_URL`: URL de conexão com o banco de dados

### Executando com Docker

```bash
docker build -t requests-service .
docker run -p 8001:8001 requests-service
```

## Health Check

O serviço disponibiliza um endpoint de health check em `/health` que retorna:
- Status da API
- Status da tarefa do consumidor RabbitMQ

## Desenvolvimento

### Migrations

```bash
# Aplicar migrations
alembic upgrade head

# Criar nova migration
alembic revision --autogenerate -m "Descrição da mudança"
```

## Tipos de Solicitações

- `approve_team`: Aprovação de equipes
- `delete_team`: Exclusão de equipes  
- `remove_team_member`: Remoção de membros da equipe

## Status das Solicitações

- `pendent`: Aguardando aprovação
- `approved`: Aprovada
- `rejected`: Rejeitada

---

*Este serviço faz parte do ecossistema IFSports e integra-se com outros microserviços através de mensageria.*
