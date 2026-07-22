# UX Redesign Direction

Este documento consolida a direcao acordada para modernizar a experiencia frontend/UX do Caixa Basilica antes de escrever a spec e quebrar em tickets.

## Objetivo

Redesenhar a experiencia visual e operacional do app Tkinter de PDV e estoque para deixar a rotina da loja mais rapida, clara, segura e visualmente moderna, sem quebrar os fluxos existentes de venda, estoque, importacao, backup e relatorios.

## Fluxo principal

A melhoria deve otimizar primeiro a **Venda no caixa**. A tela de venda deve funcionar em ritmo de balcao: busca/leitor, carrinho, pagamento e finalizacao, com foco automatico e sem exigir mouse para o caminho comum.

O mouse continua disponivel como alternativa, mas a experiencia principal deve ser orientada por teclado/leitor.

## Decisoes de produto e UX

- Manter o app como desktop Tkinter nesta leva.
- Manter navegacao principal em abas no topo.
- Usar as abas principais: Venda, Vendas e correcoes, Estoque, Importacao, Relatorios e Configuracoes.
- Criar/fortalecer um sistema visual compartilhado para Tkinter antes de redesenhar tela por tela.
- Modernizar todas as telas na primeira leva, nao apenas a tela de venda.
- Preservar a identidade visual da Loja da Basilica, refinando verde/dourado, contraste, espacamento e estados visuais.
- Prever tema claro e tema escuro, com escolha manual em Configuracoes e tema claro como padrao.
- Projetar para 1366x768 ou maior como alvo principal, com telas e grids responsivos.
- Incluir acessibilidade operacional desde o inicio: foco de teclado evidente, contraste adequado, legibilidade e mensagens claras.

## Venda no caixa

A tela de venda deve ser organizada em tres areas fixas:

1. Busca no topo, sempre pronta para teclado/leitor.
2. Carrinho no centro/esquerda, com itens, quantidade, preco e remocao rapida.
3. Resumo/pagamento a direita ou embaixo, com total muito visivel, forma de pagamento e finalizacao.

Comportamentos acordados:

- Quando a busca encontrar um unico produto confiavel, adicionar 1 unidade diretamente ao carrinho.
- Quando houver multiplos resultados, mostrar uma lista selecionavel por setas, Enter e mouse.
- Adicionar o mesmo produto novamente aumenta a quantidade.
- A quantidade padrao ao adicionar produto e 1.
- Nao mostrar estoque como informacao permanente na venda.
- Mostrar alerta de estoque baixo quando restarem 5 unidades ou menos, por exemplo "5 produtos restantes".
- Manter formas atuais de pagamento: Debito, Credito, Pix, Dinheiro e Mais de uma forma.
- Mostrar detalhes de pagamento apenas quando necessario, como bandeira/parcelas ou valor recebido/troco.
- Habilitar finalizacao apenas quando carrinho e pagamento estiverem validos.
- Depois de finalizar, limpar a venda e voltar foco para busca.
- Exibir atalhos de teclado discretos, sem competir com as informacoes principais.

## Correcao pos-venda

A tela atual de "Ultimas vendas" deve evoluir para **Vendas e correcoes**, sem criar uma segunda tela com proposito parecido.

Essa tela deve permitir localizar vendas por:

- Numero da venda.
- Data/periodo.
- Forma de pagamento.
- Responsavel.
- Produto.

A lista serve para localizar vendas; a correcao deve acontecer em uma tela/modal de detalhe da venda.

A primeira versao da correcao pos-venda deve incluir:

- Alterar forma de pagamento.
- Alterar quantidade de item.
- Remover item da venda.
- Cancelar venda inteira.

Adicionar novo item a uma venda finalizada fica fora da primeira versao. Quando necessario, a loja deve registrar uma nova venda complementar.

Correcoes devem preservar historico, registrando o que mudou, quando mudou e quem executou a acao. Acoes sensiveis devem exigir confirmacao forte, mesmo sem perfis/senhas nesta etapa.

Cancelar venda nao deve apagar historico. A linguagem do sistema deve ser "Cancelar venda", nao "Excluir venda".

Cancelamentos e correcoes devem ajustar estoque automaticamente:

- Cancelar venda devolve itens ao estoque.
- Alterar/remover item aplica a diferenca no estoque.

## Relatorios

Relatorios devem separar fechamento financeiro de relatorios operacionais.

O fechamento financeiro deve mostrar apenas a movimentacao financeira relevante do periodo. Vendas canceladas nao entram no financeiro, mas devem aparecer em uma area separada para rastreabilidade.

Correcoes que alterem valor ou pagamento devem refletir no resultado liquido correto e indicar que houve correcao.

## Estoque

Estoque continua como modulo proprio. A Venda no caixa so recebe alertas essenciais de estoque baixo.

A modernizacao da tela de Estoque deve priorizar gestao operacional de produtos:

- Localizar produto.
- Entender status.
- Ajustar entrada, perda e inventario.
- Visualizar baixo estoque.
- Confiar nos numeros.

Dashboard e indicadores continuam existindo, mas devem apoiar a operacao, nao dominar a experiencia.

## Importacao

A importacao de produtos deve ser redesenhada como fluxo guiado em etapas:

1. Selecionar arquivo.
2. Escolher modo de importacao.
3. Revisar conferencia.
4. Confirmar gravacao.

A conferencia deve destacar impactos e riscos antes de gravar:

- Produtos novos.
- Produtos atualizados.
- Estoque que sera alterado.
- Itens ignorados.
- Duplicados.
- Cadastros incompletos.
- Diferenca de custo total.
- Resumo final do que sera gravado.

## Configuracoes e manutencao

Backup e restauracao devem sair do rodape da venda e virar area propria de manutencao/configuracoes.

Criar backup pode ser simples. Restaurar backup e uma acao sensivel e deve ter contexto, confirmacao e linguagem clara de risco.

Configuracoes tambem devem conter a escolha manual de tema claro/escuro.

## Prototipo descartavel

Antes da spec, deve ser criado um prototipo descartavel em HTML/CSS/JS local.

O prototipo deve usar dados ficticios realistas e cobrir navegacao completa com as principais telas:

- Venda.
- Vendas e correcoes.
- Estoque.
- Importacao.
- Relatorios.
- Configuracoes.

A tela de Venda deve ser a mais detalhada, pois define a linguagem visual e interativa do restante do app.

Cenarios obrigatorios do prototipo:

- Venda rapida com busca/leitor adicionando produto direto.
- Busca com multiplos resultados e selecao por teclado/mouse.
- Alerta de estoque baixo com "5 produtos restantes".
- Carrinho com alteracao de quantidade e remocao.
- Pagamento com forma selecionada e finalizacao habilitada.
- Vendas e correcoes com detalhe, alteracao de pagamento, alteracao de quantidade, remocao de item e Cancelar venda.
- Venda cancelada separada no relatorio.
- Importacao em etapas com conferencia de impactos.
- Configuracoes com tema claro/escuro e backup/restauracao.

## Divisao entre agentes

AntiGravity implementara a parte visual/frontend:

- Telas.
- Componentes.
- Layout.
- Tema claro/escuro.
- Modais.
- Responsividade.
- Acabamento visual e interativo.

Codex implementara backend/funcionalidade:

- Modelo de dados para correcoes.
- Cancelamento de venda.
- Rastreabilidade.
- Ajuste automatico de estoque.
- Relatorios corretos.
- Regras de negocio.

Os tickets devem ser separados por responsabilidade sempre que possivel. Quando uma entrega precisar das duas partes, a spec deve explicitar contratos, estados de UI e dependencias.

Contratos importantes:

- Codex entrega contratos de dados/servicos, como listar vendas, corrigir item, cancelar venda, listar vendas canceladas e gerar relatorio liquido.
- AntiGravity representa estados de UI, como venda pronta para finalizar, busca ambigua, estoque baixo, correcao pendente, confirmacao sensivel e venda cancelada.
- Tickets de integracao devem declarar dependencias e, quando necessario, usar mocks ate o backend estar pronto.

## Criterios de sucesso

- Uma venda comum pode ser feita sem mouse.
- O operador sempre sabe se a venda esta pronta para finalizar.
- Busca com um unico produto e rapida; busca ambigua e navegavel por teclado.
- Acoes sensiveis exigem confirmacao.
- Correcoes pos-venda preservam historico.
- Cancelar venda ajusta estoque e nao entra no financeiro.
- Vendas canceladas aparecem separadas para rastreabilidade.
- Todas as telas principais usam o mesmo sistema visual.
- Tema claro e escuro funcionam de forma previsivel.
- Foco de teclado, contraste e mensagens de erro sao claros.

## Nao-objetivos da primeira leva

- Trocar Tkinter por web/app novo.
- Criar autenticacao, perfis ou senhas.
- Adicionar item em venda ja finalizada.
- Usar banco real no prototipo.
- Refazer regras fiscais/contabeis alem do necessario para correcao, cancelamento e relatorios.
- Criar integracao externa de backup em nuvem.
- Mudar a identidade da Loja da Basilica.
