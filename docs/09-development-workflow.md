# Fluxo de desenvolvimento

O fluxo aprovado é trabalhar em etapas isoladas, preservando alterações existentes e deixando integração no repositório sob autorização explícita.

1. **Verifique alterações locais antes de trocar de branch.** `git status --short` mostra arquivos modificados e não rastreados; preserve o trabalho existente.
2. **Atualize referências remotas e a main local.** `git fetch origin` atualiza referências; `git switch main` seleciona a branch principal; `git pull --ff-only origin main` atualiza sem criar merge commit.
3. **Crie uma branch por etapa, partindo da main atualizada.** Exemplo: `git switch -c feature/nome-da-etapa`. Não desenvolva diretamente em `main`.
4. **Implemente uma etapa de cada vez** e execute testes/lint pertinentes ao escopo.
5. **Revise mudanças e whitespace.** Use `git diff`, confira a lista de arquivos alterados e execute `git diff --check`.
   **Observação:** arquivos novos ainda não rastreados não aparecem no `git diff` convencional e precisam ser examinados separadamente.
6. **Revise o resultado completo antes de integração.** Commit, push, PR ou merge exigem autorização explícita; não são consequência automática da conclusão da implementação.

Comandos de validação no backend, a partir de `backend/`:

```powershell
poetry run ruff check app tests alembic
poetry run pytest -v
```

Comandos Git citados são parte do fluxo aprovado; não foram executados como parte desta documentação, exceto as consultas somente de leitura necessárias à validação final da tarefa.
