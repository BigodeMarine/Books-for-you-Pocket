# Regras de negócio

Este documento diferencia regras já implementadas das regras aprovadas para o endpoint HTTP ainda pendente. A fundação de schemas e persistência da importação já está implementada; as regras específicas do MVP não definem limites permanentes da arquitetura.

## Implementadas atualmente

- A busca de obras permite filtros simultâneos por trecho do título, autor, gênero e tipo, com paginação.
- Consultas de ofertas retornam apenas ofertas ativas e ordenam por preço crescente, usando UUID para desempate. Oferta ativa continua visível mesmo se o vendedor estiver inativo.
- Histórico é acessível para oferta ativa, pode ser filtrado por limites inclusivos de data e é ordenado do mais recente para o mais antigo.
- A busca Google Books exige exatamente um critério entre título, autor e ISBN. Registros sem dados mínimos/título utilizável são descartados na normalização.

Referências: `backend/app/services/catalog.py`, `backend/app/services/offers.py`, `backend/app/api/routes/` e `backend/app/services/external_books/google_books.py`.

## Importação Google Books — fundação implementada e regras aprovadas para o endpoint

1. Uma Edition poderá possuir identificadores de diferentes providers por meio de `edition_external_identifiers`.
2. `ExternalIdentifierSource` será separado de `MetadataSource` e conterá apenas `google_books` e `open_library`; não haverá valor `manual` nesse enum.
3. `(source, external_id)` é a chave natural de idempotência. Reimportações reutilizam a mesma Edition; o MVP não cria mecanismo ou tabela adicional de idempotência.
4. Importação conservadora: não sobrescrever campos já preenchidos; completar somente campos vazios.
5. `metadata_source=manual` protege metadados de Edition contra alterações automáticas, mas não impede registrar identificador externo.
6. Os campos legados `Edition.metadata_source`, `metadata_external_id` e `metadata_updated_at` representam a proveniência principal dos metadados da Edition. `EditionExternalIdentifier` registra a identidade da Edition em provedores externos; não substituir uma responsabilidade pela outra.
7. Para Edition nova, definir proveniência `google_books`, `provider_id` e timestamp em `metadata_updated_at`. Para Edition existente com `metadata_source=manual`, preservar os três campos. Se a fonte existente for outra, preservar a proveniência. Se `metadata_source` estiver ausente, preencher proveniência Google Books, incluindo ID externo e timestamp, quando houver metadados efetivamente importados. Em todos os cenários, registrar o identificador em `EditionExternalIdentifier`.
8. Mapeamento aprovado: Google Books `title` → `Work.title`; `description` → `Work.description` somente ao criar Work; `publisher` → `Edition.publisher`; `publishedDate` → `Edition.publication_date`; `pageCount` → `Edition.page_count`; `language` → `Edition.language`; `imageLinks.thumbnail` → `Edition.cover_url`; `authors` → relação Work–Author; `categories` → relação Work–Genre.
9. Ao importar para Work existente, não copiar descrição do volume para `Work.description`, mesmo se vazia.
10. Autores: normalizar espaços e comparar case-insensitive. Criar se não houver correspondência; reutilizar se houver uma única; se houver várias, não associar automaticamente, gerar warning e continuar. Não unificar variantes ou nomes semelhantes sem identificador confiável.
11. Gêneros: slug determinístico com minúsculas, remoção de acentos, conversão de espaços/separadores para hífens, remoção de caracteres especiais desnecessários e eliminação de hífens duplicados ou nas extremidades. Criar se não houver correspondência; reutilizar correspondência única; em ambiguidade/colisão, não associar e gerar warning. Não dividir categorias automaticamente.
12. Ao importar para Work existente, adicionar as associações de autores e gêneros ainda ausentes, reutilizar correspondências únicas, não duplicar associações e nunca remover relações existentes. Correspondências ambíguas não são associadas; os warnings aprovados são emitidos e a importação continua. Para Work nova, criar as associações normalmente.
13. A política aditiva de associações é específica do MVP; não é uma limitação definitiva da arquitetura.
14. A identidade e as relações usam `Genre.id`; `name` serve à apresentação e pesquisa textual; `slug` serve a URLs e referências legíveis. Pesquisa e apresentação de promoções não devem depender do slug.
15. Validar checksum de ISBN-10 e ISBN-13. ISBN inválido é ignorado com warning; ISBN ausente não impede importação. ISBN válido já associado a outra Edition é ignorado com warning, sem sobrescrever ou reassociar, e a importação continua.
16. Aceitar `publishedDate` somente se for data válida no formato `YYYY-MM-DD`. Data parcial ou inválida é ignorada com warning, sem completar componentes por suposição.
17. Idioma ausente exige fallback explícito do cliente somente quando nova Edition precisar ser criada.
18. Nunca mesclar Works automaticamente apenas por título.
19. Se Edition existente for encontrada, sua Work é autoritativa; `work_target` contraditório resulta em HTTP 409.
20. Se Edition não for encontrada, `work_target` é obrigatório. A união discriminada usa `kind`: `existing` contém `work_id`; `new` contém `work_type`.
21. `edition_format` é opcional no schema da requisição, mas obrigatório se uma nova Edition precisar ser criada.
22. `language_fallback` é opcional e obrigatório se provider não informar idioma e nova Edition precisar ser criada.
23. Metadados vêm do provider, não são enviados livremente pelo cliente.
24. A consulta ao Google Books ocorre antes da persistência. O serviço recebe uma `Session` do chamador e executa `flush()`, sem abrir, confirmar, reverter ou fechar a sessão; o controle transacional pertence ao chamador.
25. Recovery automático de `IntegrityError`, reconsulta em nova sessão e reconciliação avançada de concorrência não fazem parte do escopo atual; podem ser avaliados como melhorias futuras.

### Warnings aprovados para o MVP

`warnings` é uma lista de objetos com `code` estável e `message` legível. Códigos: `isbn_invalid`, `isbn_already_assigned`, `publication_date_incomplete`, `publication_date_invalid`, `author_ambiguous`, `genre_ambiguous` e `genre_slug_collision`. Não gerar warning apenas pela ausência de campo opcional.

Falha inesperada de persistência deverá resultar em HTTP 500; a camada chamadora deverá controlar rollback e manter detalhes técnicos somente nos logs. A rota HTTP ainda está pendente. Os demais status e contrato estão em [Decisões técnicas](05-technical-decisions.md).

O contrato completo, status HTTP aprovados e fluxo transacional estão em [Decisões técnicas](05-technical-decisions.md). A arquitetura deverá permitir no futuro atualização seletiva e proveniência por campo; a política acima não é limite permanente.
