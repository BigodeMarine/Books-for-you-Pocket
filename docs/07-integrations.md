# Integrações

## Google Books

`BookProvider` em `backend/app/services/external_books/base.py` é um protocolo assíncrono que declara `search()` e `get_by_id()`, além de erros normalizados. `GoogleBooksProvider` implementa o contrato usando HTTPX e a URL de volumes do Google Books.

### Pesquisa

`GET /api/v1/external-books/search` aceita exatamente um critério (`title`, `author` ou `isbn`) e parâmetros de página. O adapter converte os critérios em `intitle:`, `inauthor:` ou `isbn:`, envia `startIndex` e `maxResults` e normaliza campos como título, autores, editora, data de publicação, ISBNs, páginas, categorias, idioma e links. Itens sem ID, `volumeInfo` ou título utilizável são ignorados.

### Consulta por ID e importação

`get_by_id(provider_id)` consulta `/volumes/{id}`, retorna `None` em 404 e valida o volume normalizado. É uma operação interna; não é endpoint público. A consulta por ID e a fundação dos schemas e da persistência para importar o volume em `Work`/`Edition` estão implementadas; o endpoint público e seus testes seguem pendentes. O contrato consta em [Decisões técnicas](05-technical-decisions.md).

O mapeamento aprovado para a importação é: `title` para `Work.title`; `description` para `Work.description` somente ao criar Work; `publisher`, `publishedDate`, `pageCount`, `language` e `imageLinks.thumbnail` para `Edition.publisher`, `Edition.publication_date`, `Edition.page_count`, `Edition.language` e `Edition.cover_url`; `authors` e `categories` para relações de Work com Author e Genre. Os metadados vêm do provider, não do cliente.

No MVP, `publishedDate` só será aceito como data válida `YYYY-MM-DD`; datas parciais ou inválidas geram warnings e são ignoradas. ISBN-10 e ISBN-13 precisam passar checksum; ISBN inválido ou já atribuído a outra Edition é ignorado com warning, sem interromper a importação. O contrato de warnings e as demais regras estão em [Regras de negócio](06-business-rules.md).

O ID externo (`source`, `external_id`) é a chave natural de idempotência da importação. O serviço de persistência já procura esse identificador e reutiliza a Edition existente nas reimportações. A garantia decorre da persistência, não do provider.

O serviço recebe uma `Session` do chamador e executa `flush()`; não abre, confirma, reverte nem fecha a sessão. O controle transacional pertence ao chamador. Recovery automático de `IntegrityError`, reconsulta em nova sessão e reconciliação avançada de concorrência não estão implementados e podem ser avaliados como melhorias futuras.

Os campos legados `Edition.metadata_source`, `metadata_external_id` e `metadata_updated_at` representam a proveniência principal dos metadados da Edition. `EditionExternalIdentifier` registra a identidade da Edition no provider e tem responsabilidade distinta. No MVP, Edition nova recebe proveniência Google Books, ID do provider e timestamp; Edition existente com fonte `manual` ou outra fonte preserva a proveniência existente. Se `metadata_source` estiver ausente, a proveniência Google Books é preenchida quando metadados forem efetivamente importados. O identificador externo é registrado em todos os casos.

As associações de autores e gêneros seguem política aditiva no MVP: em Work existente, incluir apenas relações ausentes, não duplicar ou remover relações e não associar correspondências ambíguas; warnings aprovados não interrompem a importação. Para Work nova, criar as relações normalmente. A política é específica do MVP, não uma restrição arquitetural permanente.

### Timeout, quota e falhas

O `httpx.AsyncClient` é criado no lifespan com timeout de 5 segundos. Timeout do provider mapeia para HTTP 504; quota (429 ou razões de quota reconhecidas em 403) para 503; falha de transporte/status ou resposta inválida para 502 pela rota pública. Falhas não devem expor o corpo bruto do provider ao cliente.

## Open Library

`open_library` aparece em `MetadataSource` e `ExternalIdentifierSource`, mas a auditoria não encontrou provider ou integração funcional. É uma possibilidade futura, não uma integração existente nem uma decisão aprovada de implementação.

## IA — arquitetura futura

A pesquisa inteligente em linguagem natural é visão futura aprovada. Deverá encontrar obras e ofertas reais presentes na plataforma e não inventar preços/ofertas. A arquitetura deverá permitir substituir provider/modelo sem acoplar regras centrais do domínio. Não há integração, fornecedor ou modelo escolhido no estado atual.
