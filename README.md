# Caixa Basilica

Aplicacao desktop de PDV e estoque da Loja da Basilica, construída em Python/Tkinter. A operacao atual usa SQLite local em um unico computador. O codigo da Central permanece disponivel, mas sua implantacao esta adiada.

## Instalacao e execucao

Ambiente validado: Python 3.12.10 no Windows. O Tkinter normalmente acompanha a instalacao do Python.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m app
# Central somente por ativacao explicita futura: python -m app --central
# servidor central: python -m app.server
```

## Instalador Windows

Para uso diário, instale pelo arquivo `Instalador-Caixa-Basilica-<versão>.exe` gerado em `installer/output/`. O instalador cria atalho no Menu Iniciar e, se selecionado, na Área de Trabalho. Depois, abra pelo ícone **Caixa Basílica**; não precisa de terminal nem comando.

Dados operacionais do programa instalado ficam em `%LOCALAPPDATA%\Loja da Basilica\`: banco, backups e relatórios. Atualizar ou desinstalar o aplicativo não apaga esses dados.

Para gerar instalador em computador de desenvolvimento com [uv](https://docs.astral.sh/uv/) e Inno Setup 6 instalados:

```powershell
.\installer\build_installer.ps1 -Version 1.0.0
```

Não coloque o banco em pasta compartilhada. Cada instalação mantém dados operacionais fora do código-fonte, em diretório local do usuário.

## Organizacao

```text
main.py                         entrypoint compativel
app/
|- __main__.py                  entrypoint para python -m app
|- database.py                  persistencia SQLite
|- paths.py                     caminhos operacionais centralizados
|- estoque/
|  |- painel.py                 manutencao e movimentacoes
|  |- dashboard.py              indicadores e graficos
|  |- calculos.py                regras de estoque
|  `- relatorio_estoque.py      exportacao da posicao
|- services/
|  |- backup_service.py         backup e restauracao SQLite
|  |- importacao_service.py     fachada da importacao
|  |- vendas_service.py         fachada incremental de vendas
|  |- estoque_service.py        fachada incremental de estoque
|  `- relatorios_service.py     fachada incremental de relatorios
`- ui/
   |- theme.py                  tokens e estilos visuais
   |- app_window.py             janela principal e telas legadas
   `- importacao_dialog.py      conferencia da importacao
data/
`- imports/                     planilhas e CSVs de entrada
scripts/
`- higienizar_produtos.py       conversor de exportacao Conta Azul
relatorios/                     planilhas geradas pelo PDV
```

O codigo da aplicacao fica integralmente no pacote `app`. O `main.py` raiz apenas delega ao entrypoint do pacote.

## Importacao de produtos

Use **Importar produtos**, selecione um arquivo CSV ou Excel e revise a tela de conferencia antes de confirmar.

Mapeamento Conta Azul:

- `Disponível` -> estoque vendavel
- `Custo Médio` -> custo unitario
- `Valor de Venda` -> preco de venda
- `Custo Total` -> somente conferencia financeira
- `Reservado` -> nao altera o estoque disponivel

A linha final `CUSTO TOTAL` nunca e importada como produto.

Para converter uma exportacao legada em `data/imports/`, execute:

```powershell
python -m scripts.higienizar_produtos
```

Modos disponiveis:

- **Atualizar estoque pelo Disponível**: ajusta produtos novos e existentes para o saldo informado.
- **Preservar estoque atual**: atualiza cadastro, preco e custo sem alterar saldos.
- **Inventário inicial**: permitido somente quando não existem produtos nem movimentações; cria o cadastro e o saldo inicial completo.

A conferencia mostra produtos lidos, insercoes, atualizacoes, ignorados, soma de Disponível, Custo Total da planilha, valores calculados, cadastros incompletos, estoques invalidos e duplicados. Se a diferenca entre o Custo Total informado e o valor a custo calculado superar R$ 0,05, o sistema alerta antes da gravacao.

## Valor a custo e valor a venda

Os indicadores financeiros sao separados:

- **Valor a custo** = `estoque × custo_unitario`
- **Valor a venda** = `estoque × preco`

Quando o custo nao esta cadastrado, o valor a custo conhecido exclui aquele produto e o custo ausente e sinalizado. O sistema nao presume custo zero nem estima custo como `preco × 0,6`. A dashboard, o painel e o relatorio de estoque identificam claramente cada valor.

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

Os testes cobrem schema v2, transacoes, idempotencia, importacao, reconciliacao de estoque, Vendas no caixa simples e mistas, Correcoes pos-venda, fechamento, relatorios XLSX e backup/restauracao.

## Recomendacoes futuras

- Extrair gradualmente caixa, historico e dialogos remanescentes de `app/ui/app_window.py`.
- Armazenar quantidade reservada em coluna propria.
- Agendar copia externa criptografada dos backups.
- Adicionar teste visual/manual documentado para os principais fluxos Tkinter.
