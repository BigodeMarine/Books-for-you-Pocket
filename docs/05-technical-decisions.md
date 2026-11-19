# Decisões técnicas

Este documento separa implementação observada de decisões aprovadas para trabalho futuro. As regras conservadoras da importação descritas abaixo são específicas do MVP.

## Implementadas no código

- **Implementada:** API FastAPI com consultas de catálogo/ofertas, health check e busca Google Books. A rota pública de importação ainda está pendente.
- **Implementada:** protocolo `BookProvider` e provider Google Books, incluindo `search()` e operação interna `get_by_id()`.
- **Implementada:** models, enum `ExternalIdentifierSource` distinto de `MetadataSource`, constraint única por fonte/ID e migration da tabela de identificadores. A existência do schema não implementa o fluxo de importação.
- **Implementada:** schemas da importação e fundação do serviço de persistência Google Books, incluindo resolução por identificador externo, idempotência por `(source, external_id)`, regras de metadados e proveniência, ISBN, autores, gêneros e warnings. O serviço recebe uma `Session` do chamador e executa `flush()`; não abre, confirma, reverte nem fecha a sessão.

## Aprovadas para o MVP — contrato HTTP pendente

### Endpoint e contrato conceitual

`POST /api/v1/catalog/imports/google-books` deverá aceitar:

- `provider_id` do volume Google Books;
- `work_target`, discriminado como destino existente com `work_id` UUID ou nova Work com `work_type`;
- `edition_format`;
- `language_fallback`.

Metadados serão obtidos do provider, não enviados livremente pelo cliente. `work_target` será obrigatório se a edição não for encontrada. `edition_format` será obrigatório quando uma nova Edition precisar ser criada. `language_fallback` será obrigatório quando o provider não informar idioma e houver criação de Edition.

No contrato aprovado, `work_target` é uma união discriminada pelo campo `kind`: a variante `existing` contém `work_id`, e a variante `new` contém `work_type`.

Exemplo de Work existente:

```json
{
  "work_target": {
    "kind": "existing",
    "work_id": "uuid"
  }
}
```

Exemplo de Work nova:

```json
{
  "work_target": {
    "kind": "new",
    "work_type": "book"
  }
}
```

`edition_format` e `language_fallback` são opcionais no schema; sua obrigatoriedade depende de ser necessário criar uma Edition e da presença de idioma no provider.

A resposta contém `work_id`, `edition_id`, `work_created`, `edition_created` e `warnings`. `warnings` é uma lista de objetos `{code, message}`, com `code` estável para tratamento programático e `message` legível.

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
| 500 | Falha inesperada de persistência após rollback integral; detalhes técnicos somente nos logs. |

O contrato do endpoint está aprovado, mas a rota HTTP pública e seus testes ainda não foram implementados. A fundação de schemas e persistência descrita acima já está implementada.

### Regras de importação aprovadas

- Buscar volume no Google Books antes de iniciar transação de persistência.
- A camada chamadora controla a transação: o serviço recebe a `Session` aberta pelo chamador e executa `flush()`, sem abrir, confirmar, reverter ou fechar a sessão. A integração futura do endpoint deverá definir o limite da transação e garantir rollback em falha.
- Usar `(source, external_id)` em `edition_external_identifiers` como chave natural de idempotência. Reimportações reutilizam a Edition; não criar tabela ou mecanismo adicional de idempotência no MVP.
- Conflitos de ISBN existentes seguem a regra de ignorar o ISBN conflitante com warning, sem impedir persistência de outro ISBN válido não conflitante.
- Não sobrescrever campos já preenchidos; completar campos vazios. `metadata_source=manual` protege campos da Edition contra alterações automáticas, mas não bloqueia registrar identificadores externos.
- Os campos legados `Edition.metadata_source`, `metadata_external_id` e `metadata_updated_at` representam a proveniência principal dos metadados da Edition; `EditionExternalIdentifier` registra a identidade da Edition em provedores externos. Essas responsabilidades são distintas e ambos os registros devem ser mantidos.
- Em Edition nova, definir `metadata_source=google_books`, `metadata_external_id=provider_id` e preencher `metadata_updated_at`. Em Edition existente com `metadata_source=manual`, preservar os três campos. Se houver outra fonte, preservar a proveniência existente. Se `metadata_source` estiver ausente, preencher a proveniência Google Books — incluindo ID externo e timestamp — quando metadados forem efetivamente importados.
- Ao criar Work, descrição Google Books pode preencher `Work.description`; ao importar para Work existente, não copiar a descrição do volume.
- Mapeamento: `title` → `Work.title`; `description` → `Work.description` somente ao criar Work; `publisher`, `publishedDate`, `pageCount`, `language`, `imageLinks.thumbnail` → `Edition.publisher`, `Edition.publication_date`, `Edition.page_count`, `Edition.language`, `Edition.cover_url`; `authors` e `categories` → relações Work–Author e Work–Genre.
- Aceitar data somente no formato `YYYY-MM-DD` e se válida. Datas parciais ou inválidas são ignoradas com warning.
- ISBN-10/13 devem passar validação de checksum. ISBN inválido é ignorado com warning; ISBN válido já associado a outra Edition também é ignorado com warning, sem reassociação ou sobrescrita; ausência de ISBN não impede importação.
- Autores: normalizar espaços e comparar sem diferenciar maiúsculas/minúsculas. Criar sem correspondência, reutilizar correspondência única; múltiplas correspondências geram warning e não associação automática. Não unificar variantes ou nomes semelhantes sem identificador confiável.
- Gêneros: slug determinístico em minúsculas, sem acentos, separadores convertidos em hífen, caracteres especiais desnecessários removidos e hífens duplicados/de borda eliminados. Criar quando ausente, reutilizar correspondência única; ambiguidade ou colisão gera warning e não associação automática. Não dividir categorias automaticamente. `id` é identidade estável; `name` serve apresentação/pesquisa textual e `slug` é conveniência legível, não base de pesquisa/apresentação de promoções.
- Idioma ausente exige fallback explícito do cliente se nova Edition for criada.
- Nunca mesclar Works automaticamente apenas pelo título.
- Se Edition existente for encontrada, sua Work é autoritativa; destino contraditório gera 409.
- Se Edition não existir, `work_target` é obrigatório. Não duplicar Work ou Edition para o mesmo identificador externo.
- Warnings aprovados: `isbn_invalid`, `isbn_already_assigned`, `publication_date_incomplete`, `publication_date_invalid`, `author_ambiguous`, `genre_ambiguous` e `genre_slug_collision`. Não gerar warning apenas porque campo opcional está ausente.

## Provisórias para o MVP

- A política de preencher apenas campos vazios e proteger metadados manuais é conservadora e limitada ao MVP. Não define uma limitação definitiva da arquitetura.
- A política aditiva das associações de autores e gêneros também é específica do MVP: adicionar associações ausentes, preservar todas as existentes e não associar correspondências ambíguas. Isso não limita a evolução futura da arquitetura.
- A arquitetura deverá permitir evolução para atualização seletiva e provenance por campo, sem tornar a política MVP uma limitação permanente.

## Aprovadas para futuro

- Pesquisa inteligente em linguagem natural para localizar obras do catálogo e ofertas reais. IA não pode inventar obras, preços ou ofertas.
- Desacoplar IA do domínio, de modo que a troca de provedor/modelo não reescreva regras centrais. Nenhum fornecedor ou modelo específico está aprovado.

## Melhorias futuras

- Avaliar recovery automático de `IntegrityError`, reconsulta em nova sessão e reconciliação avançada de concorrência entre importações.

## Ideia futura ou pendente de aprovação

- Open Library consta nos enums, mas não há provider implementado e não há decisão aprovada nesta especificação para construir a integração.

## Referências

Implementação: `backend/app/services/external_books/`, `backend/app/models/`, `backend/app/api/routes/` e `backend/alembic/versions/`. Regras aprovadas: especificação de produto fornecida para esta documentação. Ver [Regras de negócio](06-business-rules.md).
