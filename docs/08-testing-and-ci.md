# Testes e CI

## Testes

Pytest está configurado em `backend/pyproject.toml`, com `pythonpath = ["."]` e `testpaths = ["tests"]`. Os testes de services e API usam SQLite em memória; os testes do provider Google Books simulam transporte HTTP. Há testes para health check, configuração de banco, schemas, consultas de catálogo, ofertas/histórico, models, identificadores externos, API externa e mapeamento de erros do Google Books.

SQLite não valida integralmente comportamento específico de PostgreSQL, incluindo enum nativo. A auditoria não executou testes; esta documentação não afirma resultado de execução.

## Ruff

Ruff é dependência de desenvolvimento. O workflow invoca `poetry run ruff check app tests alembic`. A auditoria não encontrou configuração Ruff explícita no `pyproject.toml`.

## CI

`.github/workflows/backend-ci.yml` executa em push para `main`, `feature/**`, `fix/**` e pull request para `main`. Usa Ubuntu, Python 3.11 e Poetry 2.4.1; instala dependências de desenvolvimento e roda:

```bash
poetry run ruff check app tests alembic
poetry run pytest -v
```

O workflow não sobe PostgreSQL nem executa migrations. Não há validação automatizada de upgrade/downgrade das migrations identificada na auditoria.

## Referências

`backend/pyproject.toml`, `backend/tests/*.py` e `.github/workflows/backend-ci.yml`.
