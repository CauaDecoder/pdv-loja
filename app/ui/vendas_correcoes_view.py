"""
View e modais para a aba Vendas e correções (Issue #15).

Implementa a interface de consulta de vendas finalizadas, filtros completos por
número, período, pagamento, status, responsável e produto, além do modal de
detalhes da venda com histórico de auditoria e ações de correção pós-venda.
"""

from __future__ import annotations

import math
from datetime import date, datetime
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from app.contracts import valor_para_centavos
from app.payments import (
    CARD_BRANDS,
    CARD_INSTALLMENTS,
    PAYMENT_METHODS,
    parse_currency,
)
from app.runtime import (
    database as database_runtime,
    filtered_report,
    sales as vendas_service,
)
from app.services.vendas_service import resolver_periodo_filtro
from app.ui.components import (
    BaseModal,
    Card,
    DataTable,
    LabeledField,
    PageHeader,
    SectionHeader,
    StatusBadge,
    StyledEntry,
    action_button,
    bind_escape_to_close,
    bind_mousewheel_tree,
    confirmar_acao_sensivel,
)
from app.ui.theme import FONTES, TEMA_ATUAL, moeda

def ler_quantidade(valor: str) -> int:
    """Converte quantidade informada pela UI com mensagem operacional clara."""
    try:
        return int(valor.strip())
    except (AttributeError, TypeError, ValueError) as erro:
        raise ValueError(
            "Informe a nova quantidade em unidades inteiras."
        ) from erro


def ler_valor_monetario_opcional(valor: str, campo: str) -> float | None:
    """Converte um valor monetario opcional aceitando virgula decimal."""
    texto = (valor or "").strip()
    if not texto:
        return None
    try:
        numero = parse_currency(texto)
    except ValueError as erro:
        raise ValueError(f"{campo} deve ser um valor monetario valido.") from erro
    if not math.isfinite(numero):
        raise ValueError(f"{campo} deve ser um valor monetario valido.")
    return numero


def montar_parcelas_mistas_corrigidas(
    parcelas: list[dict[str, Any]],
    valores: list[str],
    recebidos: list[str],
    total_centavos: int,
) -> list[dict[str, Any]]:
    """Converte o editor de parcelas no contrato validado pelo domínio."""
    if len(parcelas) < 2 or not (
        len(parcelas) == len(valores) == len(recebidos)
    ):
        raise ValueError("A Venda mista deve manter duas ou mais parcelas.")
    resultado = []
    for parcela, valor_texto, recebido_texto in zip(
        parcelas, valores, recebidos
    ):
        valor = ler_valor_monetario_opcional(valor_texto, "Valor da parcela")
        if valor is None or valor <= 0:
            raise ValueError("Cada parcela deve ter valor maior que zero.")
        valor_centavos = valor_para_centavos(valor)
        forma = parcela["method"]
        recebido_centavos = None
        troco_centavos = None
        if forma == "Dinheiro":
            recebido = ler_valor_monetario_opcional(
                recebido_texto, "Valor recebido"
            )
            if recebido is None:
                raise ValueError("Informe o valor recebido em Dinheiro.")
            recebido_centavos = valor_para_centavos(recebido)
            if recebido_centavos < valor_centavos:
                raise ValueError(
                    "Valor recebido deve ser maior ou igual à parcela em Dinheiro."
                )
            troco_centavos = recebido_centavos - valor_centavos
        resultado.append(
            {
                "forma": forma,
                "destino_id": int(parcela["destination_id"]),
                "valor_centavos": valor_centavos,
                "detalhe": parcela.get("detail", ""),
                "valor_recebido_centavos": recebido_centavos,
                "troco_centavos": troco_centavos,
            }
        )
    if sum(parcela["valor_centavos"] for parcela in resultado) != total_centavos:
        raise ValueError(
            f"A soma das parcelas deve ser {moeda(total_centavos / 100)}."
        )
    return resultado


class VendasCorrecoesView(tk.Frame):
    """View principal da aba Vendas e correções com filtros e tabela."""

    def __init__(self, parent: tk.Widget, on_sale_updated: Callable | None = None, autoload: bool = True, loader=None):
        super().__init__(parent, bg=TEMA_ATUAL["fundo"], padx=18, pady=16)
        self._on_sale_updated = on_sale_updated
        self._loader = loader

        # Variáveis dos Filtros
        self._var_num_venda = tk.StringVar()
        self._var_periodo_temporal = tk.StringVar(value="Este mês")
        self._var_data_inicio = tk.StringVar()
        self._var_data_fim = tk.StringVar()
        self._var_pagamento = tk.StringVar(value="Todas")
        self._var_status = tk.StringVar(value="Todos")
        self._var_responsavel = tk.StringVar()
        self._var_produto = tk.StringVar()

        self._vendas_carregadas: list[dict[str, Any]] = []
        self._resumo_atual: dict[str, Any] = {}

        self._build_ui()
        if autoload:
            self.solicitar_atualizacao()

    def _build_ui(self):
        """Monta a estrutura visual da aba."""
        for w in self.winfo_children():
            w.destroy()

        PageHeader(
            self,
            "Vendas e correções",
            "Consulte vendas finalizadas e realize correções pós-venda ou cancelamentos com histórico.",
            "Atualizar",
            self.solicitar_atualizacao,
        ).pack(fill="x", pady=(0, 12))

        # --- FILTROS ---
        self._build_filtros_card()
        self._build_resumo_card()

        # --- TABELA DE VENDAS ---
        self._build_tabela_card()

    def _build_filtros_card(self):
        card_filtros = Card(self, padding=14)
        card_filtros.pack(fill="x", pady=(0, 12))

        grid = tk.Frame(card_filtros, bg=TEMA_ATUAL["surface"])
        grid.pack(fill="x")

        for coluna in range(5):
            grid.columnconfigure(coluna, weight=1)
        box_periodo = tk.Frame(grid, bg=TEMA_ATUAL["surface"])
        box_periodo.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        tk.Label(box_periodo, text="Período", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        seletor = ttk.Combobox(box_periodo, textvariable=self._var_periodo_temporal, values=("Esta semana", "Este mês", "Este ano", "Personalizado", "Todo o histórico"), state="readonly")
        seletor.pack(fill="x", ipady=3)
        seletor.bind("<<ComboboxSelected>>", self._ao_mudar_periodo)
        self._var_intervalo_resolvido = tk.StringVar()
        tk.Label(grid, textvariable=self._var_intervalo_resolvido, bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["corpo"]).grid(row=0, column=1, sticky="sw", padx=(0, 8))
        self._frame_datas_personalizadas = tk.Frame(grid, bg=TEMA_ATUAL["surface"])
        self._frame_datas_personalizadas.grid(row=0, column=2, sticky="ew", padx=(0, 8))
        tk.Label(self._frame_datas_personalizadas, text="De / Até (DD/MM/AAAA)", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        self._entrada_data_inicio = StyledEntry(self._frame_datas_personalizadas, textvariable=self._var_data_inicio, width=10)
        self._entrada_data_inicio.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self._entrada_data_fim = StyledEntry(self._frame_datas_personalizadas, textvariable=self._var_data_fim, width=10)
        self._entrada_data_fim.pack(side="left", fill="x", expand=True)
        self._var_erro_data = tk.StringVar()
        tk.Label(grid, textvariable=self._var_erro_data, bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["danger"], font=FONTES["label_sm"]).grid(row=1, column=2, sticky="w")
        botoes = tk.Frame(grid, bg=TEMA_ATUAL["surface"])
        botoes.grid(row=0, column=4, sticky="se")
        action_button(botoes, text="Filtrar", command=self.solicitar_atualizacao, variant="primary").pack(side="left", padx=(0, 4))
        action_button(botoes, text="Limpar filtros", command=self._limpar_filtros, variant="ghost").pack(side="left")

        box_numero = tk.Frame(grid, bg=TEMA_ATUAL["surface"])
        box_numero.grid(row=2, column=0, sticky="ew", padx=(0, 8), pady=(10, 0))
        tk.Label(box_numero, text="Venda nº", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        StyledEntry(box_numero, textvariable=self._var_num_venda).pack(fill="x")
        box_produto = tk.Frame(grid, bg=TEMA_ATUAL["surface"])
        box_produto.grid(row=2, column=1, sticky="ew", padx=(0, 8), pady=(10, 0))
        tk.Label(box_produto, text="Produto", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        StyledEntry(box_produto, textvariable=self._var_produto).pack(fill="x")
        box_responsavel = tk.Frame(grid, bg=TEMA_ATUAL["surface"])
        box_responsavel.grid(row=2, column=2, sticky="ew", padx=(0, 8), pady=(10, 0))
        tk.Label(box_responsavel, text="Responsável", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        StyledEntry(box_responsavel, textvariable=self._var_responsavel).pack(fill="x")
        box_pgto = tk.Frame(grid, bg=TEMA_ATUAL["surface"])
        box_pgto.grid(row=2, column=3, sticky="ew", padx=(0, 8), pady=(10, 0))
        tk.Label(box_pgto, text="Pagamento", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        ttk.Combobox(
            box_pgto,
            textvariable=self._var_pagamento,
            values=("Todas", *PAYMENT_METHODS),
            state="readonly",
            width=10,
        ).pack(fill="x", ipady=3)

        box_status = tk.Frame(grid, bg=TEMA_ATUAL["surface"])
        box_status.grid(row=2, column=4, sticky="ew", pady=(10, 0))
        tk.Label(box_status, text="Status", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        ttk.Combobox(box_status, textvariable=self._var_status, values=["Todos", "Válida", "Corrigida", "Cancelada"], state="readonly", width=10).pack(fill="x", ipady=3)

        self._atualizar_campos_periodo()

    def _build_resumo_card(self) -> None:
        """Mostra resultado financeiro completo, independente da lista limitada."""
        resumo = Card(self, padding=12)
        resumo.pack(fill="x", pady=(0, 12))
        resumo.columnconfigure(0, weight=2)
        resumo.columnconfigure(1, weight=1)
        resumo.columnconfigure(2, weight=1)
        self._var_total_periodo = tk.StringVar(value="R$ 0,00")
        self._var_vendas_validas = tk.StringVar(value="0 vendas válidas")
        self._var_canceladas = tk.StringVar(value="0 canceladas fora total")
        self._card_resumo = resumo
        for coluna, titulo, variavel, fonte, cor in (
            (0, "TOTAL VENDIDO NO PERÍODO", self._var_total_periodo, FONTES["numero_card"], TEMA_ATUAL["primary"]),
            (1, "VENDAS VÁLIDAS", self._var_vendas_validas, FONTES["corpo_bold"], TEMA_ATUAL["texto"]),
            (2, "CANCELADAS", self._var_canceladas, FONTES["corpo_bold"], TEMA_ATUAL["texto_suave"]),
        ):
            bloco = tk.Frame(resumo, bg=TEMA_ATUAL["surface"])
            bloco.grid(row=0, column=coluna, sticky="ew", padx=(0, 16) if coluna < 2 else (0, 0))
            tk.Label(bloco, text=titulo, bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
            tk.Label(bloco, textvariable=variavel, bg=TEMA_ATUAL["surface"], fg=cor, font=fonte).pack(anchor="w", pady=(3, 0))
        action_button(resumo, text="Gerar relatório", command=self._gerar_relatorio_periodo, variant="secondary").grid(row=0, column=3, sticky="e")

    def _build_tabela_card(self):
        self._card_tabela = Card(self, padding=0)
        self._card_tabela.pack(fill="both", expand=True)

        tabela_wrap = tk.Frame(self._card_tabela, bg=TEMA_ATUAL["surface"])
        tabela_wrap.pack(fill="both", expand=True)
        columns = ("venda", "horario", "resumo", "pagamento", "total", "status")
        self._tree_vendas = DataTable(
            tabela_wrap,
            columns=columns,
            headings={
                "venda": "VENDA",
                "horario": "HORÁRIO",
                "resumo": "RESUMO",
                "pagamento": "PAGAMENTO",
                "total": "TOTAL",
                "status": "STATUS",
            },
            widths={
                "venda": 90,
                "horario": 150,
                "resumo": 430,
                "pagamento": 220,
                "total": 120,
                "status": 120,
            },
            height=14,
        )
        self._tree_vendas.column("venda", anchor="center", stretch=False)
        self._tree_vendas.column("horario", anchor="w", stretch=False)
        self._tree_vendas.column("resumo", anchor="w", stretch=True)
        self._tree_vendas.column("pagamento", anchor="w", stretch=True)
        self._tree_vendas.column("total", anchor="e", stretch=False)
        self._tree_vendas.column("status", anchor="center", stretch=False)
        scroll = ttk.Scrollbar(tabela_wrap, orient="vertical", command=self._tree_vendas.yview)
        self._tree_vendas.configure(yscrollcommand=scroll.set)
        self._tree_vendas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self._tree_vendas.bind("<Double-1>", self._abrir_detalhe_selecionado)
        self._tree_vendas.bind("<Return>", self._abrir_detalhe_selecionado)
        self._indices_por_item: dict[str, int] = {}

        # Frame de Ações da Tabela
        self._bar_acoes = tk.Frame(self, bg=TEMA_ATUAL["fundo"])
        self._bar_acoes.pack(fill="x", pady=(10, 0))
        self._var_estado_lista = tk.StringVar(value="Carregando Vendas…")
        tk.Label(
            self._bar_acoes,
            textvariable=self._var_estado_lista,
            bg=TEMA_ATUAL["fundo"],
            fg=TEMA_ATUAL["texto_suave"],
            font=FONTES["corpo"],
        ).pack(side="left", padx=(8, 0))

        action_button(
            self._bar_acoes,
            text="🔄 Atualizar Lista",
            command=self.solicitar_atualizacao,
            variant="secondary",
        ).pack(side="right", padx=(0, 8))
        action_button(
            self._bar_acoes,
            text="Ver detalhes",
            command=self._abrir_detalhe_selecionado,
            variant="primary",
        ).pack(side="right", padx=(0, 8))

    def _ao_mudar_periodo(self, _event=None) -> None:
        self._atualizar_campos_periodo()
        if self._var_periodo_temporal.get() != "Personalizado":
            self.solicitar_atualizacao()

    def _atualizar_campos_periodo(self) -> None:
        personalizado = self._var_periodo_temporal.get() == "Personalizado"
        if personalizado:
            self._frame_datas_personalizadas.grid()
            self._var_intervalo_resolvido.set("Informe intervalo")
            self._entrada_data_inicio.bind("<Return>", lambda _event: self.solicitar_atualizacao())
            self._entrada_data_fim.bind("<Return>", lambda _event: self.solicitar_atualizacao())
            return
        self._frame_datas_personalizadas.grid_remove()
        inicio, fim = resolver_periodo_filtro(self._var_periodo_temporal.get(), date.today())
        texto = "Todo histórico" if inicio is None else f"{datetime.fromisoformat(inicio):%d/%m/%Y} até {datetime.fromisoformat(fim):%d/%m/%Y}"
        self._var_intervalo_resolvido.set(texto)

    def _montar_filtros(self) -> dict[str, Any] | None:
        """Lê e valida controles sem executar consulta."""
        filtros = {}
        self._var_erro_data.set("")
        if self._var_num_venda.get().strip():
            filtros["num_venda"] = self._var_num_venda.get().strip()
        if self._var_periodo_temporal.get() == "Personalizado":
            inicio, fim = self._var_data_inicio.get().strip(), self._var_data_fim.get().strip()
            if not inicio or not fim:
                self._var_erro_data.set("Informe data inicial e final.")
                (self._entrada_data_inicio if not inicio else self._entrada_data_fim).focus_set()
                return None
            try:
                inicio_iso = datetime.strptime(inicio, "%d/%m/%Y").date().isoformat()
                fim_iso = datetime.strptime(fim, "%d/%m/%Y").date().isoformat()
            except ValueError:
                self._var_erro_data.set("Use DD/MM/AAAA.")
                self._entrada_data_inicio.focus_set()
                return None
            if inicio_iso > fim_iso:
                self._var_erro_data.set("Data inicial deve ser anterior à final.")
                self._entrada_data_inicio.focus_set()
                return None
            filtros.update(data_inicio=inicio_iso, data_fim=fim_iso)
        else:
            inicio, fim = resolver_periodo_filtro(self._var_periodo_temporal.get(), date.today())
            if inicio:
                filtros.update(data_inicio=inicio, data_fim=fim)
        if self._var_pagamento.get() != "Todas":
            filtros["pagamento"] = self._var_pagamento.get()
        if self._var_responsavel.get().strip():
            filtros["responsavel"] = self._var_responsavel.get().strip()
        if self._var_produto.get().strip():
            filtros["produto"] = self._var_produto.get().strip()

        st = self._var_status.get()
        if st == "Válida":
            filtros["status"] = "valid"
        elif st == "Corrigida":
            filtros["status"] = "corrected"
        elif st == "Cancelada":
            filtros["status"] = "cancelled"

        return filtros

    def atualizar(self, resultado: dict[str, Any] | list[dict] | None = None):
        """Compatibilidade para atualizações antigas e renderização da consulta."""
        filtros = self._montar_filtros()
        if filtros is None:
            return
        if resultado is None and self._loader:
            self._loader(filtros, self._renderizar_consulta)
            return
        if resultado is None:
            self.configure(cursor="watch")
            self.update_idletasks()
            try:
                resultado = vendas_service.consultar_vendas_correcoes(filtros)
            except Exception as erro:
                resultado = {"sales": [], "summary": {}}
                messagebox.showerror(
                    "Nao foi possivel carregar as vendas",
                    str(erro),
                    parent=self,
                )
            finally:
                self.configure(cursor="")
        self._renderizar_consulta(resultado)

    def _renderizar_consulta(self, resultado: dict[str, Any] | list[dict] | None) -> None:
        """Atualiza tabela e resumo a partir da resposta do serviço."""
        if isinstance(resultado, list):
            resultado = {"sales": resultado, "summary": {"matched_sales": len(resultado), "shown_sales": len(resultado)}}
        resultado = resultado or {"sales": [], "summary": {}}
        vendas = list(resultado.get("sales", []))
        resumo = resultado.get("summary", {})
        self._resumo_atual = dict(resumo)
        total_centavos = int(resumo.get("total_centavos", 0))
        validas = int(resumo.get("financial_sales", 0))
        canceladas = int(resumo.get("cancelled_sales", 0))
        self._var_total_periodo.set(moeda(total_centavos / 100))
        self._var_vendas_validas.set(f"{validas} venda{'s' if validas != 1 else ''}")
        self._var_canceladas.set(f"{canceladas} fora total")

        self._vendas_carregadas = vendas
        self._indices_por_item.clear()
        for item_id in self._tree_vendas.get_children():
            self._tree_vendas.delete(item_id)

        for idx, v in enumerate(vendas):
            s_code = v.get("status", "valid")
            sold_at = v.get("sold_at", {})
            dt_str = f"{sold_at.get('date', '')} {sold_at.get('time', '')}".strip()
            resumo_text = f"{v.get('item_summary', {}).get('label', '')} - {v.get('responsible', '')}"
            if s_code == "valid":
                status_text = "Válida"
            elif s_code == "corrected":
                status_text = "Corrigida"
            else:
                status_text = "Cancelada"
            item_id = self._tree_vendas.insert(
                "",
                "end",
                values=(
                    f"#{v.get('sale_number', 0):03d}",
                    dt_str,
                    resumo_text,
                    v.get("payment_summary", ""),
                    moeda(float(v.get("total", 0))),
                    status_text,
                ),
                tags=("even" if idx % 2 == 0 else "odd",),
            )
            self._indices_por_item[item_id] = idx

        if not vendas:
            self._var_estado_lista.set("Nenhuma Venda encontrada | Total: R$ 0,00")
            return
        total = moeda(int(resumo.get("total_centavos", 0)) / 100)
        texto = f"Vendas válidas: {resumo.get('financial_sales', len(vendas))} | Total do período: {total} | Canceladas fora do total: {resumo.get('cancelled_sales', 0)}"
        if resumo.get("truncated"):
            texto += f" | Exibindo {resumo.get('shown_sales', len(vendas))} de {resumo.get('matched_sales', len(vendas))}"
        self._var_estado_lista.set(texto)
        primeira = self._tree_vendas.get_children()[0]
        self._tree_vendas.selection_set(primeira)
        self._tree_vendas.focus(primeira)
        self._tree_vendas.see(primeira)

    def solicitar_atualizacao(self) -> None:
        self.atualizar()

    def _gerar_relatorio_periodo(self) -> None:
        """Exporta XLSX financeiro usando intervalo e filtros financeiros ativos."""
        filtros = self._montar_filtros()
        if filtros is None:
            return
        inicio, fim = filtros.get("data_inicio"), filtros.get("data_fim")
        if not inicio or not fim:
            messagebox.showerror(
                "Relatório indisponível",
                "Escolha Esta semana, Este mês, Este ano ou período personalizado.",
                parent=self,
            )
            return
        pasta = filedialog.askdirectory(title="Selecione pasta para relatório de vendas")
        if not pasta:
            return
        status = filtros.get("status")
        try:
            caminho = filtered_report(
                {
                    "data_inicial": inicio,
                    "data_final": fim,
                    "forma": filtros.get("pagamento"),
                    "status": status or "all",
                    "incluir_canceladas": status == "cancelled",
                },
                Path(pasta) / "relatorio_vendas_periodo.xlsx",
            )
        except Exception as erro:
            messagebox.showerror("Erro no relatório", str(erro), parent=self)
            return
        messagebox.showinfo("Relatório gerado", f"Relatório salvo em:\n{caminho}", parent=self)

    def _limpar_filtros(self):
        self._var_num_venda.set("")
        self._var_periodo_temporal.set("Este mês")
        self._var_data_inicio.set("")
        self._var_data_fim.set("")
        self._var_pagamento.set("Todas")
        self._var_status.set("Todos")
        self._var_responsavel.set("")
        self._var_produto.set("")
        self._atualizar_campos_periodo()
        self.atualizar()

    def _abrir_detalhe(self, idx):
        if idx < 0 or idx >= len(self._vendas_carregadas):
            return

        item_resumo = self._vendas_carregadas[idx]
        periodo_id = item_resumo.get("period_id", 1)
        num_venda = item_resumo.get("sale_number", 1)

        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            detalhe = vendas_service.obter_detalhe_venda(periodo_id, num_venda)
        except Exception as erro:
            messagebox.showerror(
                "Nao foi possivel abrir a venda",
                str(erro),
                parent=self,
            )
            return
        finally:
            self.configure(cursor="")
        if not detalhe:
            messagebox.showerror(
                "Venda nao encontrada",
                "A venda selecionada nao existe mais no banco de dados.",
                parent=self,
            )
            self.atualizar()
            return

        VendaDetailModal(self, detalhe, on_updated=self._apos_venda_atualizada)

    def _abrir_detalhe_selecionado(self, _event=None):
        selecao = self._tree_vendas.selection()
        if not selecao:
            return
        idx = self._indices_por_item.get(selecao[0])
        if idx is not None:
            self._abrir_detalhe(idx)

    def _apos_venda_atualizada(self) -> None:
        self.atualizar()
        if self._on_sale_updated:
            self._on_sale_updated()


class VendaDetailModal(tk.Toplevel):
    """Modal seguro de detalhes e correções pós-venda."""

    def __init__(self, parent: tk.Widget, detalhe: dict[str, Any], on_updated: Callable | None = None):
        super().__init__(parent)
        self._detalhe = detalhe
        self._on_updated = on_updated

        num = detalhe["identity"]["sale_number"]
        per = detalhe["identity"]["period_id"]

        self.title(f"Detalhes da Venda #{num:03d}")
        self.geometry("820x680")
        self.minsize(740, 560)
        self.configure(bg=TEMA_ATUAL["fundo"])
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        bind_escape_to_close(self)

        self._build_ui()

    def _build_ui(self):
        for w in self.winfo_children():
            w.destroy()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        det = self._detalhe
        num = det["identity"]["sale_number"]
        per = det["identity"]["period_id"]
        status = det.get("status", "valid")
        sold_at = det.get("timestamps", {})
        dt_str = f"{sold_at.get('date', '')} às {sold_at.get('time', '')}"

        # Page Header inside Dialog
        hdr_frame = tk.Frame(self, bg=TEMA_ATUAL["fundo"], padx=18, pady=14)
        hdr_frame.grid(row=0, column=0, sticky="ew")

        left_hdr = tk.Frame(hdr_frame, bg=TEMA_ATUAL["fundo"])
        left_hdr.pack(side="left")

        tk.Label(
            left_hdr,
            text=f"Venda #{num:03d} (Período {per:02d})",
            bg=TEMA_ATUAL["fundo"],
            fg=TEMA_ATUAL["texto"],
            font=FONTES["titulo"],
        ).pack(anchor="w")

        tk.Label(
            left_hdr,
            text=f"Registrada em {dt_str} por {det.get('responsible', 'N/A')}",
            bg=TEMA_ATUAL["fundo"],
            fg=TEMA_ATUAL["texto_suave"],
            font=FONTES["corpo"],
        ).pack(anchor="w", pady=(2, 0))

        right_hdr = tk.Frame(hdr_frame, bg=TEMA_ATUAL["fundo"])
        right_hdr.pack(side="right")

        status_text_map = {"valid": "VÁLIDA", "corrected": "CORRIGIDA", "cancelled": "CANCELADA"}
        badge_txt = status_text_map.get(status, status.upper())
        StatusBadge(right_hdr, badge_txt).pack(side="right", padx=(10, 0))
        action_button(right_hdr, text="Fechar [Esc]", command=self.destroy, variant="ghost").pack(side="right")

        # Área rolável isolada: canvas e barra ocupam exclusivamente linha central.
        scroll_host = tk.Frame(self, bg=TEMA_ATUAL["fundo"])
        scroll_host.grid(row=1, column=0, sticky="nsew")
        scroll_host.grid_columnconfigure(0, weight=1)
        scroll_host.grid_rowconfigure(0, weight=1)
        canvas = tk.Canvas(scroll_host, bg=TEMA_ATUAL["fundo"], highlightthickness=0)
        scroll = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)

        content = tk.Frame(canvas, bg=TEMA_ATUAL["fundo"], padx=18, pady=4)
        content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas_window = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

        canvas.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        pag_info = det.get("payment", {})
        metodo = pag_info.get("method", "Desconhecido")
        detalhe_met = pag_info.get("detail", "")
        txt_pag = f"{metodo} | {detalhe_met}" if detalhe_met else metodo
        totals = det.get("totals", {})
        acoes = set(det.get("available_actions", []))

        # 1. KPI Cards
        kpi_frame = tk.Frame(content, bg=TEMA_ATUAL["fundo"])
        kpi_frame.pack(fill="x", pady=(0, 12))
        kpi_frame.columnconfigure(0, weight=1, uniform="kpi")
        kpi_frame.columnconfigure(1, weight=1, uniform="kpi")
        kpi_frame.columnconfigure(2, weight=1, uniform="kpi")
        
        c1 = Card(kpi_frame, padding=12)
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        tk.Label(c1, text="Total válido", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        tk.Label(c1, text=moeda(float(totals.get('total', 0))), bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["primary"], font=FONTES["numero_card"]).pack(anchor="w", pady=(4,0))
        
        c2 = Card(kpi_frame, padding=12)
        c2.grid(row=0, column=1, sticky="nsew", padx=(6, 6))
        tk.Label(c2, text="Pagamento", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        tk.Label(c2, text=txt_pag, bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto"], font=FONTES["corpo_bold"]).pack(anchor="w", pady=(4,0))
        
        c3 = Card(kpi_frame, padding=12)
        c3.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        tk.Label(c3, text="Status", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        
        if status == "valid":
            StatusBadge(c3, "Válida", "OK").pack(anchor="w", pady=(4,0))
        elif status == "corrected":
            StatusBadge(c3, "Corrigida", "ALERTA").pack(anchor="w", pady=(4,0))
        else:
            StatusBadge(c3, "Cancelada", "CRITICO").pack(anchor="w", pady=(4,0))

        dados = Card(content, padding=12)
        dados.pack(fill="x", pady=(0, 12))
        SectionHeader(dados, "Dados da venda", "Dados efetivos; Período da Loja permanece vinculado.").pack(fill="x", pady=(0, 8))
        linha_data = tk.Frame(dados, bg=TEMA_ATUAL["surface"])
        linha_data.pack(fill="x", pady=(0, 8))
        tk.Label(linha_data, text=f"Data da Venda no caixa: {sold_at.get('date', '')}", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto"], font=FONTES["corpo_bold"]).pack(side="left")
        botao_data = action_button(linha_data, text="Alterar data", command=self._alterar_data, variant="ghost")
        botao_data.pack(side="right")
        if "alter_sale_date" not in acoes:
            botao_data.configure(state="disabled")
        linha_pagamento = tk.Frame(dados, bg=TEMA_ATUAL["surface"])
        linha_pagamento.pack(fill="x")
        tk.Label(linha_pagamento, text=f"Pagamento: {txt_pag}", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto"], font=FONTES["corpo"], justify="left", wraplength=500).pack(side="left", fill="x", expand=True)
        botao_pagamento = action_button(linha_pagamento, text="Alterar pagamento", command=self._alterar_pagamento, variant="ghost")
        botao_pagamento.pack(side="right", padx=(8, 0))
        if "alter_payment" not in acoes:
            botao_pagamento.configure(state="disabled")

        # 2. Tabela de Itens
        card_itens = Card(content, padding=12)
        card_itens.pack(fill="x", pady=(0, 12))

        SectionHeader(card_itens, "Itens da venda", "Quantidade e valores da Venda no caixa.").pack(fill="x", pady=(0, 6))
            
        for item in det.get("items", []):
            row = tk.Frame(
                card_itens,
                bg=TEMA_ATUAL["surface"],
                pady=6,
                padx=8,
                borderwidth=0,
                highlightthickness=1,
                highlightbackground=TEMA_ATUAL["border_soft"],
            )
            row.pack(fill="x")
            row.columnconfigure(0, weight=1)
            
            line_id = item.get("line_id", 0)
            
            tk.Label(row, text=f"{item.get('code', '')} — {item.get('name', '')}", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto"], font=FONTES["corpo_bold"], justify="left", wraplength=560).grid(row=0, column=0, sticky="ew")
            tk.Label(row, text=f"Quantidade: {item.get('quantity', 0)}   |   Unitário: {moeda(float(item.get('unit_price', 0)))}   |   Subtotal: {moeda(float(item.get('subtotal', 0)))}", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["corpo"]).grid(row=1, column=0, sticky="w", pady=(4, 0))
            
            acts = tk.Frame(row, bg=TEMA_ATUAL["surface"])
            acts.grid(row=2, column=0, sticky="w", pady=(8, 0))
            
            btn_alt = action_button(acts, text="Alterar", command=lambda l=line_id: self._alterar_quantidade(l), variant="secondary")
            btn_alt.pack(side="left", padx=(0, 4))
            
            btn_rem = action_button(acts, text="Remover", command=lambda l=line_id: self._remover_item(l), variant="danger")
            btn_rem.pack(side="left")
            
            if "alter_item_quantity" not in acoes:
                btn_alt.configure(state="disabled")
            if "remove_item" not in acoes:
                btn_rem.configure(state="disabled")

        # 3. Histórico
        card_hist = Card(content, padding=12)
        card_hist.pack(fill="x", pady=(0, 12))

        SectionHeader(card_hist, "Histórico de Auditoria & Correções", "Rastreabilidade de alterações pós-venda.").pack(anchor="w", fill="x", pady=(0, 6))

        historico = det.get("correction_history", [])
        if not historico:
            tk.Label(card_hist, text="Nenhuma correção registrada nesta venda.", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["corpo"]).pack(anchor="w")
        else:
            for h in historico:
                h_box = tk.Frame(card_hist, bg=TEMA_ATUAL["surface_2"], padx=8, pady=6)
                h_box.pack(fill="x", pady=(0, 4))
                tk.Label(
                    h_box,
                    text=self._texto_historico(h),
                    bg=TEMA_ATUAL["surface_2"],
                    fg=TEMA_ATUAL["texto"],
                    font=FONTES["corpo"],
                    justify="left",
                ).pack(anchor="w")

        # 4. Warning Panel
        if status != "cancelled":
            warn_panel = Card(content, padding=12)
            warn_panel.pack(fill="x", pady=(0, 12))
            warn_panel.configure(bg=TEMA_ATUAL["warning_soft"])
            
            tk.Label(warn_panel, text="⚠️ Confirmação de correção", bg=TEMA_ATUAL["warning_soft"], fg=TEMA_ATUAL["warning"], font=FONTES["corpo_bold"]).pack(anchor="w")
            tk.Label(warn_panel, text="As ações abaixo alteram o fluxo de caixa ou estoque da loja. Todas as correções são registradas.", bg=TEMA_ATUAL["warning_soft"], fg=TEMA_ATUAL["warning"]).pack(anchor="w")

        # Footer Frame
        footer = tk.Frame(self, bg=TEMA_ATUAL["fundo"], padx=18, pady=14)
        footer.grid(row=2, column=0, sticky="ew")
        
        if status != "cancelled":
            btn_cancelar = action_button(footer, text="Cancelar venda", command=self._cancelar_venda, variant="danger")
            btn_cancelar.pack(side="right", padx=(0, 8))
            if "cancel_sale" not in acoes:
                btn_cancelar.configure(state="disabled")
                
        action_button(footer, text="Fechar", command=self.destroy, variant="ghost").pack(side="right")
        bind_mousewheel_tree(content, canvas)

    # --- AÇÕES DO MODAL DE DETALHES ---

    def _identidade_venda(self) -> tuple[int, int]:
        identidade = self._detalhe["identity"]
        return identidade["period_id"], identidade["sale_number"]

    def _texto_historico(self, historico: dict[str, Any]) -> str:
        """Formata auditoria em linguagem operacional, sem estruturas cruas."""
        nomes = {
            "alter_sale_date": "Data alterada",
            "alter_payment": "Pagamento alterado",
            "alter_item_quantity": "Quantidade alterada",
            "remove_item": "Item removido",
            "cancel_sale": "Venda cancelada",
        }
        antes, depois = historico.get("before", {}), historico.get("after", {})
        titulo = nomes.get(historico.get("action"), "Correção registrada")
        if isinstance(antes, dict) and isinstance(depois, dict) and "date" in antes:
            antigo = datetime.fromisoformat(antes["date"]).strftime("%d/%m/%Y")
            novo = datetime.fromisoformat(depois.get("date", "")).strftime("%d/%m/%Y")
            mudanca = f"{antigo} → {novo}"
        else:
            mudanca = historico.get("note") or "Alteração registrada no histórico."
        criado = historico.get("created_at", "")
        try:
            criado = datetime.fromisoformat(criado).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            pass
        return f"{titulo}\n{mudanca}\nPor {historico.get('responsible', '')}, em {criado}"

    def _alterar_data(self) -> None:
        """Pede e confirma Data da Venda no caixa antes da correção auditada."""
        periodo_id, num_venda = self._identidade_venda()
        atual = self._detalhe.get("timestamps", {}).get("date", "")
        dialogo = BaseModal(
            self,
            title="Alterar data da venda",
            subtitle="A venda continuará no mesmo Período da Loja.",
            width=560,
            height=430,
        )
        dialogo.minsize(500, 400)
        card = Card(dialogo.body_frame, padding=14)
        card.pack(fill="both", expand=True)
        tk.Label(card, text="Data atual", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        tk.Label(card, text=atual, bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto"], font=FONTES["corpo_bold"]).pack(anchor="w", pady=(2, 10))
        nova_data = tk.StringVar()
        responsavel = tk.StringVar()
        tk.Label(card, text="Nova data (DD/MM/AAAA) *", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w", pady=(10, 0))
        entrada_data = StyledEntry(card, textvariable=nova_data)
        entrada_data.pack(fill="x", ipady=4)
        tk.Label(card, text="Responsável pela correção *", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w", pady=(10, 0))
        StyledEntry(card, textvariable=responsavel).pack(fill="x", ipady=4, pady=(0, 8))
        tk.Label(
            card,
            text="Correção ficará registrada no histórico. Data futura não permitida.",
            bg=TEMA_ATUAL["surface"],
            fg=TEMA_ATUAL["texto_suave"],
            font=FONTES["corpo"],
            justify="left",
            wraplength=480,
        ).pack(anchor="w")
        entrada_data.focus_set()

        def continuar() -> None:
            if not responsavel.get().strip():
                messagebox.showerror("Campo obrigatório", "Informe o responsável pela correção.", parent=dialogo)
                return
            try:
                novo_iso = datetime.strptime(nova_data.get().strip(), "%d/%m/%Y").date()
            except ValueError:
                messagebox.showerror("Data inválida", "Use DD/MM/AAAA.", parent=dialogo)
                entrada_data.focus_set()
                return
            if novo_iso > date.today():
                messagebox.showerror("Data inválida", "A Data da Venda no caixa não pode estar no futuro.", parent=dialogo)
                return
            novo_exibicao = novo_iso.strftime("%d/%m/%Y")
            self._confirmar_correcao(
                parent=dialogo,
                titulo="Confirmar alteração de data",
                risco=(f"Alterar a data da Venda #{num_venda:03d} de {atual} para {novo_exibicao}?\n\n"
                       f"A venda continuará vinculada ao Período {periodo_id:02d}.\nA alteração ficará registrada no histórico."),
                corrigir=lambda: vendas_service.alterar_data_venda(periodo_id, num_venda, novo_exibicao, responsavel=responsavel.get().strip(), observacao="Alterada via tela de Vendas e correções"),
                titulo_erro="Não foi possível alterar a data",
                titulo_sucesso="Data atualizada",
                mensagem_sucesso="A Data da Venda no caixa foi alterada com sucesso.",
                fechar_ao_concluir=dialogo,
            )

        action_button(dialogo.footer_frame, text="Continuar", command=continuar, variant="primary").pack(side="right")
        action_button(dialogo.footer_frame, text="Cancelar", command=dialogo.close, variant="ghost").pack(side="right", padx=(0, 8))

    def _executar_correcao(
        self,
        corrigir: Callable[[], dict[str, Any]],
        *,
        titulo_erro: str,
        titulo_sucesso: str,
        mensagem_sucesso: str,
        fechar_ao_concluir: tk.Toplevel | None = None,
    ) -> None:
        """Executa servico real, representa loading e atualiza detalhe e lista."""
        origem = fechar_ao_concluir or self
        origem.configure(cursor="watch")
        origem.update_idletasks()
        try:
            novo_detalhe = corrigir()
        except Exception as erro:
            messagebox.showerror(titulo_erro, str(erro), parent=origem)
            return
        finally:
            if origem.winfo_exists():
                origem.configure(cursor="")

        self._detalhe = novo_detalhe
        if fechar_ao_concluir and fechar_ao_concluir.winfo_exists():
            fechar_ao_concluir.after_idle(fechar_ao_concluir.destroy)
        self._build_ui()
        if self._on_updated:
            self._on_updated()
        messagebox.showinfo(titulo_sucesso, mensagem_sucesso, parent=self)

    def _confirmar_correcao(
        self,
        *,
        parent: tk.Widget,
        titulo: str,
        risco: str,
        corrigir: Callable[[], dict[str, Any]],
        titulo_erro: str,
        titulo_sucesso: str,
        mensagem_sucesso: str,
        fechar_ao_concluir: tk.Toplevel | None = None,
        badge_type: str = "ALERTA",
    ) -> tk.Toplevel:
        confirmacao: tk.Toplevel

        def executar() -> None:
            confirmacao.configure(cursor="watch")
            confirmacao.btn_confirm.configure(
                state="disabled",
                text="Processando...",
            )
            confirmacao.update_idletasks()
            self._executar_correcao(
                corrigir,
                titulo_erro=titulo_erro,
                titulo_sucesso=titulo_sucesso,
                mensagem_sucesso=mensagem_sucesso,
                fechar_ao_concluir=fechar_ao_concluir,
            )

        confirmacao = confirmar_acao_sensivel(
            parent=parent,
            title=titulo,
            risk_description=risco,
            confirm_label="Confirmar correção",
            badge_type=badge_type,
            on_confirm=executar,
        )
        return confirmacao

    def _pedir_responsavel(
        self,
        *,
        titulo: str,
        instrucao: str,
        continuar: Callable[[str], None],
    ) -> None:
        dialogo = BaseModal(self, title=titulo, subtitle=instrucao, width=460, height=260)
        card = Card(dialogo.body_frame, padding=14)
        card.pack(fill="both", expand=True)
        variavel = tk.StringVar()
        tk.Label(
            card,
            text="Responsável pela correção *",
            bg=TEMA_ATUAL["surface"],
            fg=TEMA_ATUAL["texto_suave"],
            font=FONTES["label_sm"],
        ).pack(anchor="w")
        entrada = StyledEntry(card, textvariable=variavel)
        entrada.pack(fill="x", ipady=5, pady=(4, 0))
        entrada.focus_set()

        def avancar() -> None:
            responsavel = variavel.get().strip()
            if not responsavel:
                messagebox.showerror(
                    "Campo Obrigatório",
                    "Informe o responsável pela correção.",
                    parent=dialogo,
                )
                return
            dialogo.close()
            continuar(responsavel)

        action_button(
            dialogo.footer_frame,
            text="Continuar",
            command=avancar,
            variant="primary",
        ).pack(side="right")
        action_button(
            dialogo.footer_frame,
            text="Voltar",
            command=dialogo.close,
            variant="ghost",
        ).pack(side="right", padx=(0, 8))

    def _pedir_parcelas_mistas(
        self,
        total_centavos: int,
        continuar: Callable[[list[dict[str, Any]]], None],
        parcelas: list[dict[str, Any]] | None = None,
    ) -> None:
        """Edita a distribuição existente antes de corrigir itens."""
        parcelas = list(
            parcelas
            or self._detalhe.get("payment", {}).get("installments", [])
        )
        if len(parcelas) < 2:
            raise ValueError("Parcelas da Venda mista não foram encontradas.")
        dialogo = BaseModal(
            self,
            title="Redistribuir parcelas",
            subtitle=f"Novo total da Venda: {moeda(total_centavos / 100)}",
            width=560,
            height=min(620, 250 + len(parcelas) * 105),
        )
        corpo = tk.Frame(dialogo.body_frame, bg=TEMA_ATUAL["surface"])
        corpo.pack(fill="both", expand=True)
        valores: list[tk.StringVar] = []
        recebidos: list[tk.StringVar] = []
        for parcela in parcelas:
            linha = tk.Frame(corpo, bg=TEMA_ATUAL["surface"])
            linha.pack(fill="x", pady=(0, 10))
            destino = parcela.get("destination", "")
            tk.Label(
                linha,
                text=f"{parcela['method']} | {destino}",
                bg=TEMA_ATUAL["surface"],
                fg=TEMA_ATUAL["texto"],
                font=FONTES["label_sm"],
            ).pack(anchor="w")
            campos = tk.Frame(linha, bg=TEMA_ATUAL["surface"])
            campos.pack(fill="x", pady=(4, 0))
            valor_var = tk.StringVar(
                value=f"{int(parcela['value_centavos']) / 100:.2f}".replace(".", ",")
            )
            recebido_atual = parcela.get("received_centavos")
            recebido_var = tk.StringVar(
                value=(
                    ""
                    if recebido_atual is None
                    else f"{int(recebido_atual) / 100:.2f}".replace(".", ",")
                )
            )
            valores.append(valor_var)
            recebidos.append(recebido_var)
            StyledEntry(campos, textvariable=valor_var).pack(
                side="left", fill="x", expand=True
            )
            if parcela["method"] == "Dinheiro":
                StyledEntry(campos, textvariable=recebido_var).pack(
                    side="left", fill="x", expand=True, padx=(8, 0)
                )

        def confirmar() -> None:
            try:
                novas = montar_parcelas_mistas_corrigidas(
                    parcelas,
                    [valor.get() for valor in valores],
                    [recebido.get() for recebido in recebidos],
                    total_centavos,
                )
            except ValueError as erro:
                messagebox.showerror(
                    "Parcelas inválidas", str(erro), parent=dialogo
                )
                return
            dialogo.close()
            continuar(novas)

        action_button(
            dialogo.footer_frame,
            text="Continuar",
            command=confirmar,
            variant="primary",
        ).pack(side="right")
        action_button(
            dialogo.footer_frame,
            text="Cancelar",
            command=dialogo.close,
            variant="ghost",
        ).pack(side="right", padx=(0, 8))

    def _parcelas_iniciais_mistas(
        self, total_centavos: int
    ) -> list[dict[str, Any]]:
        destinos = [dict(destino) for destino in database_runtime.listar_destinos_financeiros()]
        parcelas = []
        valores = (total_centavos // 2, total_centavos - total_centavos // 2)
        for forma, valor in zip(("Pix", "Dinheiro"), valores):
            destino = next(
                (
                    item
                    for item in destinos
                    if item.get("ativo", 1)
                    and forma in str(item.get("formas", "")).split(",")
                ),
                None,
            )
            if destino is None:
                raise ValueError(
                    f"Configure um Destino financeiro ativo para {forma}."
                )
            parcelas.append(
                {
                    "method": forma,
                    "destination_id": int(destino["id"]),
                    "destination": destino["nome"],
                    "value_centavos": valor,
                    "detail": "",
                    "received_centavos": valor if forma == "Dinheiro" else None,
                    "change_centavos": 0 if forma == "Dinheiro" else None,
                }
            )
        return parcelas

    def _alterar_pagamento(self):
        """Abre o sub-diálogo para alterar o pagamento da venda usando BaseModal."""
        det = self._detalhe
        per, num = self._identidade_venda()

        dialogo = BaseModal(
            self,
            title=f"Alterar pagamento - Venda #{num:03d}",
            subtitle="Defina a nova forma de pagamento e o responsável pela alteração.",
            width=480,
            height=460,
        )

        card = Card(dialogo.body_frame, padding=14)
        card.pack(fill="both", expand=True)

        pagamento_atual = det.get("payment", {})
        var_pgto = tk.StringVar(value=pagamento_atual.get("method", "Pix"))
        var_resp = tk.StringVar()
        var_detalhe = tk.StringVar(value=pagamento_atual.get("detail", ""))
        var_recebido = tk.StringVar(
            value="" if pagamento_atual.get("received") is None else str(pagamento_atual["received"])
        )
        var_troco = tk.StringVar(
            value="" if pagamento_atual.get("change") is None else str(pagamento_atual["change"])
        )

        tk.Label(card, text="Forma de Pagamento", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        ttk.Combobox(
            card,
            textvariable=var_pgto,
            values=PAYMENT_METHODS,
            state="readonly",
        ).pack(fill="x", pady=(2, 8))

        tk.Label(card, text="Detalhes (Bandeira/Parcelas)", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        StyledEntry(card, textvariable=var_detalhe).pack(fill="x", ipady=4, pady=(2, 8))

        valores = tk.Frame(card, bg=TEMA_ATUAL["surface"])
        valores.pack(fill="x", pady=(0, 8))
        for rotulo, variavel in (
            ("Valor Recebido (R$)", var_recebido),
            ("Troco (R$)", var_troco),
        ):
            campo = tk.Frame(valores, bg=TEMA_ATUAL["surface"])
            campo.pack(side="left", fill="x", expand=True, padx=(0, 8))
            tk.Label(
                campo,
                text=rotulo,
                bg=TEMA_ATUAL["surface"],
                fg=TEMA_ATUAL["texto_suave"],
                font=FONTES["label_sm"],
            ).pack(anchor="w")
            StyledEntry(campo, textvariable=variavel).pack(fill="x", ipady=4, pady=(2, 0))

        tk.Label(card, text="Responsável pela Alteração *", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        entry_resp = StyledEntry(card, textvariable=var_resp)
        entry_resp.pack(fill="x", ipady=4, pady=(2, 8))
        entry_resp.focus_set()

        def confirmar():
            if not var_resp.get().strip():
                messagebox.showerror("Campo Obrigatório", "Informe o nome do responsável pela correção.", parent=dialogo)
                return

            def executar(
                valor_recebido=None,
                troco=None,
                parcelas=None,
            ):
                kwargs = {}
                if parcelas is not None:
                    kwargs["pagamentos"] = parcelas
                self._confirmar_correcao(
                    parent=dialogo,
                    titulo="Confirmar alteração de pagamento",
                    risco=(
                        f"Alterar o pagamento da Venda #{num:03d} para {var_pgto.get()}?\n\n"
                        "A correção ficará registrada no histórico de auditoria."
                    ),
                    corrigir=lambda: vendas_service.alterar_pagamento_venda(
                        periodo_id=per,
                        num_venda=num,
                        pagamento=var_pgto.get(),
                        pagamento_detalhe=var_detalhe.get().strip(),
                        valor_recebido=valor_recebido,
                        troco=troco,
                        responsavel=var_resp.get().strip(),
                        observacao="Alterado via tela de Vendas e correções",
                        **kwargs,
                    ),
                    titulo_erro="Não foi possível alterar o pagamento",
                    titulo_sucesso="Pagamento Atualizado",
                    mensagem_sucesso="A forma de pagamento da venda foi alterada com sucesso.",
                    fechar_ao_concluir=dialogo,
                )

            if var_pgto.get() == "Mais de uma forma":
                total_centavos = valor_para_centavos(det["totals"]["total"])
                parcelas = pagamento_atual.get("installments", [])
                if len(parcelas) < 2:
                    try:
                        parcelas = self._parcelas_iniciais_mistas(total_centavos)
                    except ValueError as erro:
                        messagebox.showerror(
                            "Pagamento inválido", str(erro), parent=dialogo
                        )
                        return
                self._pedir_parcelas_mistas(
                    total_centavos,
                    lambda novas: executar(parcelas=novas),
                    parcelas,
                )
                return
            try:
                valor_recebido = ler_valor_monetario_opcional(
                    var_recebido.get(), "Valor recebido"
                )
                troco = ler_valor_monetario_opcional(var_troco.get(), "Troco")
            except ValueError as erro:
                messagebox.showerror("Pagamento inválido", str(erro), parent=dialogo)
                return
            executar(valor_recebido, troco)

        action_button(dialogo.footer_frame, text="Salvar Alteração", command=confirmar, variant="primary").pack(side="right")
        action_button(dialogo.footer_frame, text="Cancelar", command=dialogo.close, variant="ghost").pack(side="right", padx=(0, 8))

    def _alterar_quantidade(self, line_id):
        """Altera a quantidade de um item usando BaseModal."""
        det = self._detalhe
        per, num = self._identidade_venda()

        dialogo = BaseModal(
            self,
            title=f"Alterar quantidade - Item #{line_id}",
            subtitle=f"Defina a nova quantidade para a linha da Venda #{num:03d}.",
            width=440,
            height=320,
        )

        card = Card(dialogo.body_frame, padding=14)
        card.pack(fill="both", expand=True)

        var_qtd = tk.StringVar(value="1")
        var_resp = tk.StringVar()

        tk.Label(card, text="Nova Quantidade (Unidades) *", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        entry_qtd = StyledEntry(card, textvariable=var_qtd)
        entry_qtd.pack(fill="x", ipady=4, pady=(2, 10))

        tk.Label(card, text="Responsável pela Alteração *", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        entry_resp = StyledEntry(card, textvariable=var_resp)
        entry_resp.pack(fill="x", ipady=4, pady=(2, 10))
        entry_qtd.focus_set()

        def confirmar():
            if not var_resp.get().strip():
                messagebox.showerror("Campo Obrigatório", "Informe o responsável.", parent=dialogo)
                return
            try:
                quantidade = ler_quantidade(var_qtd.get())
            except ValueError as erro:
                messagebox.showerror("Quantidade inválida", str(erro), parent=dialogo)
                return

            def executar(parcelas=None):
                kwargs = {}
                if parcelas is not None:
                    kwargs["pagamentos"] = parcelas
                self._confirmar_correcao(
                    parent=dialogo,
                    titulo="Confirmar alteração de quantidade",
                    risco=(
                        f"Alterar a quantidade do item #{line_id} para {quantidade}?\n\n"
                        "O estoque, as parcelas e o total serão ajustados na mesma transação."
                    ),
                    corrigir=lambda: vendas_service.alterar_quantidade_item_venda(
                        periodo_id=per,
                        num_venda=num,
                        line_id=line_id,
                        quantidade=quantidade,
                        responsavel=var_resp.get().strip(),
                        **kwargs,
                    ),
                    titulo_erro="Não foi possível alterar a quantidade",
                    titulo_sucesso="Quantidade Atualizada",
                    mensagem_sucesso="A quantidade do item foi alterada com sucesso.",
                    fechar_ao_concluir=dialogo,
                )

            pagamento = det.get("payment", {})
            if pagamento.get("method") == "Mais de uma forma":
                item = next(
                    item for item in det["items"] if item["line_id"] == line_id
                )
                novo_total = (
                    valor_para_centavos(det["totals"]["total"])
                    - valor_para_centavos(item["subtotal"])
                    + valor_para_centavos(item["unit_price"]) * quantidade
                )
                self._pedir_parcelas_mistas(novo_total, executar)
                return
            executar()

        action_button(dialogo.footer_frame, text="Salvar Quantidade", command=confirmar, variant="primary").pack(side="right")
        action_button(dialogo.footer_frame, text="Cancelar", command=dialogo.close, variant="ghost").pack(side="right", padx=(0, 8))

    def _remover_item(self, line_id):
        """Remove o item com confirmacao explicita de risco."""
        per, num = self._identidade_venda()

        def continuar(responsavel: str) -> None:
            def executar(parcelas=None):
                kwargs = {}
                if parcelas is not None:
                    kwargs["pagamentos"] = parcelas
                self._confirmar_correcao(
                    parent=self,
                    titulo="Remover item da venda",
                    risco=(
                        f"Você está prestes a remover o item da linha #{line_id} da Venda #{num:03d}.\n\n"
                        "Estoque, parcelas e total serão ajustados na mesma transação."
                    ),
                    corrigir=lambda: vendas_service.remover_item_venda(
                        periodo_id=per,
                        num_venda=num,
                        line_id=line_id,
                        responsavel=responsavel,
                        **kwargs,
                    ),
                    titulo_erro="Ação Não Permitida",
                    titulo_sucesso="Item Removido",
                    mensagem_sucesso="O item foi removido da venda com sucesso.",
                    badge_type="CRITICO",
                )

            pagamento = self._detalhe.get("payment", {})
            if pagamento.get("method") == "Mais de uma forma":
                item = next(
                    item
                    for item in self._detalhe["items"]
                    if item["line_id"] == line_id
                )
                novo_total = (
                    valor_para_centavos(self._detalhe["totals"]["total"])
                    - valor_para_centavos(item["subtotal"])
                )
                self._pedir_parcelas_mistas(novo_total, executar)
                return
            executar()

        self._pedir_responsavel(
            titulo="Responsável pela remoção",
            instrucao="Identifique quem está removendo o item antes da confirmação.",
            continuar=continuar,
        )

    def _cancelar_venda(self):
        """Cancela a venda inteira com confirmacao forte de risco."""
        per, num = self._identidade_venda()

        def continuar(responsavel: str) -> None:
            self._confirmar_correcao(
                parent=self,
                titulo="Cancelar venda",
                risco=(
                    f"Você está prestes a cancelar a Venda #{num:03d} do Período {per:02d}.\n\n"
                    "Ela não entrará na movimentação financeira líquida, todos os itens voltarão "
                    "ao estoque e o histórico permanecerá preservado."
                ),
                corrigir=lambda: vendas_service.cancelar_venda(
                    periodo_id=per,
                    num_venda=num,
                    responsavel=responsavel,
                    observacao="Cancelada via tela de Vendas e correções",
                ),
                titulo_erro="Não foi possível cancelar a venda",
                titulo_sucesso="Venda Cancelada",
                mensagem_sucesso=f"A Venda #{num:03d} foi cancelada com sucesso.",
                badge_type="CRITICO",
            )

        self._pedir_responsavel(
            titulo="Responsável pelo cancelamento",
            instrucao="Identifique quem está cancelando a venda antes da confirmação.",
            continuar=continuar,
        )
