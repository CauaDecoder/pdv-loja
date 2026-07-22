# Spec 001: Redesign visual/UX do PDV com a Variante A

## Problem Statement

A operacao diaria da Loja da Basilica depende de um app Tkinter de PDV e estoque, mas a interface atual parece datada, com botoes, campos, buscas e modais pouco consistentes. Isso torna a Venda no caixa menos fluida, aumenta a carga cognitiva do operador e dificulta a confianca em telas sensiveis como importacao, backup, estoque e relatorios.

O usuario quer modernizar toda a experiencia visual e operacional do app sem trocar Tkinter, sem quebrar os fluxos existentes e preservando a identidade visual da Loja da Basilica. A Variante A do prototipo descartavel foi escolhida como direcao: uma experiencia "Command Center", com busca forte, carrinho claro e resumo/pagamento sempre visivel.

## Solution

Implementar um Visual operacional moderno em Tkinter, baseado na Variante A do prototipo HTML/CSS/JS. A entrega deve criar ou fortalecer um sistema visual compartilhado e aplicar essa linguagem a todas as abas principais: Venda, Vendas e correcoes, Estoque, Importacao, Relatorios e Configuracoes.

A Tela de venda deve priorizar Operacao orientada por teclado/leitor. A busca fica em destaque no topo, o carrinho ocupa a area central/esquerda, e o resumo de pagamento fica sempre visivel a direita ou embaixo quando a janela exigir responsividade. O app deve ter tema claro e tema escuro com escolha manual em Configuracoes, mantendo o tema claro como padrao.

AntiGravity implementa esta spec na camada visual/frontend. Mudancas de backend, persistencia e regras de negocio ficam fora desta spec, exceto pela exibicao de estados fornecidos pelos contratos de integracao.

## User Stories

1. As an operador de caixa, I want a modernized Tela de venda, so that I can operate the PDV with more confidence and less visual friction.
2. As an operador de caixa, I want the Busca de produto to be visually dominant and focused by default, so that I can start scanning or typing immediately.
3. As an operador de caixa, I want the carrinho to show product name, quantity, unit price, total and quick actions clearly, so that I can verify the sale before finishing it.
4. As an operador de caixa, I want the total and payment state to stay visible, so that I always know whether the sale is ready to finalize.
5. As an operador de caixa, I want Atalhos discretos near important controls, so that I can learn keyboard operation without visual clutter.
6. As an operador de caixa, I want keyboard focus to be visible, so that I can operate without the mouse safely.
7. As an operador de caixa, I want search ambiguity to be presented as a selectable list, so that I can choose the correct product using arrow keys, Enter or mouse.
8. As an operador de caixa, I want Alerta de estoque baixo to appear only when relevant, so that I notice low stock without turning the Tela de venda into a stock dashboard.
9. As an operador de caixa, I want payment options to be clear and compact, so that choosing Debito, Credito, Pix, Dinheiro or Mais de uma forma is fast.
10. As an operador de caixa, I want payment details to appear only when necessary, so that the screen does not show irrelevant fields.
11. As an operador de caixa, I want the finalization button to become visually strong only when the sale is valid, so that I do not finalize incomplete sales.
12. As an operador de caixa, I want the screen to return focus to Busca de produto after finalizing, so that the next Venda no caixa starts immediately.
13. As an operador de caixa, I want Vendas e correcoes to replace Ultimas vendas, so that I can find and correct finalized sales from one clear place.
14. As an operador de caixa, I want filters in Vendas e correcoes for number, date/period, payment method, responsible person and product, so that I can locate a sale quickly.
15. As an operador de caixa, I want sale correction actions to happen in a detail modal, so that sensitive changes are not made accidentally in a table row.
16. As an operador de caixa, I want Confirmacao de correcao to be visually strong, so that I understand when an action is sensitive.
17. As an operador de caixa, I want Cancelar venda to be presented as cancellation rather than deletion, so that I understand that history is preserved.
18. As an operador de caixa, I want Venda cancelada to have a distinct visual state, so that it is not confused with a valid sale.
19. As an operador de estoque, I want Estoque to feel modern but operationally dense, so that I can locate products and act on stock quickly.
20. As an operador de estoque, I want product status and low-stock states to be visually distinct, so that I can identify risks quickly.
21. As an operador de importacao, I want Importacao to be a guided flow, so that I understand the steps before changing product data.
22. As an operador de importacao, I want the import review to highlight impact and risk, so that I do not confirm dangerous changes blindly.
23. As a responsavel financeiro, I want Relatorios to separate financial closing from operational reporting, so that the period total is easier to trust.
24. As a responsavel financeiro, I want Vendas canceladas to appear separately, so that cancelled sales do not pollute financial movement but remain traceable.
25. As a responsavel pela loja, I want Backup e restauracao to live in Configuracoes, so that sensitive maintenance actions are not hidden in the Venda no caixa.
26. As a responsavel pela loja, I want restoring backup to use clear risk language and confirmation, so that accidental restoration is less likely.
27. As an operador, I want the app to use a consistent component system, so that every screen feels like the same product.
28. As an operador, I want light and dark themes to work predictably, so that the app can adapt to different visual preferences.
29. As an operador, I want the theme choice to be manual in Configuracoes, so that the app does not change unexpectedly.
30. As an operador, I want the app to work well at 1366x768 and above, so that it fits the typical shop computer.
31. As an operador, I want responsive grids and panels, so that smaller windows remain usable.
32. As an operador, I want modals to look polished and consistent, so that important tasks feel safe and professional.
33. As an operador, I want error and warning messages to be direct and visible, so that I understand what to fix.
34. As AntiGravity, I want a clear visual reference from the prototype, so that I can implement the chosen direction in Tkinter without reopening design questions.
35. As Codex, I want UI states to be explicit, so that backend services can expose the data and statuses the interface needs.

## Implementation Decisions

- Use the selected prototype direction: Variant A, "Command Center".
- Keep Tkinter as the production frontend technology.
- Keep navigation in top tabs, not a sidebar.
- Use these main tabs: Venda, Vendas e correcoes, Estoque, Importacao, Relatorios and Configuracoes.
- Implement a shared visual system for Tkinter components before rewriting individual screens.
- The shared visual system should cover buttons, inputs, search fields, cards, panels, tables, badges, page headers, modals, confirmation surfaces, empty states and keyboard focus.
- Preserve the Loja da Basilica identity through a refined green/gold palette, stronger contrast and more modern surfaces.
- Support light and dark themes through shared theme tokens.
- Theme selection is manual and lives in Configuracoes; the default is the light theme.
- The Tela de venda follows the Variant A layout: strong search area, central cart, right-side status/payment stack.
- On narrower layouts, the payment/status stack may move below the cart, but the search, cart and total must remain easy to access.
- Busca de produto should represent three states: idle/focused, single match added, and ambiguous results.
- Ambiguous results must be keyboard and mouse navigable.
- Alerta de estoque baixo appears when remaining stock is 5 or less and should be visually noticeable without dominating the sale.
- Payment controls should make the selected form visually obvious.
- Details for card, cash and split payment should be progressive, appearing only when relevant.
- Finalization should have disabled, ready and success/feedback states.
- Vendas e correcoes replaces the old Ultimas vendas surface.
- Correction and cancellation actions happen in a sale-detail modal or dedicated detail surface, not inline table editing.
- Sensitive actions use a visually distinct confirmation pattern.
- Importacao uses a guided stepper: file, mode, review, confirm.
- Relatorios visually separate financial movement from cancelled sales and operational reports.
- Configuracoes includes theme choice and Backup e restauracao.
- The prototype is a reference, not production code; do not copy its HTML/CSS structure directly into Tkinter without adapting to the app component system.

## Testing Decisions

- Visual/frontend validation should test external behavior rather than widget internals.
- The main seam is the composed Tkinter UI and shared component system, not individual low-level Tkinter calls.
- Manual validation is required for keyboard-only Venda no caixa, focus visibility, ambiguous search selection, payment readiness, modal behavior, theme switching and responsive layouts.
- Where feasible, lightweight smoke checks may instantiate screens/components to catch import errors and missing dependencies.
- Existing prior art includes tests for services and business rules; this spec should not add brittle visual snapshot tests unless a stable Tkinter testing approach exists.
- AntiGravity should validate all main tabs against the Variant A direction and the required states from the integration spec.
- Accessibility validation should include focus indicator, contrast, readable font sizes and clear warning/error messages.

## Out of Scope

- Replacing Tkinter with a web app or another frontend framework.
- Implementing backend persistence for Correcoes pos-venda.
- Implementing cancellation, stock adjustment or financial summary logic.
- Creating authentication, profiles, roles or passwords.
- Adding item to a finalized sale.
- Connecting the prototype to the real SQLite database.
- Changing the Loja da Basilica identity into a new brand.

## Further Notes

- This spec is intended for AntiGravity.
- Codex-owned backend behavior is described separately.
- Integration states and contracts are described in the shared integration spec.
- The prototype source of truth for visual direction is `docs/prototypes/ux-redesign/index.html?variant=A`.
