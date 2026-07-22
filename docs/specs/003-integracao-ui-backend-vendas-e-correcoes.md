# Spec 003: Integracao UI/backend para Vendas e correcoes

## Problem Statement

O redesign visual e as novas regras de Correcao pos-venda dependem um do outro. AntiGravity precisa saber quais estados e dados a UI deve representar, enquanto Codex precisa saber quais contratos backend expor para que a UI modernizada nao dependa de detalhes internos do banco.

Sem uma spec compartilhada, ha risco de desalinhamento: o frontend pode desenhar estados que o backend nao entrega, e o backend pode implementar servicos que nao correspondem ao fluxo operacional da loja.

## Solution

Definir o contrato entre a UI modernizada e os servicos backend para Vendas e correcoes. Esta spec e compartilhada por AntiGravity e Codex. Ela descreve estados de venda, dados de listagem/detalhe, acoes de correcao, erros esperados, confirmacoes sensiveis e dependencias entre tickets.

Codex entrega os servicos e dados. AntiGravity representa os estados visualmente e pode usar mocks com o mesmo formato ate os servicos reais existirem.

## User Stories

1. As AntiGravity, I want a stable sale list contract, so that Vendas e correcoes can be built before backend details are final.
2. As AntiGravity, I want a stable sale detail contract, so that the correction modal can show items, payment, status and history consistently.
3. As AntiGravity, I want explicit sale status values, so that valid, corrected and cancelled sales have distinct visual states.
4. As AntiGravity, I want explicit action availability, so that the UI can disable correction actions that are not allowed.
5. As AntiGravity, I want predictable validation errors, so that the UI can show clear messages.
6. As AntiGravity, I want correction preview data when possible, so that the modal can explain stock and financial impact before confirmation.
7. As AntiGravity, I want mocks that match backend contracts, so that frontend work can proceed while Codex implements services.
8. As Codex, I want UI-required states documented, so that backend contracts expose the right information.
9. As Codex, I want clear correction action inputs, so that service functions can validate and persist changes.
10. As Codex, I want the UI to send responsible person with sensitive actions, so that correction history is auditable.
11. As Codex, I want Confirmacao de correcao handled by UI before calling mutation services, so that backend receives intentional actions.
12. As an operador de caixa, I want Vendas e correcoes to show sale number, time, responsible person, payment and status, so that I can locate the correct sale.
13. As an operador de caixa, I want filters for number, date/period, payment, responsible person and product, so that I can find a sale quickly.
14. As an operador de caixa, I want the sale detail to show original items and current valid state, so that I understand what will be corrected.
15. As an operador de caixa, I want to see correction history in the detail, so that I know whether the sale was already changed.
16. As an operador de caixa, I want the UI to warn me before cancelling a sale, so that I do not annul a sale accidentally.
17. As an operador de caixa, I want the UI to warn me before removing an item, so that I understand stock and financial impact.
18. As an operador de caixa, I want the UI to warn me before changing quantity, so that I understand the correction being made.
19. As an operador de caixa, I want successful corrections to refresh the sale list and detail, so that the screen reflects current state.
20. As an operador de caixa, I want cancelled sales to remain visible but separated in reports, so that history remains traceable.
21. As a responsavel financeiro, I want report contracts to separate valid financial movement and cancelled sales, so that closing is clean.
22. As a responsavel financeiro, I want corrected sales to indicate correction state, so that financial totals can be trusted.
23. As an operador de estoque, I want correction impact to reference stock movement where relevant, so that stock changes are explainable.
24. As a future implementer, I want integration tickets to declare whether they are Codex, AntiGravity or paired, so that work ownership is clear.
25. As a future implementer, I want backend dependencies explicit, so that AntiGravity can use mocks before real services exist.

## Implementation Decisions

- This spec is shared by AntiGravity and Codex.
- Use service-level contracts rather than direct UI access to database tables.
- The UI should treat sale status as explicit data, not infer it from missing rows or totals.
- Required sale statuses are valid, corrected and cancelled.
- Sale list rows should include sale number, period/date/time, responsible person, payment summary, total, status, item summary and available actions.
- Sale detail should include sale identity, status, responsible person, timestamps, payment details, item lines, correction history and available actions.
- Correction actions are alter payment, alter item quantity, remove item and cancel sale.
- Each sensitive action requires responsible person and should be invoked only after Confirmacao de correcao in the UI.
- Backend should return clear success state with updated sale detail or enough identity for the UI to refresh.
- Backend should return validation errors in a shape the UI can map to field-level or action-level messages.
- UI should support optimistic visual loading states, but should not assume mutation success before backend confirmation.
- AntiGravity may build with static mocks matching this contract while Codex implements real services.
- Integration tickets should declare dependencies: backend service ready, UI mock ready, or final wiring.
- Report contracts should expose valid financial movement separately from cancelled sales.
- Stock impact should be represented in correction preview/history where available.

Suggested contract shape from the prototype/spec discussion, expressed as decision data rather than production code:

```text
SaleListItem:
  sale_number
  period_id
  sold_at
  responsible
  payment_summary
  total
  status: valid | corrected | cancelled
  item_summary
  available_actions

SaleDetail:
  identity
  status
  payment
  items
  totals
  correction_history
  available_actions

CorrectionAction:
  alter_payment
  alter_item_quantity
  remove_item
  cancel_sale
```

## Testing Decisions

- Codex tests the service contracts at behavior level with temporary SQLite data.
- AntiGravity validates that the UI can represent every contract state using mocks.
- Integration validation should cover valid, corrected and cancelled sale states.
- Integration validation should cover action unavailable states, such as attempting to correct a cancelled sale.
- Integration validation should cover loading, success and validation-error states.
- Integration validation should cover report separation between financial movement and cancelled sales.
- UI tests should not depend on real SQLite data.
- Backend tests should not depend on Tkinter widgets.
- Final wiring should be manually checked through the app once both sides are implemented.

## Out of Scope

- Creating a third implementation owned by a separate agent.
- Changing the chosen Variant A visual direction.
- Adding authentication or roles.
- Adding item to a finalized sale.
- Replacing SQLite or Tkinter.
- Publishing tickets in this step.

## Further Notes

- This spec should be read by both AntiGravity and Codex.
- It is not a substitute for the AntiGravity visual spec or the Codex backend spec.
- It exists to keep the two workstreams aligned before tickets are created.
