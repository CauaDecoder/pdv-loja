# Caixa Basilica

Aplicacao desktop de PDV e estoque da Loja da Basilica, construída em Python/Tkinter com banco SQLite local.

## Instalacao e execucao

Requer Python 3.10+ no Windows. O Tkinter normalmente acompanha a instalacao do Python.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

O banco principal fica em `data/loja.db`. As dependencias declaradas sao `openpyxl`, `matplotlib` e `pytest`.

## Organizacao

```text
main.py                         ponto de entrada compativel
database.py                     persistencia SQLite e consultas existentes
app/
|- main.py                      ponto de entrada do pacote
|- services/
|  |- backup_service.py         backup e restauracao SQLite
|  |- importacao_service.py     fachada da importacao
|  |- vendas_service.py         fachada incremental de vendas
|  |- estoque_service.py        fachada incremental de estoque
|  `- relatorios_service.py     fachada incremental de relatorios
`- ui/
   |- app_window.py             janela principal e telas legadas
   `- importacao_dialog.py      conferencia da importacao
estoque/
|- painel.py                    manutencao e movimentacoes
|- dashboard.py                 indicadores e graficos
|- calculos.py                  regras de estoque
`- relatorio_estoque.py         exportacao da posicao
```

A refatoracao e incremental: imports antigos continuam funcionando, enquanto novas regras e telas passam a viver em modulos menores. O `main.py` raiz agora apenas cria `CaixaApp` e inicia o loop da interface.

## Importacao de produtos

Use **Importar produtos**, selecione um arquivo CSV ou Excel e revise a tela de conferencia antes de confirmar.

Mapeamento Conta Azul:

- `Disponível` -> estoque vendavel
- `Custo Médio` -> custo unitario
- `Valor de Venda` -> preco de venda
- `Custo Total` -> somente conferencia financeira
- `Reservado` -> nao altera o estoque disponivel

A linha final `CUSTO TOTAL` nunca e importada como produto.

Modos disponiveis:

- **Atualizar estoque pelo Disponível**: ajusta produtos novos e existentes para o saldo informado.
- **Preservar estoque atual**: atualiza cadastro, preco e custo sem alterar saldos.
- **Inventário inicial**: aplica o saldo informado somente a produtos novos e preserva produtos existentes.

A conferencia mostra produtos lidos, insercoes, atualizacoes, ignorados, soma de Disponível, Custo Total da planilha, valores calculados, cadastros incompletos, estoques invalidos e duplicados. Se a diferenca entre o Custo Total informado e o valor a custo calculado superar R$ 0,05, o sistema alerta antes da gravacao.

## Valor a custo e valor a venda

Os indicadores financeiros sao separados:

- **Valor a custo** = `estoque × custo_unitario`
- **Valor a venda** = `estoque × preco`

Quando o custo nao esta cadastrado, o valor a custo daquele produto e zero. O sistema nao estima mais custo como `preco × 0,6`. A dashboard, o painel e o relatorio de estoque identificam claramente cada valor.

## Backup e restauracao

No rodape da tela de venda:

1. **Criar backup** gera um arquivo com data, hora e microssegundos em `backups/`.
2. **Restaurar backup** valida o arquivo SQLite selecionado.
3. Antes da restauracao, o sistema cria automaticamente um backup de seguranca do banco atual.
4. Ao concluir, os paineis e o periodo atual sao recarregados.

Mantenha copias da pasta `backups/` também fora do computador da loja.

## Testes

```powershell
python -m pytest -q
```

Os testes cobrem mapeamento Conta Azul, descarte da linha `CUSTO TOTAL`, importacao e modos de estoque, baixa por venda, valores a custo/venda, entrada, perda, inventario, status e backup/restauracao.

## Recomendacoes futuras

- Extrair gradualmente caixa, historico e dialogos remanescentes de `app/ui/app_window.py`.
- Armazenar quantidade reservada em coluna propria.
- Trocar valores monetarios internos para `Decimal` em uma migracao controlada.
- Agendar copia externa criptografada dos backups.
- Adicionar teste visual/manual documentado para os principais fluxos Tkinter.
