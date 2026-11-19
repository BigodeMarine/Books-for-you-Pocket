# Integrações

## Google Books

`BookProvider` em `backend/app/services/external_books/base.py` é um protocolo assíncrono que declara `search()` e `get_by_id()`, além de erros normalizados. `GoogleBooksProvider` implementa o contrato usando HTTPX e a URL de volumes do Google Books.

### Pesquisa

`GET /api/v1/external-books/search` aceita exatamente um critério (`title`, `author` ou `isbn`) e parâmetros de página. O adapter converte os critérios em `intitle:`, `inauthor:` ou `isbn:`, envia `startIndex` e `maxResults` e normaliza campos como título, autores, editora, data de publicação, ISBNs, páginas, categorias, idioma e links. Itens sem ID, `volumeInfo` ou título utilizável são ignorados.

### Consulta por ID e importação

`get_by_id(provider_id)` consulta `/volumes/{id}`, retorna `None` em 404 e valida o volume normalizado. É uma operação interna; não é endpoint público. A importação do volume para `Work`/`Edition` é aprovada para o MVP, mas não implementada. O endpoint planejado e seu contrato constam em [Decisões técnicas](05-technical-decisions.md).

### Timeout, quota e falhas

O `httpx.AsyncClient` é criado no lifespan com timeout de 5 segundos. Timeout do provider mapeia para HTTP 504; quota (429 ou razões de quota reconhecidas em 403) para 503; falha de transporte/status ou resposta inválida para 502 pela rota pública. Falhas não devem expor o corpo bruto do provider ao cliente.

## Open Library

`open_library` aparece em `MetadataSource` e `ExternalIdentifierSource`, mas a auditoria não encontrou provider ou integração funcional. É uma possibilidade futura, não uma integração existente nem uma decisão aprovada de implementação.

## IA — arquitetura futura

A pesquisa inteligente em linguagem natural é visão futura aprovada. Deverá encontrar obras e ofertas reais presentes na plataforma e não inventar preços/ofertas. A arquitetura deverá permitir substituir provider/modelo sem acoplar regras centrais do domínio. Não há integração, fornecedor ou modelo escolhido no estado atual.
