# Regras de negócio

Este documento diferencia regras que o código já aplica das regras aprovadas para a futura importação. As regras de importação são **aprovadas para o MVP**, não comportamento implementado.

## Implementadas atualmente

- A busca de obras permite filtros simultâneos por trecho do título, autor, gênero e tipo, com paginação.
- Consultas de ofertas retornam apenas ofertas ativas e ordenam por preço crescente, usando UUID para desempate. Oferta ativa continua visível mesmo se o vendedor estiver inativo.
- Histórico é acessível para oferta ativa, pode ser filtrado por limites inclusivos de data e é ordenado do mais recente para o mais antigo.
- A busca Google Books exige exatamente um critério entre título, autor e ISBN. Registros sem dados mínimos/título utilizável são descartados na normalização.

Referências: `backend/app/services/catalog.py`, `backend/app/services/offers.py`, `backend/app/api/routes/` e `backend/app/services/external_books/google_books.py`.

## Aprovadas para o MVP da importação Google Books — ainda não implementadas

1. Uma Edition poderá possuir identificadores de diferentes providers em `edition_external_identifiers`.
2. `ExternalIdentifierSource` será separado de `MetadataSource` e conterá apenas `google_books` e `open_library`; não haverá valor `manual` nesse enum.
3. Importação conservadora: não sobrescrever campos já preenchidos automaticamente; completar somente campos vazios.
4. `metadata_source=manual` protege campos da Edition contra mudanças automáticas, sem impedir salvar identificador externo.
5. Ao criar Work nova, a descrição do Google Books pode preencher `Work.description`.
6. Ao importar para Work existente, não copiar descrição do volume para `Work.description`, mesmo se vazia.
7. Autores: normalizar com trim, remoção de espaços repetidos e comparação case-insensitive. Criar se não houver correspondência; reutilizar se houver uma única; se houver várias, não associar automaticamente, gerar warning e continuar a importação.
8. Gêneros: usar slug determinístico. Criar se não houver correspondência; reutilizar uma correspondência única; em colisão/ambiguidade, não associar e gerar warning.
9. ISBN inválido será ignorado com warning. O identificador externo segue sendo usado.
10. Datas parciais não serão convertidas em datas completas por suposição.
11. Se idioma estiver ausente, exigir fallback explícito do cliente quando for criar Edition.
12. Nunca mesclar Works automaticamente apenas por título.
13. Se Edition existente for encontrada, sua Work é autoritativa; `work_target` contraditório resulta em HTTP 409.
14. Se Edition não for encontrada, `work_target` é obrigatório.
15. `work_target` é discriminado: Work existente por `work_id` UUID ou nova Work por `work_type`.
16. `edition_format` é opcional no schema da requisição, mas obrigatório se uma nova Edition precisar ser criada.
17. `language_fallback` é opcional e obrigatório se provider não informar idioma e nova Edition precisar ser criada.
18. Metadados vêm do provider, não são enviados livremente pelo cliente.

O contrato completo, status HTTP aprovados e fluxo transacional estão em [Decisões técnicas](05-technical-decisions.md). A arquitetura deverá permitir no futuro atualização seletiva e proveniência por campo; a política acima não é limite permanente.
