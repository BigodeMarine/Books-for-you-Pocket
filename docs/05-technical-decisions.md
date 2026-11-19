# Decisões técnicas

Este documento separa implementação observada de decisões aprovadas para trabalho futuro. A política de importação descrita abaixo é específica do MVP.

## Implementadas no código

- **Implementada:** API FastAPI com consultas de catálogo/ofertas, health check e busca Google Books. Isso não inclui importação persistente.
- **Implementada:** protocolo `BookProvider` e provider Google Books, incluindo `search()` e operação interna `get_by_id()`.
- **Implementada:** models, enum `ExternalIdentifierSource` distinto de `MetadataSource`, constraint única por fonte/ID e migration da tabela de identificadores. A existência do schema não implementa o fluxo de importação.

## Aprovadas, mas ainda não implementadas — importação do MVP

### Endpoint e contrato conceitual

`POST /api/v1/catalog/imports/google-books` deverá aceitar:

- `provider_id` do volume Google Books;
- `work_target`, discriminado como destino existente com `work_id` UUID ou nova Work com `work_type`;
- `edition_format`;
- `language_fallback`.

Metadados serão obtidos do provider, não enviados livremente pelo cliente. `work_target` será obrigatório se a edição não for encontrada. `edition_format` será obrigatório quando uma nova Edition precisar ser criada. `language_fallback` será obrigatório quando o provider não informar idioma e houver criação de Edition.

A resposta conceitual contém `work_id`, `edition_id`, `work_created`, `edition_created` e `warnings`.

| HTTP | Contrato aprovado |
|---|---|
| 200 | Edition existente reutilizada, inclusive se identificadores forem registrados ou campos vazios completados. |
| 201 | Nova Work ou nova Edition criada. |
| 404 | Volume externo ou Work solicitada não encontrada. |
| 409 | Conflito, inclusive destino incompatível com a Work da Edition encontrada. |
| 422 | Informação obrigatória ausente: destino, formato ou fallback de idioma quando necessário. |
| 502 | Falha de transporte ou resposta inválida do provider. |
| 503 | Quota do provider. |
| 504 | Timeout do provider. |

Este endpoint e contrato estão aprovados, mas não implementados.

### Regras de importação aprovadas

- Buscar volume no Google Books antes de iniciar transação de persistência.
- Persistir todas as alterações numa transação única; executar flush e commit em sucesso e rollback integral em falha.
- Em `IntegrityError`, fazer rollback e reconsultar em sessão/transação válida; não reutilizar sessão em estado de falha. Tratar concorrência de identificador externo e ISBN.
- Não sobrescrever campos já preenchidos; completar campos vazios. `metadata_source=manual` protege campos da Edition contra alterações automáticas, mas não bloqueia registrar identificadores externos.
- Ao criar Work, descrição Google Books pode preencher `Work.description`; ao importar para Work existente, não copiar a descrição do volume.
- Autores: trim, reduzir espaços repetidos e comparar sem diferenciar maiúsculas/minúsculas. Criar sem correspondência, reutilizar correspondência única; múltiplas correspondências geram warning e não associação automática.
- Gêneros: slug determinístico; criar quando ausente, reutilizar correspondência única; colisão/ambiguidade gera warning e não associação automática.
- ISBN inválido é ignorado com warning; identificador externo continua sendo usado.
- Datas parciais não são completadas por suposição.
- Idioma ausente exige fallback explícito do cliente se nova Edition for criada.
- Nunca mesclar Works automaticamente apenas pelo título.
- Se Edition existente for encontrada, sua Work é autoritativa; destino contraditório gera 409.

## Provisórias para o MVP

- A política de preencher apenas campos vazios e proteger metadados manuais é conservadora e limitada ao MVP. Não define uma limitação definitiva da arquitetura.
- A arquitetura deverá permitir evolução para atualização seletiva, proveniência por campo e sincronização de metadados.

## Aprovadas para futuro

- Pesquisa inteligente em linguagem natural para localizar obras do catálogo e ofertas reais. IA não pode inventar obras, preços ou ofertas.
- Desacoplar IA do domínio, de modo que a troca de provedor/modelo não reescreva regras centrais. Nenhum fornecedor ou modelo específico está aprovado.

## Ideia futura ou pendente de aprovação

- Open Library consta nos enums, mas não há provider implementado e não há decisão aprovada nesta especificação para construir a integração.

## Referências

Implementação: `backend/app/services/external_books/`, `backend/app/models/`, `backend/app/api/routes/` e `backend/alembic/versions/`. Regras aprovadas: especificação de produto fornecida para esta documentação. Ver [Regras de negócio](06-business-rules.md).
