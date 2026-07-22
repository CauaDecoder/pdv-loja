# Caixa Basilica

Aplicacao de PDV e estoque para a operacao diaria da Loja da Basilica.

## Language

**Venda no caixa**:
Fluxo principal de atendimento no balcao, em que o operador busca produtos, monta o carrinho, escolhe a forma de pagamento e finaliza a venda.
_Avoid_: venda, pedido

**PDV**:
Sistema usado no ponto de venda da loja para registrar vendas, apoiar pagamentos e manter a operacao diaria fluindo.
_Avoid_: caixa, sistema

**Operacao orientada por teclado/leitor**:
Modo de uso em que a Venda no caixa deve poder avancar principalmente por leitor de codigo de barras e teclado, mantendo o mouse como alternativa.
_Avoid_: interface rapida, modo caixa

**Busca de produto**:
Etapa da Venda no caixa em que o operador encontra um item por codigo de barras, codigo interno ou nome. Quando houver um unico resultado confiavel, o produto deve entrar direto no carrinho; quando houver multiplos resultados, o operador escolhe pela lista.
_Avoid_: pesquisa, filtro de produtos

**Quantidade no carrinho**:
Numero de unidades de um produto dentro da Venda no caixa. A quantidade padrao ao adicionar um produto e 1; adicionar o mesmo produto novamente deve aumentar essa quantidade.
_Avoid_: unidade, qtd

**Alerta de estoque baixo**:
Aviso exibido na Venda no caixa quando o produto adicionado ou selecionado tem 5 unidades ou menos restantes. O alerta informa quantos produtos restam, sem transformar a tela de venda em uma tela de gestao de estoque.
_Avoid_: estoque na venda, dashboard de estoque

**Tela de venda**:
Interface principal da Venda no caixa, organizada em busca de produto, carrinho e resumo de pagamento. A tela deve manter a busca pronta para teclado/leitor e deixar total, itens e finalizacao sempre claros.
_Avoid_: pagina de venda, tela inicial

**Atalho discreto**:
Indicacao visual curta de uma tecla de acao, exibida perto do controle correspondente sem competir com as informacoes principais da Venda no caixa.
_Avoid_: ajuda de teclado, dica visual

**Correcao pos-venda**:
Fluxo usado para corrigir uma venda ja finalizada, incluindo forma de pagamento, quantidade, produtos ou exclusao da venda quando ela foi registrada errado.
_Avoid_: editar venda, ajuste de historico

**Confirmacao de correcao**:
Confirmacao explicita exigida antes de aplicar uma Correcao pos-venda sensivel, como cancelar venda, remover produto ou alterar pagamento. A confirmacao nao substitui perfis de acesso, mas deve reduzir erros e deixar o responsavel pela acao claro.
_Avoid_: senha, permissao

**Cancelar venda**:
Tipo de Correcao pos-venda que anula uma venda finalizada sem apagar seu historico. A linguagem do sistema deve usar cancelar venda em vez de excluir venda.
_Avoid_: excluir venda, apagar venda

**Venda cancelada**:
Venda finalizada que foi anulada por uma Correcao pos-venda. Ela nao deve entrar na movimentacao financeira do periodo, mas deve permanecer visivel em uma area separada para rastreabilidade.
_Avoid_: venda excluida, venda apagada

**Vendas e correcoes**:
Tela de consulta e acao sobre vendas ja finalizadas, incluindo visualizacao, Correcao pos-venda e Cancelar venda. Ela substitui a ideia limitada de "ultimas vendas" para evitar duas telas com quase o mesmo proposito.
_Avoid_: ultimas vendas, historico de vendas

**Visual operacional moderno**:
Estilo visual leve, claro e agradavel para uso diario no PDV, com componentes bem acabados, modais consistentes e hierarquia forte sem sacrificar densidade operacional.
_Avoid_: visual antigo, app datado, tela enfeitada

**Identidade visual refinada**:
Evolucao da paleta atual da Loja da Basilica, preservando verde e dourado como sinais de identidade, mas com contraste, espacamento e estados visuais mais modernos.
_Avoid_: nova marca, tema antigo

**Acessibilidade operacional**:
Qualidade da interface que permite operar o PDV com legibilidade, contraste adequado, foco de teclado evidente e mensagens de erro claras durante a rotina da loja.
_Avoid_: acessibilidade visual, polimento

**Backup e restauracao**:
Area de manutencao do app dedicada a criar backup e restaurar o banco de dados local. Restaurar backup e uma acao sensivel e deve ter contexto, confirmacao e linguagem clara de risco.
_Avoid_: botoes de backup, rodape de backup
