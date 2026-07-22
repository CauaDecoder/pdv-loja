"""
View para a aba de Relatórios e fechamento (Issue #18).

Separa visualmente a movimentação financeira líquida (vendas válidas e corrigidas),
o resumo de conciliação por forma de pagamento, a rastreabilidade de vendas
canceladas em seção isolada e as ações de exportação em Excel.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

import database
from app.services import relatorios_service
from app.ui.components import (
    Card,
    DataTable,
    EmptyState,
    PageHeader,
    SectionHeader,
    StatusBadge,
    action_button,
)
from estoque.relatorio_estoque import gerar_posicao_estoque
from tema import FONTES, TEMA_ATUAL, moeda


class RelatoriosView(tk.Frame):
    """View principal da aba de Relatórios e Fechamento."""

    def __init__(self, parent: tk.Widget, periodo_id_provider: Callable[[], int] | None = None):
        super().__init__(parent, bg=TEMA_ATUAL["fundo"], padx=18, pady=16)
        self._periodo_id_provider = periodo_id_provider
        self._dados_fechamento: dict[str, Any] = {}

        self._build_ui()
        self.atualizar()

    def _obter_periodo_id(self) -> int:
        if self._periodo_id_provider:
            return self._periodo_id_provider()
        # Fallback para o ultimo periodo aberto ou 1
        with database.get_conn() as conn:
            row = conn.execute("SELECT id FROM periodos_caixa ORDER BY id DESC LIMIT 1").fetchone()
            return row["id"] if row else 1

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

    def _build_card_fechamento_financeiro(self):
        self._card_financeiro = Card(self._content, padding=16)
        self._card_financeiro.pack(fill="x", pady=(0, 12))

        SectionHeader(
            self._card_financeiro,
            "Fechamento Financeiro Líquido do Período",
            "Movimentação financeira real (apenas vendas válidas e corrigidas).",
        ).pack(anchor="w", fill="x", pady=(0, 12))

        # KPI Stats Header
        self._stats_frame = tk.Frame(self._card_financeiro, bg=TEMA_ATUAL["surface"])
        self._stats_frame.pack(fill="x", pady=(0, 12))

        # Card Total Líquido
        box_total = tk.Frame(self._stats_frame, bg=TEMA_ATUAL["surface_2"], padx=14, pady=10)
        box_total.pack(side="left", padx=(0, 12))
        tk.Label(box_total, text="MOVIMENTAÇÃO LÍQUIDA", bg=TEMA_ATUAL["surface_2"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        self._lbl_total_liquido = tk.Label(box_total, text="R$ 0,00", bg=TEMA_ATUAL["surface_2"], fg=TEMA_ATUAL["primary"], font=FONTES["titulo"])
        self._lbl_total_liquido.pack(anchor="w", pady=(2, 0))

        # Card Vendas Válidas
        box_validas = tk.Frame(self._stats_frame, bg=TEMA_ATUAL["surface_2"], padx=14, pady=10)
        box_validas.pack(side="left", padx=(0, 12))
        tk.Label(box_validas, text="VENDAS VÁLIDAS", bg=TEMA_ATUAL["surface_2"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        self._lbl_qtd_validas = tk.Label(box_validas, text="0 vendas", bg=TEMA_ATUAL["surface_2"], fg=TEMA_ATUAL["texto"], font=FONTES["subtitulo"])
        self._lbl_qtd_validas.pack(anchor="w", pady=(2, 0))

        # Card Vendas Corrigidas
        box_corrigidas = tk.Frame(self._stats_frame, bg=TEMA_ATUAL["surface_2"], padx=14, pady=10)
        box_corrigidas.pack(side="left")
        tk.Label(box_corrigidas, text="VENDAS CORRIGIDAS", bg=TEMA_ATUAL["surface_2"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        self._lbl_qtd_corrigidas = tk.Label(box_corrigidas, text="0 correções", bg=TEMA_ATUAL["surface_2"], fg=TEMA_ATUAL["warning"], font=FONTES["subtitulo"])
        self._lbl_qtd_corrigidas.pack(anchor="w", pady=(2, 0))

        # Tabela de Conciliação por Forma de Pagamento
        tk.Label(self._card_financeiro, text="Conciliação por Forma de Pagamento", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto"], font=FONTES["corpo_bold"]).pack(anchor="w", pady=(4, 6))

        colunas = ("forma", "transacoes", "total")
        titulos = {"forma": "Forma de Pagamento", "transacoes": "Vendas", "total": "Total Acumulado"}
        larguras = {"forma": 240, "transacoes": 120, "total": 180}

        self._tree_pgto = DataTable(self._card_financeiro, colunas, titulos, larguras, height=5)
        self._tree_pgto.column("forma", anchor="w")
        self._tree_pgto.pack(fill="x")

    def _build_card_vendas_canceladas(self):
        self._card_canceladas = Card(self._content, padding=16)
        self._card_canceladas.pack(fill="x", pady=(0, 12))

        SectionHeader(
            self._card_canceladas,
            "Vendas Canceladas (Rastreabilidade & Auditoria)",
            "Vendas anuladas do período mantidas exclusivamente para auditoria.",
        ).pack(anchor="w", fill="x", pady=(0, 6))

        # Banner informativo
        banner = tk.Frame(self._card_canceladas, bg=TEMA_ATUAL["surface_2"], padx=12, pady=8)
        banner.pack(fill="x", pady=(0, 10))
        tk.Label(
            banner,
            text="⚠️ Importante: Vendas canceladas NÃO integram a receita líquida nem entram na movimentação financeira do período acima.",
            bg=TEMA_ATUAL["surface_2"],
            fg=TEMA_ATUAL["danger"],
            font=FONTES["corpo_bold"],
        ).pack(anchor="w")

        colunas = ("venda", "data_hora", "responsavel", "pagamento", "total", "status")
        titulos = {
            "venda": "Venda",
            "data_hora": "Data / Hora",
            "responsavel": "Responsável",
            "pagamento": "Forma Original",
            "total": "Valor Anulado",
            "status": "Status",
        }
        larguras = {
            "venda": 90,
            "data_hora": 140,
            "responsavel": 160,
            "pagamento": 200,
            "total": 120,
            "status": 110,
        }

        self._tree_canceladas = DataTable(self._card_canceladas, colunas, titulos, larguras, height=4)
        self._tree_canceladas.column("responsavel", anchor="w")
        self._tree_canceladas.column("pagamento", anchor="w")
        self._tree_canceladas.pack(fill="x")

        self._empty_canceladas = EmptyState(
            self._card_canceladas,
            "Nenhuma venda cancelada",
            "Não houve cancelamentos de vendas registrados neste período.",
        )

    def _build_card_exportacoes(self):
        card_exp = Card(self._content, padding=16)
        card_exp.pack(fill="x", pady=(0, 12))

        SectionHeader(
            card_exp,
            "Relatórios Operacionais & Exportação em Excel",
            "Gere arquivos da conciliação do período ou posição atual do estoque.",
        ).pack(anchor="w", fill="x", pady=(0, 10))

        row_btns = tk.Frame(card_exp, bg=TEMA_ATUAL["surface"])
        row_btns.pack(fill="x")

        action_button(
            row_btns,
            text="📊 Exportar Relatório do Período (.xlsx)",
            command=self._exportar_fechamento_xlsx,
            variant="primary",
        ).pack(side="left", padx=(0, 10))

        action_button(
            row_btns,
            text="📦 Exportar Posição do Estoque (.xlsx)",
            command=self._exportar_estoque_xlsx,
            variant="secondary",
        ).pack(side="left")

        self._lbl_feedback_exp = tk.Label(card_exp, text="", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["primary"], font=FONTES["corpo_bold"])
        self._lbl_feedback_exp.pack(anchor="w", pady=(8, 0))

    def atualizar(self):
        """Carrega os dados atualizados do servico de relatorios."""
        periodo_id = self._obter_periodo_id()
        try:
            dados = relatorios_service.obter_fechamento_financeiro(periodo_id)
        except Exception:
            dados = {
                "period_id": periodo_id,
                "financial_movement": {
                    "transactions": 0,
                    "total": 0.0,
                    "corrected_transactions": 0,
                    "payment_summary": {},
                },
                "cancelled_sales": [],
            }

        self._dados_fechamento = dados
        mov = dados.get("financial_movement", {})

        # Atualiza KPIs
        tot_liquido = float(mov.get("total", 0.0))
        qtd_validas = int(mov.get("transactions", 0))
        qtd_corrigidas = int(mov.get("corrected_transactions", 0))

        self._lbl_total_liquido.config(text=moeda(tot_liquido))
        self._lbl_qtd_validas.config(text=f"{qtd_validas} vendas")
        self._lbl_qtd_corrigidas.config(text=f"{qtd_corrigidas} correções")

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
        for item in self._tree_canceladas.get_children():
            self._tree_canceladas.delete(item)

        canceladas = dados.get("cancelled_sales", [])
        if not canceladas:
            self._tree_canceladas.pack_forget()
            self._empty_canceladas.pack(fill="x", pady=6)
        else:
            self._empty_canceladas.pack_forget()
            self._tree_canceladas.pack(fill="x")
            for c in canceladas:
                sold_at = c.get("sold_at", {})
                dt_str = f"{sold_at.get('date', '')} {sold_at.get('time', '')}".strip()
                self._tree_canceladas.insert(
                    "",
                    "end",
                    values=(
                        f"#{c.get('sale_number', 0):03d}",
                        dt_str,
                        c.get("responsible", ""),
                        c.get("payment_summary", ""),
                        moeda(float(c.get("total", 0))),
                        "CANCELADA",
                    ),
                )

    def _exportar_fechamento_xlsx(self):
        """Exporta o relatorio do periodo em formato Excel."""
        periodo_id = self._obter_periodo_id()
        pasta = filedialog.askdirectory(title="Selecione a pasta para salvar o relatório")
        if not pasta:
            return
        try:
            caminho = relatorios_service.gerar_relatorio_periodo(periodo_id, pasta_saida=pasta)
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
            caminho = gerar_posicao_estoque(pasta_saida=pasta)
            self._lbl_feedback_exp.config(text=f"✓ Posição do estoque salva em:\n{caminho}")
            messagebox.showinfo("Exportação Concluída", f"Posição do estoque exportada com sucesso para:\n\n{caminho}", parent=self)
        except Exception as erro:
            messagebox.showerror("Erro na Exportação", str(erro), parent=self)
