# 07 — [Codex] Implementar Cancelar venda

**What to build:** Permitir cancelar uma venda sem apagar histórico, devolvendo estoque e bloqueando novas correções inválidas.

**Blocked by:** 04 — [Codex] Persistir status e histórico de Correção pós-venda.

**Status:** ready-for-agent

- [ ] Cancelar venda marca a venda como cancelada sem deletá-la.
- [ ] Todos os itens vendidos são devolvidos ao estoque.
- [ ] Movimentações de estoque referenciam a venda cancelada.
- [ ] Venda cancelada fica fora da movimentação financeira.
- [ ] Correções posteriores inválidas em venda cancelada são bloqueadas.
