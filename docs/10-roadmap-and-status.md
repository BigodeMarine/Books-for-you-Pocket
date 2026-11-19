# Roadmap e status

Os status abaixo distinguem funcionalidades presentes de decisões aprovadas e possibilidades. Model, enum, diretório ou protocolo sem fluxo funcional não conta como funcionalidade completa.

## Implementado

- **Catálogo de leitura:** listagem filtrada/paginada e detalhe de Work com edições, autores e gêneros.
- **Ofertas e preços:** leitura de ofertas ativas por edição/Work, detalhes de oferta e histórico paginado com filtro temporal.
- **Google Books:** busca por título, autor ou ISBN via API; normalização de volume e mapeamento de timeout, quota e falhas.
- **Identificadores externos — estrutura:** model, enum, constraint e migration para identificadores por Edition. O fluxo de importação não está implementado.
- **Frontend:** apenas diretórios foram encontrados em `frontend/src`; nenhuma implementação de tela ou fluxo foi identificada.

## Aprovado e pendente

- **Importação Google Books MVP:** operação de importação com seleção/criação de Work, reutilização/criação de Edition, identificador externo, regras conservadoras de metadados, warnings, transação e tratamento de concorrência. Endpoint planejado: `POST /api/v1/catalog/imports/google-books`. Contrato conceitual e status HTTP aprovados estão em [Decisões técnicas](05-technical-decisions.md). Ainda não implementado.
- **Pesquisa inteligente por IA:** busca em linguagem natural para localizar obras relevantes e ofertas reais da plataforma. A IA não deverá inventar dados comerciais; a camada será substituível sem mudar regras centrais. Visão aprovada e futura, sem implementação ou fornecedor/modelo escolhido.
- **Flexibilidade de metadados:** arquitetura deve permitir evolução além da política conservadora do MVP, incluindo atualização seletiva, proveniência por campo e sincronização.

## Ideia futura / não aprovada como entrega

- **Open Library:** aparece nos enums, sem provider funcional ou decisão aprovada para implementação.
- Outras funcionalidades de escrita, gestão administrativa de catálogo e processos de ingestão não têm especificação aprovada identificada aqui. A API atual não as oferece; não são anunciadas como roadmap comprometido.

## Pendências de confirmação

- Estado efetivo do banco implantado: não consultado. O head esperado pelas migrations no repositório é `b71e942efc61`.
- Telas, navegação e tecnologia efetiva do frontend: não confirmadas; há apenas diretórios vazios observados pela auditoria.
- Modelo/provedor de IA e desenho detalhado da integração: não definidos.
- A implementação e os contratos completos da importação devem ser conferidos com [Decisões técnicas](05-technical-decisions.md) e [Regras de negócio](06-business-rules.md).

## Referências

O código de rotas, services, models e migrations documenta o estado atual. O README registra o objetivo e tecnologias planejadas. As decisões fornecidas para esta documentação são a fonte do status aprovado da importação e da visão futura de IA.
