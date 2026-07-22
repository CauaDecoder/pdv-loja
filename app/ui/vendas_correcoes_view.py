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
    confirmar_acao_sensivel,
)
from tema import FONTES, TEMA_ATUAL, moeda

FORMAS_PGTO = ["Debito", "Credito", "Pix", "Dinheiro", "Mais de uma forma"]
BANDEIRAS_DEBITO = ["Visa", "Mastercard", "Elo", "American Express", "Hipercard"]
BANDEIRAS_CREDITO = ["Visa", "Mastercard", "Elo", "American Express", "Hipercard"]
PARCELAS_CREDITO = [str(i) for i in range(1, 13)]


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
        numero = float(texto.replace(",", "."))
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
        card_filtros = Card(self, padding=12)
        card_filtros.pack(fill="x", pady=(0, 12))

        SectionHeader(card_filtros, "Filtros de Pesquisa", "Localize vendas por número, período, pagamento ou responsável.").pack(anchor="w", fill="x", pady=(0, 8))

        row1 = tk.Frame(card_filtros, bg=TEMA_ATUAL["surface"])
        row1.pack(fill="x", pady=(0, 6))

        for text, var, w in (
            ("Nº Venda", self._var_num_venda, 8),
            ("Início (DD/MM/AAAA)", self._var_data_inicio, 12),
            ("Fim (DD/MM/AAAA)", self._var_data_fim, 12),
            ("Responsável", self._var_responsavel, 16),
            ("Produto / Cód.", self._var_produto, 18),
        ):
            box = tk.Frame(row1, bg=TEMA_ATUAL["surface"])
            box.pack(side="left", padx=(0, 10))
            tk.Label(box, text=text, bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
            entry = StyledEntry(box, width=w, textvariable=var)
            entry.pack(fill="x", ipady=4)
            entry.bind("<Return>", lambda _: self.atualizar())

        row2 = tk.Frame(card_filtros, bg=TEMA_ATUAL["surface"])
        row2.pack(fill="x", pady=(4, 0))

        box_pgto = tk.Frame(row2, bg=TEMA_ATUAL["surface"])
        box_pgto.pack(side="left", padx=(0, 10))
        tk.Label(box_pgto, text="Pagamento", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        cb_pgto = ttk.Combobox(box_pgto, textvariable=self._var_pagamento, values=["Todas"] + FORMAS_PGTO, state="readonly", width=16)
        cb_pgto.pack(fill="x", ipady=3)

        box_status = tk.Frame(row2, bg=TEMA_ATUAL["surface"])
        box_status.pack(side="left", padx=(0, 16))
        tk.Label(box_status, text="Status", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        cb_status = ttk.Combobox(box_status, textvariable=self._var_status, values=["Todos", "Válida", "Corrigida", "Cancelada"], state="readonly", width=14)
        cb_status.pack(fill="x", ipady=3)

        botoes = tk.Frame(row2, bg=TEMA_ATUAL["surface"])
        botoes.pack(side="right", pady=(10, 0))

        action_button(botoes, text="🔍 Filtrar", command=self.atualizar, variant="primary").pack(side="right", padx=(6, 0))
        action_button(botoes, text="🧹 Limpar", command=self._limpar_filtros, variant="secondary").pack(side="right")

    def _build_tabela_card(self):
        self._card_tabela = Card(self, padding=0)
        self._card_tabela.pack(fill="both", expand=True)

        colunas = ("venda", "data_hora", "total", "pagamento", "itens", "responsavel", "status")
        titulos = {
            "venda": "Venda",
            "data_hora": "Data / Hora",
            "total": "Total",
            "pagamento": "Forma de Pagamento",
            "itens": "Itens",
            "responsavel": "Responsável",
            "status": "Status",
        }
        larguras = {
            "venda": 80,
            "data_hora": 130,
            "total": 110,
            "pagamento": 210,
            "itens": 150,
            "responsavel": 160,
            "status": 110,
        }

        self._tree = DataTable(self._card_tabela, colunas, titulos, larguras, height=12)
        self._tree.column("pagamento", anchor="w")
        self._tree.column("responsavel", anchor="w")
        self._tree.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(self._card_tabela, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

        self._tree.bind("<Double-1>", lambda _: self._abrir_detalhe_selecionado())

        # Frame de Ações da Tabela
        self._bar_acoes = tk.Frame(self, bg=TEMA_ATUAL["fundo"])
        self._bar_acoes.pack(fill="x", pady=(10, 0))

        action_button(
            self._bar_acoes,
            text="👁️ Ver Detalhes / Corrigir Venda ➔",
            command=self._abrir_detalhe_selecionado,
            variant="primary",
        ).pack(side="right")

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

        for item in self._tree.get_children():
            self._tree.delete(item)

        status_labels = {
            "valid": "VÁLIDA",
            "corrected": "CORRIGIDA",
            "cancelled": "CANCELADA",
        }

        for idx, v in enumerate(vendas):
            s_code = v.get("status", "valid")
            s_str = status_labels.get(s_code, s_code.upper())
            sold_at = v.get("sold_at", {})
            dt_str = f"{sold_at.get('date', '')} {sold_at.get('time', '')}".strip()

            self._tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    f"#{v.get('sale_number', 0):03d}",
                    dt_str,
                    moeda(float(v.get("total", 0))),
                    v.get("payment_summary", ""),
                    v.get("item_summary", {}).get("label", ""),
                    v.get("responsible", ""),
                    s_str,
                ),
            )

    def _limpar_filtros(self):
        self._var_num_venda.set("")
        self._var_data_inicio.set("")
        self._var_data_fim.set("")
        self._var_pagamento.set("Todas")
        self._var_status.set("Todos")
        self._var_responsavel.set("")
        self._var_produto.set("")
        self.atualizar()

    def _abrir_detalhe_selecionado(self):
        selecao = self._tree.selection()
        if not selecao:
            messagebox.showinfo("Selecionar Venda", "Selecione uma venda na tabela para visualizar os detalhes.")
            return

        idx = int(selecao[0])
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
        StatusBadge(right_hdr, badge_txt).pack(side="right")

        # Scrollable Content Area
        content = tk.Frame(self, bg=TEMA_ATUAL["fundo"], padx=18)
        content.pack(fill="both", expand=True)

        # 1. Resumo Financeiro & Pagamento
        card_pag = Card(content, padding=14)
        card_pag.pack(fill="x", pady=(0, 12))

        SectionHeader(card_pag, "Pagamento & Resumo Financeiro", "Detalhes da forma de pagamento e total.").pack(anchor="w", fill="x", pady=(0, 6))

        pag_info = det.get("payment", {})
        metodo = pag_info.get("method", "Desconhecido")
        detalhe_met = pag_info.get("detail", "")
        txt_pag = f"{metodo} | {detalhe_met}" if detalhe_met else metodo
        recebido = pag_info.get("received")
        troco = pag_info.get("change")
        detalhes_financeiros = []
        if recebido is not None:
            detalhes_financeiros.append(f"Recebido: {moeda(float(recebido))}")
        if troco is not None:
            detalhes_financeiros.append(f"Troco: {moeda(float(troco))}")

        totals = det.get("totals", {})

        row_p = tk.Frame(card_pag, bg=TEMA_ATUAL["surface"])
        row_p.pack(fill="x")

        tk.Label(row_p, text=f"Forma: {txt_pag}", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto"], font=FONTES["corpo_bold"]).pack(side="left")
        tk.Label(row_p, text=f"Total: {moeda(float(totals.get('total', 0)))}", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["primary"], font=FONTES["subtitulo"]).pack(side="right")
        if detalhes_financeiros:
            tk.Label(
                card_pag,
                text=" | ".join(detalhes_financeiros),
                bg=TEMA_ATUAL["surface"],
                fg=TEMA_ATUAL["texto_suave"],
                font=FONTES["corpo"],
            ).pack(anchor="w", pady=(6, 0))

        # 2. Tabela de Itens da Venda
        card_itens = Card(content, padding=12)
        card_itens.pack(fill="x", pady=(0, 12))

        SectionHeader(card_itens, f"Itens da Venda ({totals.get('items', 0)} itens, {totals.get('units', 0)} un.)", "Produtos registrados no caixa.").pack(anchor="w", fill="x", pady=(0, 6))

        colunas = ("codigo", "produto", "qtd", "preco", "subtotal")
        titulos = {"codigo": "Cód.", "produto": "Produto", "qtd": "Qtd", "preco": "Preço Unit.", "subtotal": "Subtotal"}
        larguras = {"codigo": 90, "produto": 260, "qtd": 60, "preco": 100, "subtotal": 110}

        self._tree_items = DataTable(card_itens, colunas, titulos, larguras, height=5)
        self._tree_items.column("produto", anchor="w")
        self._tree_items.pack(fill="x")

        for item in det.get("items", []):
            self._tree_items.insert(
                "",
                "end",
                iid=str(item.get("line_id", 0)),
                values=(
                    item.get("code", ""),
                    item.get("name", ""),
                    item.get("quantity", 0),
                    moeda(float(item.get("unit_price", 0))),
                    moeda(float(item.get("subtotal", 0))),
                ),
            )

        # 3. Histórico de Correções
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

        # 4. Painel de Ações Disponíveis
        card_acoes = Card(content, padding=14)
        card_acoes.pack(fill="x", pady=(0, 14))

        if status == "cancelled":
            tk.Label(
                card_acoes,
                text="⚠️ Venda Cancelada: Esta venda foi anulada e não permite novas correções pós-venda.",
                bg=TEMA_ATUAL["surface"],
                fg=TEMA_ATUAL["danger"],
                font=FONTES["corpo_bold"],
            ).pack(anchor="w")
        else:
            SectionHeader(card_acoes, "Ações de Correção Pós-Venda", "Selecione uma ação autorizada.").pack(anchor="w", fill="x", pady=(0, 8))

            grid_botoes = tk.Frame(card_acoes, bg=TEMA_ATUAL["surface"])
            grid_botoes.pack(fill="x")

            acoes = set(det.get("available_actions", []))
            botoes = (
                ("💳 Alterar Pagamento", self._alterar_pagamento, "secondary", "alter_payment", "left"),
                ("✏️ Alterar Quantidade", self._alterar_quantidade, "secondary", "alter_item_quantity", "left"),
                ("🗑️ Remover Item", self._remover_item, "danger", "remove_item", "left"),
                ("🚫 Cancelar Venda", self._cancelar_venda, "danger", "cancel_sale", "right"),
            )
            for texto, comando, variante, acao, lado in botoes:
                botao = action_button(
                    grid_botoes,
                    text=texto,
                    command=comando,
                    variant=variante,
                    state="normal" if acao in acoes else "disabled",
                )
                botao.pack(side=lado, padx=(0, 6) if lado == "left" else 0)

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
        """Abre o sub-diálogo para alterar o pagamento da venda."""
        det = self._detalhe
        per, num = self._identidade_venda()

        sub = tk.Toplevel(self)
        sub.title(f"Alterar pagamento da Venda #{num:03d}")
        sub.geometry("450x500")
        sub.configure(bg=TEMA_ATUAL["fundo"])
        sub.transient(self)
        sub.grab_set()

        pad = Card(sub, padding=18)
        pad.pack(fill="both", expand=True, padx=14, pady=14)

        SectionHeader(pad, "Alterar Forma de Pagamento", f"Defina a nova forma para a Venda #{num:03d}.").pack(anchor="w", fill="x", pady=(0, 10))

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

        tk.Label(pad, text="Forma de Pagamento", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        ttk.Combobox(pad, textvariable=var_pgto, values=FORMAS_PGTO, state="readonly").pack(fill="x", pady=(2, 10))

        tk.Label(pad, text="Detalhes (Bandeira/Parcelas)", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        StyledEntry(pad, textvariable=var_detalhe).pack(fill="x", ipady=4, pady=(2, 10))

        valores = tk.Frame(pad, bg=TEMA_ATUAL["surface"])
        valores.pack(fill="x", pady=(0, 10))
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

        tk.Label(pad, text="Responsável pela Alteração *", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        StyledEntry(pad, textvariable=var_resp).pack(fill="x", ipady=4, pady=(2, 14))

        def confirmar():
            if not var_resp.get().strip():
                messagebox.showerror("Campo Obrigatório", "Informe o nome do responsável pela correção.", parent=sub)
                return
            try:
                valor_recebido = ler_valor_monetario_opcional(
                    var_recebido.get(), "Valor recebido"
                )
                troco = ler_valor_monetario_opcional(var_troco.get(), "Troco")
            except ValueError as erro:
                messagebox.showerror("Pagamento inválido", str(erro), parent=sub)
                return

            self._confirmar_correcao(
                parent=sub,
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
                fechar_ao_concluir=sub,
            )

        action_button(pad, text="Salvar Alteração", command=confirmar, variant="primary").pack(side="right", pady=(10, 0))

    def _alterar_quantidade(self):
        """Altera a quantidade de um item selecionado na tabela."""
        selecao = self._tree_items.selection()
        if not selecao:
            messagebox.showinfo("Selecionar Item", "Selecione um item na tabela acima para alterar a quantidade.", parent=self)
            return

        line_id = int(selecao[0])
        det = self._detalhe
        per, num = self._identidade_venda()

        sub = tk.Toplevel(self)
        sub.title(f"Alterar quantidade - Item #{line_id}")
        sub.geometry("420x300")
        sub.configure(bg=TEMA_ATUAL["fundo"])
        sub.transient(self)
        sub.grab_set()

        pad = Card(sub, padding=18)
        pad.pack(fill="both", expand=True, padx=14, pady=14)

        SectionHeader(pad, "Alterar Quantidade do Item", f"Defina a nova quantidade para a linha #{line_id}.").pack(anchor="w", fill="x", pady=(0, 10))

        var_qtd = tk.StringVar(value="1")
        var_resp = tk.StringVar()

        tk.Label(pad, text="Nova Quantidade (Unidades)", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        StyledEntry(pad, textvariable=var_qtd).pack(fill="x", ipady=4, pady=(2, 10))

        tk.Label(pad, text="Responsável pela Alteração *", bg=TEMA_ATUAL["surface"], fg=TEMA_ATUAL["texto_suave"], font=FONTES["label_sm"]).pack(anchor="w")
        StyledEntry(pad, textvariable=var_resp).pack(fill="x", ipady=4, pady=(2, 14))

        def confirmar():
            if not var_resp.get().strip():
                messagebox.showerror("Campo Obrigatório", "Informe o responsável.", parent=sub)
                return
            try:
                quantidade = ler_quantidade(var_qtd.get())
            except ValueError as erro:
                messagebox.showerror("Quantidade inválida", str(erro), parent=sub)
                return

            self._confirmar_correcao(
                parent=sub,
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
                fechar_ao_concluir=sub,
            )

        action_button(pad, text="Salvar Quantidade", command=confirmar, variant="primary").pack(side="right", pady=(10, 0))

    def _remover_item(self):
        """Remove o item selecionado com confirmacao explicita de risco."""
        selecao = self._tree_items.selection()
        if not selecao:
            messagebox.showinfo("Selecionar Item", "Selecione um item na tabela para remover.", parent=self)
            return

        line_id = int(selecao[0])
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
