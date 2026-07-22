# Validação final do redesign — issue #20

Este roteiro fecha a validação de integração depois das entregas de Venda no
caixa, Vendas e correções, Estoque, Importação, Relatórios e Configurações.

## Verificação automatizada

Executar no Windows com Python 3.10+:

```powershell
py -3 -m pytest -q
```

A suíte deve validar, em conjunto, o fluxo de teclado da Venda no caixa, as
quatro Correções pós-venda, a recomposição de estoque, o financeiro líquido, a
separação de Vendas canceladas e a propagação do tema pelas seis telas.

## Roteiro manual obrigatório

Executar em 1366x768 e em uma resolução maior, primeiro no tema claro e depois
no escuro. Registrar evidência e resultado de cada bloco.

### Venda no caixa sem mouse

- Pressionar F2, ler ou digitar um código único e confirmar com Enter.
- Repetir o mesmo código e confirmar que a Quantidade no carrinho aumenta.
- Em uma Busca de produto ambígua, usar seta para baixo, setas de navegação e
  Enter para escolher o item.
- Pressionar F4, navegar por Tab até Pix, acionar com Espaço e finalizar com F8.
- Confirmar o feedback de sucesso e o retorno do foco à Busca de produto.
- Repetir com Débito, Crédito, Dinheiro e Mais de uma forma; conferir foco,
  Enter/Espaço, Escape, validações e detalhes progressivos dos pagamentos.

### Vendas e correções, estoque e relatórios

- Localizar uma venda pelos filtros e abrir seu detalhe.
- Alterar pagamento e quantidade, remover um item e conferir responsável,
  confirmação, mensagem de sucesso e histórico da Correção pós-venda.
- Cancelar venda; confirmar que ela continua rastreável, não aceita nova
  correção e que o estoque é recomposto.
- Abrir Relatórios; conferir o financeiro líquido sem a Venda cancelada e a
  seção separada de canceladas com os valores atuais após correções.

### Consistência visual e acessibilidade operacional

- Percorrer Venda, Vendas e correções, Estoque, Importação, Relatórios e
  Configurações nos dois temas, inclusive criando conteúdo depois da troca.
- Conferir contraste de texto, estados disabled/hover/selecionado, alertas de
  estoque baixo, badges e tabelas.
- Navegar por Tab/Shift+Tab e confirmar anel de foco visível em campos, botões,
  tabelas e controles de modal.
- Abrir modais de pagamento, correção, importação e restauração; conferir
  título, risco, ação principal, cancelamento por Escape e mensagens de erro.
- Redimensionar a janela e verificar que busca, carrinho, total e ações
  principais continuam acessíveis sem sobreposição ou corte.

## Registro do handoff

- Verificação automatizada: executada pelo Codex.
- Validação visual/manual: pendente de execução e aprovação pelo AntiGravity.
- Em caso de falha visual, corrigir somente a camada de UI, preservar os
  contratos dos serviços e repetir a suíte completa antes da aprovação.
