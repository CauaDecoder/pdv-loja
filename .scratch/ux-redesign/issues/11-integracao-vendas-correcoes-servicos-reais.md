# 11 — [Integração] Ligar Vendas e correções UI aos serviços reais

**What to build:** Conectar a UI de Vendas e correções aos serviços reais de alteração de pagamento, alteração de quantidade, remoção de item e Cancelar venda.

**Blocked by:** 05 — [Codex] Implementar alteração de pagamento pós-venda; 06 — [Codex] Implementar alteração de quantidade e remoção de item; 07 — [Codex] Implementar Cancelar venda; 10 — [AntiGravity] Redesenhar Vendas e correções com mocks do contrato.

**Status:** ready-for-agent

- [ ] UI chama serviços reais para as quatro ações de Correção pós-venda.
- [ ] Confirmacao de correcao ocorre antes de mutações sensíveis.
- [ ] Sucesso atualiza lista e detalhe.
- [ ] Erros de validação aparecem com mensagem clara.
- [ ] Estados válido, corrigido e cancelado são representados corretamente.
