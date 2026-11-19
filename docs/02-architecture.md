# Arquitetura

## Arquitetura implementada

O backend é uma aplicação FastAPI organizada em rotas HTTP, schemas Pydantic, services de consulta, models SQLAlchemy e configuração/persistência em `core`. As rotas de catálogo dependem de sessão SQLAlchemy síncrona e delegam consultas aos services. A rota Google Books é assíncrona e recebe um provider construído com o cliente HTTP compartilhado no ciclo de vida da aplicação.

### Consulta ao catálogo

1. FastAPI valida parâmetros de rota e query.
2. A dependência `get_db` abre uma sessão e fecha-a ao final da requisição.
3. O router chama `services.catalog` ou `services.offers`.
4. O service consulta models e retorna registros/contagens; o router transforma ausência em 404 e serializa pelo schema de resposta.

### Pesquisa Google Books

1. A aplicação cria `httpx.AsyncClient` no lifespan com timeout de 5 segundos.
2. A dependência `get_book_provider` cria `GoogleBooksProvider` com esse cliente.
3. `GET /api/v1/external-books/search` valida um critério entre título, autor e ISBN.
4. O provider chama a API Google Books, normaliza os volumes e classifica falhas; a rota traduz erros de provider em status HTTP.

`GoogleBooksProvider.get_by_id()` é operação interna do provider. Não é endpoint público e não significa que exista busca pública por ID. A importação e persistência de volumes ainda não estão implementadas.

## Domínio e relações

`Work` representa a obra; `Edition` representa uma edição e contém ISBN e metadados editoriais. `EditionExternalIdentifier` associa uma edição a uma fonte e ID externos. `Author` e `Genre` ligam-se a `Work` por tabelas associativas. `Offer` liga edição a vendedor; `PriceHistory` armazena snapshots. Os detalhes de constraints e migrations estão em [Database](04-database.md).

## Arquitetura futura aprovada

A futura pesquisa inteligente deverá converter a intenção em linguagem natural em descoberta de obras do catálogo e ofertas reais da plataforma. A IA não deve ser fonte de preços ou ofertas inventados. A camada de IA deverá ficar desacoplada das regras centrais do domínio, permitindo substituir fornecedor ou modelo. Isso é requisito arquitetural aprovado, ainda sem implementação nem escolha aprovada de fornecedor/modelo.

A política conservadora de preenchimento de metadados descrita para a importação é específica do MVP. A arquitetura deverá permitir evolução posterior para atualização seletiva, proveniência por campo e sincronização, sem transformar a política inicial em limite permanente.

## Referências de implementação

- `backend/app/main.py`
- `backend/app/api/routes/`
- `backend/app/services/`
- `backend/app/schemas/`
- `backend/app/models/`
- [Integrações](07-integrations.md)
- [Decisões técnicas](05-technical-decisions.md)
