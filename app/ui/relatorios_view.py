"""
View para a aba de Relatórios e fechamento (Issue #18).

Separa visualmente a movimentação financeira líquida (vendas válidas e corrigidas),
o resumo de conciliação por forma de pagamento, a rastreabilidade de vendas
canceladas em seção isolada e as ações de exportação em Excel.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from app.runtime import database, filtered_report, period_report, reports as relatorios_service
from app.ui.components import (
    Card,
    DataTable,
    KpiCard,
    PageHeader,
    SectionHeader,
    StatusBadge,
    StyledEntry,
    action_button,
    bind_mousewheel_tree,
)
from app.estoque.relatorio_estoque import gerar_posicao_estoque
from app.ui.theme import FONTES, TEMA_ATUAL, moeda


class RelatoriosView(tk.Frame):
    """View principal da aba de Relatórios e Fechamento."""

    def __init__(
        self,
        parent: tk.Widget,
        periodo_id_provider: Callable[[], int] | None = None,
        destinos: list[dict] | None = None,
        autoload: bool = True,
    ):
        super().__init__(parent, bg=TEMA_ATUAL["fundo"], padx=18, pady=16)
        self._periodo_id_provider = periodo_id_provider
        self._dados_fechamento: dict[str, Any] = {}
        self._destinos_iniciais = destinos

        self._build_ui()
        if autoload:
            self.atualizar()

    def _obter_periodo_id(self) -> int:
        if self._periodo_id_provider:
            return self._periodo_id_provider()
        # Fallback para o ultimo periodo aberto ou 1
        return database.ultimo_periodo_id()

    def _build_ui(self):
        """Monta a estrutura visual da aba."""
        for w in self.winfo_children():
            w.destroy()

        PageHeader(
            self,
            "Relatórios e fechamento",
            "Consulte a movimentação financeira líquida, vendas canceladas e exporte conciliações.",
            "Exportar Relatório (XLSX)",
            self._exportar_fechamento_xlsx,
        ).pack(fill="x", pady=(0, 12))

        # Scrollable container para caber bem em telas 1366x768 e menores
        canvas = tk.Canvas(self, bg=TEMA_ATUAL["fundo"], highlightthickness=0)
        self._canvas = canvas
        scroll = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)

        self._content = tk.Frame(canvas, bg=TEMA_ATUAL["fundo"])
        self._content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas_window = canvas.create_window((0, 0), window=self._content, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # --- SEÇÃO 1: Fechamento Financeiro Líquido ---
        self._build_card_fechamento_financeiro()

        # --- SEÇÃO 2: Vendas Canceladas & Rastreabilidade ---
        self._build_card_vendas_canceladas()

        # --- SEÇÃO 3: Relatórios Operacionais & Exportação ---
        self._build_card_exportacoes()
        bind_mousewheel_tree(self._content, canvas)

    def _build_card_fechamento_financeiro(self):
        self._card_financeiro = Card(self._content, padding=16)
        self._card_financeiro.pack(fill="x", pady=(0, 12))

        SectionHeader(
            self._card_financeiro,
            "Fechamento do periodo",
            "Vendas canceladas nao entram na movimentacao financeira, mas aparecem abaixo para rastreabilidade.",
        ).pack(anchor="w", fill="x", pady=(0, 12))

        # Faixa de leitura rápida: os detalhes ficam na tabela logo abaixo.
        self._stats_frame = tk.Frame(self._card_financeiro, bg=TEMA_ATUAL["surface"])
        self._stats_frame.pack(fill="x", pady=(0, 12))
        for column in range(3):
            self._stats_frame.columnconfigure(column, weight=1, uniform="kpi")

        kpi_total = KpiCard(self._stats_frame, "Financeiro valido", "R$ 0,00", tone="primary")
        kpi_total.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._lbl_total_liquido = kpi_total.value_label

        kpi_corrigidas = KpiCard(self._stats_frame, "Correções", "0")
        kpi_corrigidas.grid(row=0, column=1, sticky="ew", padx=4)
        self._lbl_qtd_corrigidas = kpi_corrigidas.value_label

        kpi_canceladas = KpiCard(self._stats_frame, "Canceladas separadas", "0")
        kpi_canceladas.grid(row=0, column=2, sticky="ew", padx=(8, 0))
        self._lbl_qtd_canceladas = kpi_canceladas.value_label

        # Tabela de Conciliação por Forma de Pagamento
        tk.Label(self._card_financeiro, text="Conciliação por Forma de Pagamento", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto"], font=FONTES["corpo_bold"]).pack(anchor="w", pady=(4, 6))

        colunas = ("forma", "transacoes", "total")
        titulos = {"forma": "Forma de Pagamento", "transacoes": "Vendas", "total": "Total Acumulado"}
        larguras = {"forma": 240, "transacoes": 120, "total": 180}

        self._tree_pgto = DataTable(self._card_financeiro, colunas, titulos, larguras, height=5)
        self._tree_pgto.column("forma", anchor="w")
        self._tree_pgto.pack(fill="x")

    def _build_card_vendas_canceladas(self):
        self._card_canceladas = tk.Frame(self._content, bg=TEMA_ATUAL["danger_soft"], padx=16, pady=16)
        self._card_canceladas.pack(fill="x", pady=(0, 12))

        tk.Label(
            self._card_canceladas,
            text="Vendas canceladas",
            bg=TEMA_ATUAL["danger_soft"],
            fg=TEMA_ATUAL["danger"],
            font=FONTES["corpo_bold"]
        ).pack(anchor="w", pady=(0, 8))

        self._container_canceladas = tk.Frame(self._card_canceladas, bg=TEMA_ATUAL["danger_soft"])
        self._container_canceladas.pack(fill="x")

    def _build_card_exportacoes(self):
        card_exp = Card(self._content, padding=16)
        card_exp.pack(fill="x", pady=(0, 12))

        SectionHeader(
            card_exp,
            "Relatórios Operacionais & Exportação em Excel",
            "Gere arquivos da conciliação do período ou posição atual do estoque.",
        ).pack(anchor="w", fill="x", pady=(0, 10))

        filtros = tk.Frame(card_exp, bg=TEMA_ATUAL["surface"])
        filtros.pack(fill="x", pady=(0, 10))
        self._var_data_inicial = tk.StringVar()
        self._var_data_final = tk.StringVar()
        self._var_forma = tk.StringVar(value="Todas")
        destinos = self._destinos_iniciais if self._destinos_iniciais is not None else database.listar_destinos_financeiros()
        self._destinos_relatorio = {destino["nome"]: int(destino["id"]) for destino in destinos}
        self._var_destino = tk.StringVar(value="Todos")
        self._var_status_relatorio = tk.StringVar(value="Válidas e corrigidas")
        campos = []
        for rotulo, fabrica in (
            ("De (AAAA-MM-DD)", lambda parent: StyledEntry(parent, textvariable=self._var_data_inicial, bg=TEMA_ATUAL["surface_2"])),
            ("Até", lambda parent: StyledEntry(parent, textvariable=self._var_data_final, bg=TEMA_ATUAL["surface_2"])),
            ("Forma", lambda parent: ttk.Combobox(parent, textvariable=self._var_forma, values=("Todas", "Dinheiro", "Pix", "Debito", "Credito", "Cartao"), state="readonly")),
            ("Destino", lambda parent: ttk.Combobox(parent, textvariable=self._var_destino, values=("Todos", *self._destinos_relatorio), state="readonly")),
            ("Status", lambda parent: ttk.Combobox(parent, textvariable=self._var_status_relatorio, values=("Válidas e corrigidas", "Canceladas", "Todas"), state="readonly")),
        ):
            bloco = tk.Frame(filtros, bg=TEMA_ATUAL["surface"])
            tk.Label(bloco, text=rotulo, bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["text_muted"]).pack(anchor="w")
            fabrica(bloco).pack(fill="x", ipady=3, pady=(3, 0))
            campos.append(bloco)

        row_btns = tk.Frame(card_exp, bg=TEMA_ATUAL["surface"])
        row_btns.pack(fill="x")
        botoes = [action_button(
            row_btns,
            text="📊 Exportar Relatório do Período (.xlsx)",
            command=self._exportar_fechamento_xlsx,
            variant="primary",
        ), action_button(
            row_btns,
            text="📦 Exportar Posição do Estoque (.xlsx)",
            command=self._exportar_estoque_xlsx,
            variant="secondary",
        ), action_button(
            row_btns,
            text="Exportar vendas filtradas (.xlsx)",
            command=self._exportar_vendas_filtradas,
            variant="secondary",
        )]

        def ajustar_grade(event):
            colunas = 1 if event.width < 480 else (2 if event.width < 900 else 5)
            for coluna in range(5):
                filtros.columnconfigure(coluna, weight=1 if coluna < colunas else 0)
            for indice, bloco in enumerate(campos):
                bloco.grid(row=indice // colunas, column=indice % colunas, sticky="ew", padx=(0 if indice % colunas == 0 else 8, 0), pady=(0, 8))

            colunas_botoes = 1 if event.width < 620 else 3
            for coluna in range(3):
                row_btns.columnconfigure(coluna, weight=1 if coluna < colunas_botoes else 0)
            for indice, botao in enumerate(botoes):
                botao.grid(row=indice // colunas_botoes, column=indice % colunas_botoes, sticky="ew", padx=(0 if indice % colunas_botoes == 0 else 8, 0), pady=(0, 8))

        card_exp.bind("<Configure>", ajustar_grade)

        self._lbl_feedback_exp = tk.Label(card_exp, text="", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["primary"], font=FONTES["corpo_bold"])
        self._lbl_feedback_exp.pack(anchor="w", pady=(8, 0))

    def atualizar(self, dados: dict | None = None):
        """Carrega os dados atualizados do servico de relatorios."""
        periodo_id = self._obter_periodo_id()
        if dados is None:
            try:
                dados = relatorios_service.obter_fechamento_financeiro(periodo_id)
            except Exception as erro:
                messagebox.showerror(
                    "Não foi possível carregar o fechamento",
                    str(erro),
                    parent=self,
                )
                return

        self._dados_fechamento = dados
        mov = dados.get("financial_movement", {})

        # Atualiza KPIs
        tot_liquido = float(mov.get("total", 0.0))
        qtd_corrigidas = int(mov.get("corrected_transactions", 0))
        qtd_canceladas = len(dados.get("cancelled_sales", []))

        self._lbl_total_liquido.config(text=moeda(tot_liquido))
        self._lbl_qtd_corrigidas.config(text=str(qtd_corrigidas))
        self._lbl_qtd_canceladas.config(text=str(qtd_canceladas))

        # Preenche Tabela de Conciliação por Forma de Pagamento
        for item in self._tree_pgto.get_children():
            self._tree_pgto.delete(item)

        pgto_summary = mov.get("payment_summary", {})
        if not pgto_summary:
            self._tree_pgto.insert("", "end", values=("Nenhum pagamento registrado", "0", moeda(0)))
        else:
            for forma, info in pgto_summary.items():
                self._tree_pgto.insert(
                    "",
                    "end",
                    values=(
                        forma,
                        f"{info.get('transactions', 0)} vendas",
                        moeda(float(info.get("total", 0))),
                    ),
                )

        # Preenche Tabela de Vendas Canceladas
        for widget in self._container_canceladas.winfo_children():
            widget.destroy()

        canceladas = dados.get("cancelled_sales", [])
        if not canceladas:
            self._card_canceladas.pack_forget()
        else:
            self._card_canceladas.pack(fill="x", pady=(0, 12))
            for c in canceladas:
                sold_at = c.get("sold_at", {})
                dt_str = f"{sold_at.get('time', '')}".strip()
                n = c.get('sale_number', 0)
                v = moeda(float(c.get("total", 0)))
                resp = c.get("responsible", "")
                
                texto = f"#{n:03d} - {v} - cancelada por {resp} às {dt_str}. Estoque devolvido automaticamente."
                tk.Label(
                    self._container_canceladas,
                    text=texto,
                    bg=TEMA_ATUAL["danger_soft"],
                    fg=TEMA_ATUAL["danger"],
                    font=FONTES["corpo"]
                ).pack(anchor="w", pady=2)

    def _exportar_fechamento_xlsx(self):
        """Exporta o relatorio do periodo em formato Excel."""
        periodo_id = self._obter_periodo_id()
        pasta = filedialog.askdirectory(title="Selecione a pasta para salvar o relatório")
        if not pasta:
            return
        try:
            caminho = period_report(periodo_id, Path(pasta) / f"Relatorio_periodo-{periodo_id}.xlsx")
            self._lbl_feedback_exp.config(text=f"✓ Relatório salvo com sucesso em:\n{caminho}")
            messagebox.showinfo("Exportação Concluída", f"Relatório do período exportado com sucesso para:\n\n{caminho}", parent=self)
        except Exception as erro:
            messagebox.showerror("Erro na Exportação", str(erro), parent=self)

    def _exportar_estoque_xlsx(self):
        """Exporta a posicao atual do estoque em formato Excel."""
        pasta = filedialog.askdirectory(title="Selecione a pasta para salvar a posição do estoque")
        if not pasta:
            return
        try:
            caminho = gerar_posicao_estoque(database.indicadores_produtos_estoque(), pasta)
            self._lbl_feedback_exp.config(text=f"✓ Posição do estoque salva em:\n{caminho}")
            messagebox.showinfo("Exportação Concluída", f"Posição do estoque exportada com sucesso para:\n\n{caminho}", parent=self)
        except Exception as erro:
            messagebox.showerror("Erro na Exportação", str(erro), parent=self)

    def _exportar_vendas_filtradas(self):
        data_inicial = self._var_data_inicial.get().strip()
        data_final = self._var_data_final.get().strip()
        if not data_inicial or not data_final:
            messagebox.showerror("Filtro incompleto", "Informe as datas inicial e final.", parent=self)
            return
        pasta = filedialog.askdirectory(title="Selecione a pasta para salvar o relatório")
        if not pasta:
            return
        forma = self._var_forma.get()
        try:
            caminho = filtered_report(
                {"data_inicial": data_inicial, "data_final": data_final,
                 "forma": None if forma == "Todas" else forma,
                 "destino_id": self._destinos_relatorio.get(self._var_destino.get()),
                 "status": {"Canceladas": "cancelled", "Todas": "all"}.get(self._var_status_relatorio.get(), "valid")},
                Path(pasta) / "relatorio_vendas_filtrado.xlsx",
            )
            self._lbl_feedback_exp.config(text=f"✓ Relatório filtrado salvo em:\n{caminho}")
            messagebox.showinfo("Exportação concluída", f"Relatório salvo em:\n\n{caminho}", parent=self)
        except Exception as erro:
            messagebox.showerror("Erro na exportação", str(erro), parent=self)
