# Books for Your Pocket — visão do projeto

## Propósito

Books for Your Pocket é uma plataforma brasileira para descobrir leituras e comparar promoções e ofertas de livros, quadrinhos e mangás em diferentes lojas. A agregação de ofertas e a descoberta de bons preços são partes centrais da proposta; o produto não se limita a manter um catálogo.

O contexto é o mercado brasileiro de leitura e comércio, com preços e ofertas reais disponibilizados pela própria plataforma. A visão aprovada prevê uma experiência futura na qual a pessoa descreve em linguagem natural o que deseja ler e recebe ajuda para encontrar obras relevantes no catálogo e ofertas disponíveis. IA não deve inventar obras, preços ou ofertas.

## Estado atual

O backend implementa consultas de catálogo, leitura de ofertas e histórico de preços e busca no Google Books. A busca externa também é uma operação de consulta e não persiste resultados no catálogo. Há ainda um modelo para associar identificadores externos a edições. A importação Google Books, a interface frontend e a pesquisa inteligente por IA não estão implementadas.

O README descreve a plataforma como produto de descoberta e recomendação e lista tecnologias frontend como planejadas. A auditoria encontrou apenas diretórios em `frontend/src`, sem arquivos de implementação. A visão de pesquisa inteligente é aprovada como futura, não como capacidade existente.

## Stack

Backend: Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic/Pydantic Settings, PostgreSQL, Psycopg 3, Alembic e HTTPX. Poetry gerencia dependências; Pytest e Ruff são dependências de desenvolvimento. O README cita Next.js, React, TypeScript e CSS Modules como tecnologias planejadas para o frontend.

## Referências

- [README](../README.md)
- [Arquitetura](02-architecture.md)
- [Status e roadmap](10-roadmap-and-status.md)
- [Auditoria do backend](03-backend.md)
