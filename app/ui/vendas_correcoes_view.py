"""
View e modais para a aba Vendas e correções (Issue #15).

Implementa a interface de consulta de vendas finalizadas, filtros completos por
número, período, pagamento, status, responsável e produto, além do modal de
detalhes da venda com histórico de auditoria e ações de correção pós-venda.
"""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from app.payments import (
    CARD_BRANDS,
    CARD_INSTALLMENTS,
    PAYMENT_METHODS,
    parse_currency,
)
from app.services import vendas_service
from app.ui.components import (
    BaseModal,
    Card,
    DataTable,
    EmptyState,
    LabeledField,
    PageHeader,
    SectionHeader,
    StatusBadge,
    StyledEntry,
    action_button,
    bind_escape_to_close,
    confirmar_acao_sensivel,
)
from tema import FONTES, TEMA_ATUAL, moeda

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


class VendasCorrecoesView(tk.Frame):
    """View principal da aba Vendas e correções com filtros e tabela."""

    def __init__(self, parent: tk.Widget, on_sale_updated: Callable | None = None):
        super().__init__(parent, bg=TEMA_ATUAL["fundo"], padx=18, pady=16)
        self._on_sale_updated = on_sale_updated

        # Variáveis dos Filtros
        self._var_num_venda = tk.StringVar()
        self._var_data_inicio = tk.StringVar()
        self._var_data_fim = tk.StringVar()
        self._var_pagamento = tk.StringVar(value="Todas")
        self._var_status = tk.StringVar(value="Todos")
        self._var_responsavel = tk.StringVar()
        self._var_produto = tk.StringVar()

        self._vendas_carregadas: list[dict[str, Any]] = []

        self._build_ui()
        self.atualizar()

    def _build_ui(self):
        """Monta a estrutura visual da aba."""
        for w in self.winfo_children():
            w.destroy()

        PageHeader(
            self,
            "Vendas e correções",
            "Consulte vendas finalizadas e realize correções pós-venda ou cancelamentos com histórico.",
            "Atualizar",
            self.atualizar,
        ).pack(fill="x", pady=(0, 12))

        # --- FILTROS ---
        self._build_filtros_card()

        # --- TABELA DE VENDAS ---
        self._build_tabela_card()

    def _build_filtros_card(self):
        card_filtros = Card(self, padding=14)
        card_filtros.pack(fill="x", pady=(0, 12))

        grid = tk.Frame(card_filtros, bg=TEMA_ATUAL["surface"])
        grid.pack(fill="x")

        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, minsize=150)
        grid.columnconfigure(2, minsize=150)
        grid.columnconfigure(3, minsize=150)
        grid.columnconfigure(4, minsize=100)

        box_search = tk.Frame(grid, bg=TEMA_ATUAL["surface"])
        box_search.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        tk.Label(box_search, text="Nº / Prod / Resp", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")

        search_inner = tk.Frame(box_search, bg=TEMA_ATUAL["surface"])
        search_inner.pack(fill="x")
        StyledEntry(search_inner, textvariable=self._var_num_venda, width=5).pack(side="left", fill="x", expand=True, padx=(0, 4))
        StyledEntry(search_inner, textvariable=self._var_produto, width=8).pack(side="left", fill="x", expand=True, padx=(0, 4))
        StyledEntry(search_inner, textvariable=self._var_responsavel, width=8).pack(side="left", fill="x", expand=True)

        box_date = tk.Frame(grid, bg=TEMA_ATUAL["surface"])
        box_date.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        tk.Label(box_date, text="Período (Início/Fim)", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        date_inner = tk.Frame(box_date, bg=TEMA_ATUAL["surface"])
        date_inner.pack(fill="x")
        StyledEntry(date_inner, textvariable=self._var_data_inicio, width=8).pack(side="left", fill="x", expand=True, padx=(0, 2))
        StyledEntry(date_inner, textvariable=self._var_data_fim, width=8).pack(side="left", fill="x", expand=True)

        box_pgto = tk.Frame(grid, bg=TEMA_ATUAL["surface"])
        box_pgto.grid(row=0, column=2, sticky="ew", padx=(0, 10))
        tk.Label(box_pgto, text="Pagamento", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        ttk.Combobox(
            box_pgto,
            textvariable=self._var_pagamento,
            values=("Todas", *PAYMENT_METHODS),
            state="readonly",
            width=10,
        ).pack(fill="x", ipady=3)

        box_status = tk.Frame(grid, bg=TEMA_ATUAL["surface"])
        box_status.grid(row=0, column=3, sticky="ew", padx=(0, 10))
        tk.Label(box_status, text="Status", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        ttk.Combobox(box_status, textvariable=self._var_status, values=["Todos", "Válida", "Corrigida", "Cancelada"], state="readonly", width=10).pack(fill="x", ipady=3)

        box_btn = tk.Frame(grid, bg=TEMA_ATUAL["surface"])
        box_btn.grid(row=0, column=4, sticky="e", pady=(15, 0))
        action_button(box_btn, text="🔍", command=self.atualizar, variant="primary").pack(side="left", padx=(0, 4))
        action_button(box_btn, text="🧹", command=self._limpar_filtros, variant="secondary").pack(side="left")

    def _build_tabela_card(self):
        self._card_tabela = Card(self, padding=0)
        self._card_tabela.pack(fill="both", expand=True)

        header = tk.Frame(self._card_tabela, bg=TEMA_ATUAL["surface_2"], pady=8, padx=12)
        header.pack(fill="x")
        
        header.columnconfigure(0, minsize=90)
        header.columnconfigure(1, minsize=110)
        header.columnconfigure(2, weight=1)
        header.columnconfigure(3, minsize=130)
        header.columnconfigure(4, minsize=120)
        header.columnconfigure(5, minsize=130)
        
        for i, text in enumerate(["VENDA", "HORÁRIO", "RESUMO", "PAGAMENTO", "STATUS", ""]):
            tk.Label(header, text=text, bg=TEMA_ATUAL["surface_2"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).grid(row=0, column=i, sticky="w")
            
        self._canvas = tk.Canvas(self._card_tabela, bg=TEMA_ATUAL["surface"], highlightthickness=0)
        self._scroll = ttk.Scrollbar(self._card_tabela, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scroll.set)
        
        self._tabela_body = tk.Frame(self._canvas, bg=TEMA_ATUAL["surface"])
        self._tabela_body.bind("<Configure>", lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        
        self._canvas_window = self._canvas.create_window((0, 0), window=self._tabela_body, anchor="nw")
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(self._canvas_window, width=e.width))
        
        self._canvas.pack(side="left", fill="both", expand=True)
        self._scroll.pack(side="right", fill="y")

        # Frame de Ações da Tabela
        self._bar_acoes = tk.Frame(self, bg=TEMA_ATUAL["fundo"])
        self._bar_acoes.pack(fill="x", pady=(10, 0))

        action_button(
            self._bar_acoes,
            text="🔄 Atualizar Lista",
            command=self.atualizar,
            variant="secondary",
        ).pack(side="right", padx=(0, 8))

    def atualizar(self):
        """Consulta o servico real para renderizar a tabela."""
        filtros = {}
        if self._var_num_venda.get().strip():
            filtros["num_venda"] = self._var_num_venda.get().strip()
        if self._var_data_inicio.get().strip():
            filtros["data_inicio"] = self._var_data_inicio.get().strip()
        if self._var_data_fim.get().strip():
            filtros["data_fim"] = self._var_data_fim.get().strip()
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

        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            vendas = vendas_service.listar_vendas_correcoes(filtros)
        except Exception as erro:
            vendas = []
            messagebox.showerror(
                "Nao foi possivel carregar as vendas",
                str(erro),
                parent=self,
            )
        finally:
            self.configure(cursor="")

        self._vendas_carregadas = vendas

        for w in self._tabela_body.winfo_children():
            w.destroy()

        for idx, v in enumerate(vendas):
            s_code = v.get("status", "valid")
            sold_at = v.get("sold_at", {})
            dt_str = f"{sold_at.get('date', '')} {sold_at.get('time', '')}".strip()

            row = tk.Frame(self._tabela_body, bg=TEMA_ATUAL["surface"], pady=8, padx=12)
            row.pack(fill="x", borderwidth=0, highlightthickness=1, highlightbackground=TEMA_ATUAL["border_soft"])
            
            row.columnconfigure(0, minsize=90)
            row.columnconfigure(1, minsize=110)
            row.columnconfigure(2, weight=1)
            row.columnconfigure(3, minsize=130)
            row.columnconfigure(4, minsize=120)
            row.columnconfigure(5, minsize=130)
            
            tk.Label(row, text=f"#{v.get('sale_number', 0):03d}", bg=TEMA_ATUAL["surface"], font=FONTES["corpo_bold"]).grid(row=0, column=0, sticky="w")
            tk.Label(row, text=dt_str, bg=TEMA_ATUAL["surface"]).grid(row=0, column=1, sticky="w")
            
            resumo_text = f"{v.get('item_summary', {}).get('label', '')} - {v.get('responsible', '')}"
            tk.Label(row, text=resumo_text, bg=TEMA_ATUAL["surface"]).grid(row=0, column=2, sticky="w")
            tk.Label(row, text=v.get("payment_summary", ""), bg=TEMA_ATUAL["surface"]).grid(row=0, column=3, sticky="w")
            
            if s_code == "valid":
                badge = StatusBadge(row, "Válida", "OK")
            elif s_code == "corrected":
                badge = StatusBadge(row, "Corrigida", "ALERTA")
            else:
                badge = StatusBadge(row, "Cancelada", "CRITICO")
            badge.grid(row=0, column=4, sticky="w")
            
            btn = action_button(row, text="Detalhe", command=lambda i=idx: self._abrir_detalhe(i), variant="secondary")
            btn.grid(row=0, column=5, sticky="e")

    def _limpar_filtros(self):
        self._var_num_venda.set("")
        self._var_data_inicio.set("")
        self._var_data_fim.set("")
        self._var_pagamento.set("Todas")
        self._var_status.set("Todos")
        self._var_responsavel.set("")
        self._var_produto.set("")
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

        VendaDetailModal(self, detalhe, on_updated=self.atualizar)


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

        det = self._detalhe
        num = det["identity"]["sale_number"]
        per = det["identity"]["period_id"]
        status = det.get("status", "valid")
        sold_at = det.get("timestamps", {})
        dt_str = f"{sold_at.get('date', '')} às {sold_at.get('time', '')}"

        # Page Header inside Dialog
        hdr_frame = tk.Frame(self, bg=TEMA_ATUAL["fundo"], padx=18, pady=14)
        hdr_frame.pack(fill="x")

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

        # Scrollable Content Area
        canvas = tk.Canvas(self, bg=TEMA_ATUAL["fundo"], highlightthickness=0)
        scroll = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)

        content = tk.Frame(canvas, bg=TEMA_ATUAL["fundo"], padx=18, pady=4)
        content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas_window = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

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

        # 2. Tabela de Itens
        card_itens = Card(content, padding=12)
        card_itens.pack(fill="x", pady=(0, 12))

        hdr_itens = tk.Frame(card_itens, bg=TEMA_ATUAL["surface_2"], pady=6, padx=8)
        hdr_itens.pack(fill="x")
        hdr_itens.columnconfigure(0, weight=1)
        hdr_itens.columnconfigure(1, minsize=60)
        hdr_itens.columnconfigure(2, minsize=100)
        hdr_itens.columnconfigure(3, minsize=160)
        
        for i, text in enumerate(["Produto", "Qtd", "Valor", "Ação"]):
            tk.Label(hdr_itens, text=text, bg=TEMA_ATUAL["surface_2"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).grid(row=0, column=i, sticky="w")
            
        for item in det.get("items", []):
            row = tk.Frame(card_itens, bg=TEMA_ATUAL["surface"], pady=6, padx=8)
            row.pack(fill="x", borderwidth=0, highlightthickness=1, highlightbackground=TEMA_ATUAL["border_soft"])
            row.columnconfigure(0, weight=1)
            row.columnconfigure(1, minsize=60)
            row.columnconfigure(2, minsize=100)
            row.columnconfigure(3, minsize=160)
            
            line_id = item.get("line_id", 0)
            
            tk.Label(row, text=f"{item.get('code', '')} - {item.get('name', '')}", bg=TEMA_ATUAL["surface"]).grid(row=0, column=0, sticky="w")
            tk.Label(row, text=str(item.get("quantity", 0)), bg=TEMA_ATUAL["surface"]).grid(row=0, column=1, sticky="w")
            tk.Label(row, text=moeda(float(item.get("subtotal", 0))), bg=TEMA_ATUAL["surface"]).grid(row=0, column=2, sticky="w")
            
            acts = tk.Frame(row, bg=TEMA_ATUAL["surface"])
            acts.grid(row=0, column=3, sticky="e")
            
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
                    text=f"• {h.get('created_at', '')} por {h.get('responsible', '')}: Ação '{h.get('action', '')}'\n  Antes: {h.get('before')} ➔ Depois: {h.get('after')}",
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
        footer.pack(side="bottom", fill="x")
        
        if status != "cancelled":
            btn_salvar = action_button(footer, text="Salvar correção", command=self.destroy, variant="primary")
            btn_salvar.pack(side="right")
            
            btn_cancelar = action_button(footer, text="Cancelar venda", command=self._cancelar_venda, variant="danger")
            btn_cancelar.pack(side="right", padx=(0, 8))
            if "cancel_sale" not in acoes:
                btn_cancelar.configure(state="disabled")
                
            btn_pag = action_button(footer, text="Alterar pagamento", command=self._alterar_pagamento, variant="ghost")
            btn_pag.pack(side="left")
            if "alter_payment" not in acoes:
                btn_pag.configure(state="disabled")

    # --- AÇÕES DO MODAL DE DETALHES ---

    def _identidade_venda(self) -> tuple[int, int]:
        identidade = self._detalhe["identity"]
        return identidade["period_id"], identidade["sale_number"]

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
            try:
                valor_recebido = ler_valor_monetario_opcional(
                    var_recebido.get(), "Valor recebido"
                )
                troco = ler_valor_monetario_opcional(var_troco.get(), "Troco")
            except ValueError as erro:
                messagebox.showerror("Pagamento inválido", str(erro), parent=dialogo)
                return

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
                ),
                titulo_erro="Não foi possível alterar o pagamento",
                titulo_sucesso="Pagamento Atualizado",
                mensagem_sucesso="A forma de pagamento da venda foi alterada com sucesso.",
                fechar_ao_concluir=dialogo,
            )

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

            self._confirmar_correcao(
                parent=dialogo,
                titulo="Confirmar alteração de quantidade",
                risco=(
                    f"Alterar a quantidade do item #{line_id} para {quantidade}?\n\n"
                    "O estoque e o total da venda serão ajustados e a correção ficará auditada."
                ),
                corrigir=lambda: vendas_service.alterar_quantidade_item_venda(
                    periodo_id=per,
                    num_venda=num,
                    line_id=line_id,
                    quantidade=quantidade,
                    responsavel=var_resp.get().strip(),
                ),
                titulo_erro="Não foi possível alterar a quantidade",
                titulo_sucesso="Quantidade Atualizada",
                mensagem_sucesso="A quantidade do item foi alterada com sucesso.",
                fechar_ao_concluir=dialogo,
            )

        action_button(dialogo.footer_frame, text="Salvar Quantidade", command=confirmar, variant="primary").pack(side="right")
        action_button(dialogo.footer_frame, text="Cancelar", command=dialogo.close, variant="ghost").pack(side="right", padx=(0, 8))

    def _remover_item(self, line_id):
        """Remove o item com confirmacao explicita de risco."""
        per, num = self._identidade_venda()

        def continuar(responsavel: str) -> None:
            self._confirmar_correcao(
                parent=self,
                titulo="Remover item da venda",
                risco=(
                    f"Você está prestes a remover o item da linha #{line_id} da Venda #{num:03d}.\n\n"
                    "A quantidade voltará ao estoque, o total será recalculado e a correção "
                    "ficará registrada no histórico."
                ),
                corrigir=lambda: vendas_service.remover_item_venda(
                    periodo_id=per,
                    num_venda=num,
                    line_id=line_id,
                    responsavel=responsavel,
                ),
                titulo_erro="Ação Não Permitida",
                titulo_sucesso="Item Removido",
                mensagem_sucesso="O item foi removido da venda com sucesso.",
                badge_type="CRITICO",
            )

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
