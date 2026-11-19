# Roadmap e status

Os status abaixo distinguem funcionalidades presentes de decisões aprovadas e possibilidades. Model, enum, diretório ou protocolo sem fluxo funcional não conta como funcionalidade completa.

## Implementado

- **Catálogo de leitura:** listagem filtrada/paginada e detalhe de Work com edições, autores e gêneros.
- **Ofertas e preços:** leitura de ofertas ativas por edição/Work, detalhes de oferta e histórico paginado com filtro temporal.
- **Google Books:** busca por título, autor ou ISBN via API; normalização de volume e mapeamento de timeout, quota e falhas.
- **Importação Google Books — fundação:** schemas, consulta de volume por ID, serviço de persistência, idempotência por `(source, external_id)` e regras aprovadas do MVP para metadados, proveniência, ISBN, autores, gêneros e warnings. O serviço recebe a `Session` do chamador e executa `flush()`; o controle transacional é externo ao serviço.
- **Identificadores externos:** model, enum, constraint e migration para identificadores por Edition; o serviço de importação registra e resolve esses identificadores.
- **Frontend:** apenas diretórios foram encontrados em `frontend/src`; nenhuma implementação de tela ou fluxo foi identificada.

## Aprovado e pendente

- **Endpoint de importação Google Books MVP — aprovado e pendente:** implementar `POST /api/v1/catalog/imports/google-books`, com request discriminado por `work_target.kind` (`existing` com `work_id` ou `new` com `work_type`), integração do serviço existente, mapeamento dos erros e status HTTP aprovados (200, 201, 404, 409, 422, 500, 502, 503 e 504) e testes HTTP. A fundação dos schemas e da persistência já está implementada; detalhes em [Decisões técnicas](05-technical-decisions.md) e [Regras de negócio](06-business-rules.md).
- **Pesquisa inteligente por IA:** busca em linguagem natural para localizar obras relevantes e ofertas reais da plataforma. A IA não deverá inventar dados comerciais; a camada será substituível sem mudar regras centrais. Visão aprovada e futura, sem implementação ou fornecedor/modelo escolhido.
- **Flexibilidade de metadados:** arquitetura deve permitir evolução além da política conservadora do MVP, incluindo atualização seletiva, proveniência por campo e sincronização.

## Ideia futura / não aprovada como entrega

- **Open Library:** aparece nos enums, sem provider funcional ou decisão aprovada para implementação.
- Outras funcionalidades de escrita, gestão administrativa de catálogo e processos de ingestão não têm especificação aprovada identificada aqui. A API atual não as oferece; não são anunciadas como roadmap comprometido.

## Pendências de confirmação

- Estado efetivo do banco implantado: não consultado. O head esperado pelas migrations no repositório é `b71e942efc61`.
- Telas, navegação e tecnologia efetiva do frontend: não confirmadas; há apenas diretórios vazios observados pela auditoria.
- Modelo/provedor de IA e desenho detalhado da integração: não definidos.
- Recovery automático de `IntegrityError`, reconciliação avançada de concorrência em PostgreSQL e validação de migrations no CI podem ser avaliados como melhorias futuras; não estão implementados no MVP.

## Referências

O código de rotas, services, models e migrations documenta o estado atual. O README registra o objetivo e tecnologias planejadas. As decisões fornecidas para esta documentação são a fonte do status aprovado da importação e da visão futura de IA.
