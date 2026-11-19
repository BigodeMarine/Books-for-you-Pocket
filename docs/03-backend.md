# Backend

## Tecnologias e organização

- `backend/app/main.py`: cria a aplicação FastAPI, lifespan e rotas.
- `backend/app/api/routes/`: endpoints HTTP e tradução de erros para HTTP.
- `backend/app/schemas/`: contratos Pydantic de entrada e saída.
- `backend/app/services/`: consultas de catálogo/ofertas e integração externa.
- `backend/app/models/`: models SQLAlchemy e enums do domínio.
- `backend/app/core/`: configurações, engine, base declarativa e dependência de sessão.
- `backend/alembic/`: ambiente e histórico de migrations.
- `backend/tests/`: testes.

O projeto exige Python `>=3.11,<4.0`; dependências estão em `backend/pyproject.toml` e `backend/poetry.lock`. O código usa SQLAlchemy 2.x e schemas/validação Pydantic v2. Configurações usam `pydantic-settings` e arquivo `.env` na raiz, com variáveis PostgreSQL e defaults de host/porta definidos em `app/core/config.py`. Não registrar valores secretos na documentação.

## Ciclo de vida e persistência

`app/main.py` cria um `httpx.AsyncClient` com timeout de 5 segundos durante o lifespan e o fecha ao encerrar. Esse cliente fica em `app.state.google_books_client`.

`app/core/database.py` cria engine síncrona PostgreSQL via Psycopg, com `pool_pre_ping=True`, e `SessionLocal`. A dependência `get_db()` fornece sessão e a fecha no `finally`. O health check `/health` responde se o processo está ativo; não verifica banco nem Google Books.

## Rotas atuais

| Método e caminho | Função |
|---|---|
| `GET /health` | Health check de processo. |
| `GET /api/v1/catalog/works` | Lista e filtra obras por texto, autor, gênero e tipo; paginação. |
| `GET /api/v1/catalog/works/{work_id}` | Detalhe de obra com edições, autores e gêneros. |
| `GET /api/v1/catalog/editions/{edition_id}/offers` | Lista ofertas ativas de edição, com filtros e paginação. |
| `GET /api/v1/catalog/works/{work_id}/offers` | Lista ofertas ativas nas edições da obra. |
| `GET /api/v1/catalog/offers/{offer_id}` | Detalhe de oferta ativa com vendedor. |
| `GET /api/v1/catalog/offers/{offer_id}/price-history` | Histórico paginado, com intervalo temporal opcional. |
| `GET /api/v1/external-books/search` | Pesquisa Google Books por exatamente um critério: título, autor ou ISBN. |

Parâmetros de paginação e schemas estão definidos nos routers e em `app/schemas/`. Endpoints de escrita não foram identificados. O futuro endpoint de importação está especificado, mas não existe: `POST /api/v1/catalog/imports/google-books`; veja [Decisões técnicas](05-technical-decisions.md).

## Services, providers e erros

`services.catalog` e `services.offers` executam consultas SQLAlchemy de leitura. `services.external_books.base` define o protocolo `BookProvider` e erros normalizados; `GoogleBooksProvider` implementa pesquisa e consulta interna por ID. A rota traduz timeout para 504, quota para 503 e demais erros de provider para 502. Open Library aparece nos enums, mas não há provider implementado identificado.

## Limitações identificadas

- API identificada sem operações de escrita/administração e sem autenticação observada.
- Busca Google Books não persiste resultados; `get_by_id()` não é endpoint.
- Sem fluxo de importação, ingestão automática de ofertas, scheduler ou integração de IA identificados.
- `frontend/src` contém diretórios, sem implementação encontrada na auditoria.
- O health check não verifica dependências.

## Referências

Código-fonte: `backend/app/main.py`, `backend/app/core/`, `backend/app/api/routes/`, `backend/app/services/`, `backend/app/schemas/` e `backend/app/models/`.
