# 06 — [Codex] Implementar alteração de quantidade e remoção de item

**What to build:** Permitir corrigir quantidade ou remover item de venda finalizada, ajustando estoque pela diferença e preservando histórico.

**Blocked by:** 04 — [Codex] Persistir status e histórico de Correção pós-venda.

**Status:** ready-for-agent

- [ ] Quantidade de item pode ser alterada para valor válido.
- [ ] Remoção de item restaura o estoque correspondente.
- [ ] Alteração de quantidade ajusta estoque somente pela diferença.
- [ ] Histórico registra antes/depois, responsável e data/hora.
- [ ] Quantidade negativa, venda inexistente ou venda cancelada são rejeitadas.
