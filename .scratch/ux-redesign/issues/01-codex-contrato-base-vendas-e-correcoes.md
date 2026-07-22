# 01 — [Codex] Criar contrato e base de serviço para Vendas e correções

**What to build:** Uma fachada de serviço para Vendas e correções que permita listar vendas, abrir detalhe e representar estados `valid`, `corrected` e `cancelled`, ainda sem mutações completas. AntiGravity pode consumir ou mockar esse contrato.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] Existe um contrato de listagem de vendas com número, período/data/hora, responsável, pagamento, total, status, resumo de itens e ações disponíveis.
- [ ] Existe um contrato de detalhe da venda com identidade, status, pagamento, itens, totais, histórico de correções e ações disponíveis.
- [ ] Estados `valid`, `corrected` e `cancelled` são explícitos e não inferidos pela UI.
- [ ] Há testes de comportamento para listagem/detalhe usando dados SQLite temporários ou seam equivalente.
