# Banco de dados

## Tecnologia e estado conhecido

O projeto configura PostgreSQL com SQLAlchemy 2.x e Psycopg 3. Alembic mantém as migrations. O repositório contém uma cadeia linear cuja cabeça esperada pelo código é `b71e942efc61`. Isso descreve o schema esperado após aplicar as migrations; o estado de qualquer banco real não foi consultado e permanece **não confirmado**.

## Models

| Model/tabela | Papel e relações principais |
|---|---|
| `Work` / `works` | Obra; relaciona-se a várias `Edition`, `Author` e `Genre`. |
| `Edition` / `editions` | Edição de uma obra; possui ISBN, dados editoriais e proveniência geral de metadados; associa identificadores externos e ofertas. |
| `Author` / `authors` | Autor associado a obras. |
| `Genre` / `genres` | Gênero associado a obras. |
| `Seller` / `sellers` | Loja/vendedor com slug e estado ativo. |
| `Offer` / `offers` | Oferta para uma edição por vendedor; preço, moeda, condição e disponibilidade. |
| `PriceHistory` / `price_history` | Snapshot de preço e disponibilidade por oferta. |
| `EditionExternalIdentifier` / `edition_external_identifiers` | Identificador externo de uma edição por fonte. |

`work_authors` e `work_genres` são tabelas associativas. Os models usam UUID como chave primária.

## Enums

- `WorkType`: `book`, `manga`, `comic`
- `EditionFormat`: `paperback`, `hardcover`, `ebook`, `audiobook`, `digital`, `other`
- `MetadataSource`: `google_books`, `open_library`, `manual`
- `ExternalIdentifierSource`: `google_books`, `open_library` (sem `manual`)
- `OfferCondition`: `new`, `used`
- `AvailabilityStatus`: `in_stock`, `out_of_stock`, `preorder`, `unknown`

`ExternalIdentifierSource` é distinto de `MetadataSource`. A tabela de identificadores tem unicidade por `(source, external_id)`, permitindo o mesmo valor em fontes diferentes.

## Constraints, índices e exclusão

- ISBN-10 e ISBN-13 de edição são únicos quando fornecidos; slugs de gênero e vendedor são únicos.
- Preços e preços originais de oferta/histórico não podem ser negativos.
- Tabelas associativas têm chave primária composta e FKs em cascata.
- Edição aponta para obra com `ON DELETE CASCADE`; identificador externo aponta para edição com `CASCADE`.
- Oferta aponta para edição e vendedor com `RESTRICT`; histórico aponta para oferta com `RESTRICT`.
- Índices incluem nomes/títulos, FKs de edição/oferta, disponibilidade, identificadores por edição e `(offer_id, captured_at)` no histórico.

Ver definições completas em `backend/app/models/` e migrations.

## Histórico de migrations

1. `10ad61f1f29a_create_catalog_and_marketplace_tables.py` — migration raiz; cria catálogo, vendedores, ofertas, histórico e associações.
2. `b71e942efc61_create_edition_external_identifiers.py` — sucede a raiz; cria enum PostgreSQL e tabela de identificadores externos.

Não foram executadas migrations nem consultas ao banco nesta documentação.

## Referências

`backend/app/models/*.py`, `backend/alembic/env.py`, `backend/alembic.ini` e `backend/alembic/versions/*.py`.
