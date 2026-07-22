# 04 — [Codex] Persistir status e histórico de Correção pós-venda

**What to build:** Suporte persistente para status da venda e histórico de Correção pós-venda, preservando o registro original e auditando ações sensíveis.

**Blocked by:** 01 — [Codex] Criar contrato e base de serviço para Vendas e correções.

**Status:** ready-for-agent

- [ ] Vendas podem ser marcadas como válidas, corrigidas ou canceladas sem apagar histórico.
- [ ] Correções registram ação, responsável, data/hora, venda afetada, antes e depois.
- [ ] Migrações preservam compatibilidade com vendas existentes.
- [ ] Operações de correção têm base transacional para futuras mutações.
