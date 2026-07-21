"""Painel Tkinter do módulo de estoque (Variante A - Command Center)."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import database as db
from estoque import calculos
from estoque import relatorio_estoque
from app.ui.components import (
    ActionButton,
    BaseModal,
    Card,
    DataTable,
    EmptyState,
    FocusHelper,
    LabeledField,
    PageHeader,
    Panel,
    SearchInput,
    SectionHeader,
    StatusBadge,
    StyledEntry,
    action_button,
    confirmar_acao_sensivel,
)
from tema import FONTES, ESPACOS, moeda, obter_tema_atual


class PainelEstoque(tk.Frame):
    def __init__(self, parent):
        tema = obter_tema_atual()
        super().__init__(parent, bg=tema["bg"])
        self._produtos: list[dict] = []
        self._resumo_labels: dict[str, tk.Label] = {}
        self._var_busca = tk.StringVar()
        self._var_status = tk.StringVar(value="Todos")
        self._var_abc = tk.StringVar(value="Todos")
        self._var_categoria = tk.StringVar(value="Todas")
        self._var_fornecedor = tk.StringVar(value="Todos")
        self._var_ativos = tk.StringVar(value="Ativos")
        self._var_sem_custo = tk.BooleanVar(value=False)
        self._var_sem_minimo = tk.BooleanVar(value=False)
        self._var_sem_movimento = tk.BooleanVar(value=False)
        self._categorias = ["Todas"]
        self._fornecedores = ["Todos"]
        self._empty_state: EmptyState | None = None
        self._build_ui()
        self.atualizar()

    def _build_ui(self):
        tema = obter_tema_atual()

        # Cabeçalho da página
        PageHeader(
            self,
            "Estoque",
            "Gestão operacional de produtos, movimentações e baixo estoque em uma visão unificada.",
            "Atualizar",
            self.atualizar,
        ).pack(fill="x", padx=ESPACOS["lg"], pady=ESPACOS["lg"])

        # Cards compactos de indicadores (KPIs)
        cards_frame = tk.Frame(self, bg=tema["bg"], padx=ESPACOS["lg"])
        cards_frame.pack(fill="x", pady=(0, 12))

        kpi_config = (
            ("ativos", "SKUs ativos", "primary"),
            ("inativos", "Inativos", "neutral"),
            ("criticos", "Críticos", "danger"),
            ("alertas", "Em alerta", "warning"),
            ("sem_custo", "Sem custo", "danger"),
            ("mortos", "Sem giro", "neutral"),
            ("valor_total_custo", "Valor a custo", "primary"),
            ("valor_total_venda", "Valor a venda", "gold"),
        )

        for chave, titulo, tipo_cor in kpi_config:
            card = Card(cards_frame, padding=10)
            card.pack(side="left", fill="x", expand=True, padx=(0, 6))

            # Indicador de topo de card
            bar_color = (
                tema["danger"]
                if tipo_cor == "danger"
                else (
                    tema["warning"]
                    if tipo_cor == "warning"
                    else (
                        tema["gold"]
                        if tipo_cor == "gold"
                        else (tema["primary"] if tipo_cor == "primary" else tema["border"])
                    )
                )
            )
            tk.Frame(card, bg=bar_color, height=3).pack(fill="x", pady=(0, 6))

            tk.Label(card, text=titulo, bg=tema["surface"], fg=tema["text_muted"], font=FONTES["label_sm"]).pack(
                anchor="w"
            )
            lbl = tk.Label(card, text="0", bg=tema["surface"], fg=tema["text"], font=FONTES["numero_card"])
            lbl.pack(anchor="w", pady=(2, 0))
            self._resumo_labels[chave] = lbl

        # Card de Busca e Filtros
        filtros_card = Card(self, padding=ESPACOS["lg"])
        filtros_card.pack(fill="x", padx=ESPACOS["lg"], pady=(0, ESPACOS["sm"]))

        SectionHeader(
            filtros_card,
            "Busca e filtros",
            "Localize rapidamente produtos ou filtre por categoria, curva ABC e status.",
        ).pack(anchor="w", pady=(0, 8))

        # Campo de Busca proeminente (SearchInput)
        self._search_input = SearchInput(
            filtros_card,
            textvariable=self._var_busca,
            placeholder="Buscar por código, código de barras ou nome do produto...",
            on_return=self._renderizar_tabela,
        )
        self._search_input.pack(fill="x", pady=(0, 10))
        self._var_busca.trace_add("write", lambda *_: self._renderizar_tabela())

        # Controles de Filtro secundários
        filtros_grid = tk.Frame(filtros_card, bg=tema["surface"])
        filtros_grid.pack(fill="x", pady=(0, 8))

        # Configurar colunas responsivas
        for c in range(6):
            filtros_grid.columnconfigure(c, weight=1 if c < 5 else 0)

        tk.Label(filtros_grid, text="Status", bg=tema["surface"], fg=tema["text_muted"], font=FONTES["label_sm"]).grid(
            row=0, column=0, sticky="w", padx=(0, 6)
        )
        self._status_box = ttk.Combobox(
            filtros_grid,
            textvariable=self._var_status,
            values=["Todos", "CRITICO", "ALERTA", "OK", "MORTO"],
            state="readonly",
            width=12,
        )
        self._status_box.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(2, 0))

        tk.Label(filtros_grid, text="Curva ABC", bg=tema["surface"], fg=tema["text_muted"], font=FONTES["label_sm"]).grid(
            row=0, column=1, sticky="w", padx=(0, 6)
        )
        self._abc_box = ttk.Combobox(
            filtros_grid,
            textvariable=self._var_abc,
            values=["Todos", "A", "B", "C"],
            state="readonly",
            width=10,
        )
        self._abc_box.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(2, 0))

        tk.Label(filtros_grid, text="Categoria", bg=tema["surface"], fg=tema["text_muted"], font=FONTES["label_sm"]).grid(
            row=0, column=2, sticky="w", padx=(0, 6)
        )
        self._categoria_box = ttk.Combobox(
            filtros_grid,
            textvariable=self._var_categoria,
            values=self._categorias,
            state="readonly",
            width=16,
        )
        self._categoria_box.grid(row=1, column=2, sticky="ew", padx=(0, 8), pady=(2, 0))

        tk.Label(
            filtros_grid, text="Fornecedor", bg=tema["surface"], fg=tema["text_muted"], font=FONTES["label_sm"]
        ).grid(row=0, column=3, sticky="w", padx=(0, 6))
        self._fornecedor_box = ttk.Combobox(
            filtros_grid,
            textvariable=self._var_fornecedor,
            values=self._fornecedores,
            state="readonly",
            width=16,
        )
        self._fornecedor_box.grid(row=1, column=3, sticky="ew", padx=(0, 8), pady=(2, 0))

        tk.Label(filtros_grid, text="Situação", bg=tema["surface"], fg=tema["text_muted"], font=FONTES["label_sm"]).grid(
            row=0, column=4, sticky="w", padx=(0, 6)
        )
        self._ativos_box = ttk.Combobox(
            filtros_grid,
            textvariable=self._var_ativos,
            values=["Ativos", "Inativos", "Todos"],
            state="readonly",
            width=10,
        )
        self._ativos_box.grid(row=1, column=4, sticky="ew", padx=(0, 8), pady=(2, 0))

        btn_limpar = action_button(
            filtros_grid,
            text="Limpar Filtros",
            command=self._limpar_filtros,
            variant="ghost",
            padx=12,
            pady=6,
        )
        btn_limpar.grid(row=1, column=5, sticky="e", pady=(2, 0))

        self._var_status.trace_add("write", lambda *_: self._renderizar_tabela())
        self._var_abc.trace_add("write", lambda *_: self._renderizar_tabela())
        self._var_categoria.trace_add("write", lambda *_: self._renderizar_tabela())
        self._var_fornecedor.trace_add("write", lambda *_: self._renderizar_tabela())
        self._var_ativos.trace_add("write", lambda *_: self._renderizar_tabela())

        # Checkboxes secundários
        filtros2 = tk.Frame(filtros_card, bg=tema["surface"])
        filtros2.pack(fill="x", pady=(6, 4))
        for i, (texto, var) in enumerate(
            (
                ("Sem custo cadastrado", self._var_sem_custo),
                ("Sem mínimo configurado", self._var_sem_minimo),
                ("Sem movimentação recente", self._var_sem_movimento),
            )
        ):
            cb = tk.Checkbutton(
                filtros2,
                text=texto,
                variable=var,
                bg=tema["surface"],
                fg=tema["text"],
                selectcolor=tema["surface_3"],
                activebackground=tema["surface"],
                command=self._renderizar_tabela,
                relief="flat",
                padx=6,
                pady=2,
                font=FONTES["corpo"],
                highlightthickness=0,
            )
            cb.grid(row=0, column=i, sticky="w", padx=(0, 14))

        self._lbl_resultados = tk.Label(
            filtros_card,
            text="0 produtos encontrados",
            bg=tema["surface"],
            fg=tema["text_muted"],
            font=FONTES["corpo"],
        )
        self._lbl_resultados.pack(anchor="w", pady=(4, 0))

        # Tabela de Produtos (Container)
        self._tabela_box = Card(self, padding=0)
        self._tabela_box.pack(fill="both", expand=True, padx=ESPACOS["lg"])

        colunas = ("codigo", "produto", "categoria", "qtd", "minimo", "pedido", "abc", "demanda", "status", "ativo")
        self._tree = ttk.Treeview(self._tabela_box, columns=colunas, show="headings", height=14)
        titulos = {
            "codigo": "Cód.",
            "produto": "Produto",
            "categoria": "Categoria",
            "qtd": "Qtd",
            "minimo": "Mín.",
            "pedido": "Pedido",
            "abc": "ABC",
            "demanda": "Demanda/dia",
            "status": "Status",
            "ativo": "Ativo",
        }
        larguras = {
            "codigo": 90,
            "produto": 440,
            "categoria": 150,
            "qtd": 70,
            "minimo": 70,
            "pedido": 80,
            "abc": 60,
            "demanda": 110,
            "status": 120,
            "ativo": 70,
        }
        for coluna in colunas:
            self._tree.heading(coluna, text=titulos[coluna])
            self._tree.column(coluna, width=larguras[coluna], anchor="center")
        self._tree.column("produto", anchor="w")
        self._tree.column("categoria", anchor="w")

        # Configuração de tags com cores dinâmicas do tema
        self._configurar_tags_tabela()

        self._tree.bind("<Double-1>", lambda _event: self._abrir_detalhe())

        self._scroll = ttk.Scrollbar(self._tabela_box, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=self._scroll.set)
        self._tree.pack(side="left", fill="both", expand=True)
        self._scroll.pack(side="right", fill="y")

        # Componente de Estado Vazio
        self._empty_state = EmptyState(
            self._tabela_box,
            title="Nenhum produto encontrado",
            subtitle="Tente alterar os termos da busca ou redefinir os filtros aplicados.",
            icon_symbol="⌕",
            action_text="Limpar Filtros",
            action=self._limpar_filtros,
        )

        # Barra de Ações Operacionais (Rodapé)
        acoes_frame = tk.Frame(self, bg=tema["bg"], padx=ESPACOS["lg"], pady=12)
        acoes_frame.pack(fill="x")

        # Flex-like container para botões operacionais
        btn_box = tk.Frame(acoes_frame, bg=tema["bg"])
        btn_box.pack(fill="x")

        botoes_esquerda = [
            ("Novo Produto", "primary", self._novo_produto),
            ("Entrada", "primary", self._entrada),
            ("Inventário", "secondary", self._ajuste),
            ("Editar Cadastro", "secondary", self._editar_cadastro),
            ("Detalhes", "secondary", self._abrir_detalhe),
            ("Movimentações", "secondary", self._abrir_movimentacoes),
        ]

        for texto, variant, cmd in botoes_esquerda:
            action_button(btn_box, text=texto, command=cmd, variant=variant, padx=14, pady=8).pack(
                side="left", padx=(0, 6)
            )

        botoes_direita = [
            ("Perda", "danger", self._perda),
            ("Inativar/Reativar", "gold", self._alternar_ativo),
            ("Exportar XLSX", "ghost", self._exportar),
        ]

        for texto, variant, cmd in botoes_direita:
            action_button(btn_box, text=texto, command=cmd, variant=variant, padx=14, pady=8).pack(
                side="right", padx=(6, 0)
            )

    def _configurar_tags_tabela(self):
        tema = obter_tema_atual()
        self._tree.tag_configure("CRITICO", background=tema["danger_soft"], foreground=tema["danger"])
        self._tree.tag_configure("ALERTA", background=tema["warning_soft"], foreground=tema["warning"])
        self._tree.tag_configure("OK", background=tema["surface"], foreground=tema["text"])
        self._tree.tag_configure("MORTO", background=tema["neutral_soft"], foreground=tema["text_muted"])
        self._tree.tag_configure("INATIVO", background=tema["neutral_soft"], foreground=tema["text_muted"])

    def _limpar_filtros(self):
        self._var_busca.set("")
        self._var_status.set("Todos")
        self._var_abc.set("Todos")
        self._var_categoria.set("Todas")
        self._var_fornecedor.set("Todos")
        self._var_ativos.set("Ativos")
        self._var_sem_custo.set(False)
        self._var_sem_minimo.set(False)
        self._var_sem_movimento.set(False)
        self._renderizar_tabela()

    def atualizar(self):
        tema = obter_tema_atual()
        self.configure(bg=tema["bg"])
        self._configurar_tags_tabela()

        produtos = db.listar_produtos_estoque(incluir_inativos=True)
        config = db.configuracoes()
        self._categorias = ["Todas"] + db.opcoes_produtos("categoria")
        self._fornecedores = ["Todos"] + db.opcoes_produtos("fornecedor")
        self._categoria_box.configure(values=self._categorias)
        self._fornecedor_box.configure(values=self._fornecedores)
        if self._var_categoria.get() not in self._categorias:
            self._var_categoria.set("Todas")
        if self._var_fornecedor.get() not in self._fornecedores:
            self._var_fornecedor.set("Todos")
        with db.get_conn() as conn:
            self._produtos = calculos.indicadores_produtos(conn, produtos, config)
        resumo = calculos.resumo_estoque(self._produtos)
        ativos = sum(1 for produto in self._produtos if int(produto.get("ativo") or 1) == 1)
        inativos = sum(1 for produto in self._produtos if int(produto.get("ativo") or 1) == 0)
        sem_custo = sum(1 for produto in self._produtos if float(produto.get("custo_unitario") or 0) <= 0)

        self._resumo_labels["ativos"].config(text=str(ativos), fg=tema["text"])
        self._resumo_labels["inativos"].config(text=str(inativos), fg=tema["text_muted"])
        self._resumo_labels["criticos"].config(text=str(resumo["criticos"]), fg=tema["danger"])
        self._resumo_labels["alertas"].config(text=str(resumo["alertas"]), fg=tema["warning"])
        self._resumo_labels["sem_custo"].config(text=str(sem_custo), fg=tema["danger"])
        self._resumo_labels["mortos"].config(text=str(resumo["mortos"]), fg=tema["text_muted"])
        self._resumo_labels["valor_total_custo"].config(text=moeda(resumo["valor_total_custo"]), fg=tema["primary"])
        self._resumo_labels["valor_total_venda"].config(text=moeda(resumo["valor_total_venda"]), fg=tema["gold"])

        self._renderizar_tabela()

    def _produtos_filtrados(self) -> list[dict]:
        termo = self._var_busca.get().strip().lower()
        status = self._var_status.get()
        abc = self._var_abc.get()
        categoria = self._var_categoria.get()
        fornecedor = self._var_fornecedor.get()
        ativos = self._var_ativos.get()
        produtos = []
        for produto in self._produtos:
            cod_barras = str(produto.get("cod_barras") or "").lower()
            if (
                termo
                and termo not in produto["nome"].lower()
                and termo not in produto["codigo"].lower()
                and termo not in cod_barras
            ):
                continue
            if status != "Todos" and produto["status"] != status:
                continue
            if abc != "Todos" and (produto.get("curva_abc") or "") != abc:
                continue
            if categoria != "Todas" and (produto.get("categoria") or "") != categoria:
                continue
            if fornecedor != "Todos" and (produto.get("fornecedor") or "") != fornecedor:
                continue
            ativo = int(produto.get("ativo") or 0)
            if ativos == "Ativos" and ativo != 1:
                continue
            if ativos == "Inativos" and ativo != 0:
                continue
            if self._var_sem_custo.get() and float(produto.get("custo_unitario") or 0) > 0:
                continue
            if self._var_sem_minimo.get() and int(produto.get("estoque_minimo") or 0) > 0:
                continue
            if self._var_sem_movimento.get() and produto.get("status") != "MORTO":
                continue
            produtos.append(produto)
        return produtos

    def _renderizar_tabela(self):
        produtos = self._produtos_filtrados()
        self._lbl_resultados.config(text=f"{len(produtos)} produto{'s' if len(produtos) != 1 else ''} encontrado{'s' if len(produtos) != 1 else ''}")

        for item in self._tree.get_children():
            self._tree.delete(item)

        if not produtos:
            self._tree.pack_forget()
            self._scroll.pack_forget()
            if self._empty_state:
                self._empty_state.pack(fill="both", expand=True)
            return

        if self._empty_state:
            self._empty_state.pack_forget()
        self._tree.pack(side="left", fill="both", expand=True)
        self._scroll.pack(side="right", fill="y")

        for produto in produtos:
            status = produto["status"]
            simbolo_status = {
                "CRITICO": "● Crítico",
                "ALERTA": "● Alerta",
                "OK": "✓ Normal",
                "MORTO": "● Sem giro",
                "INATIVO": "● Inativo",
            }.get(status, status)

            self._tree.insert(
                "",
                "end",
                iid=str(produto["id"]),
                tags=(produto["status"],),
                values=(
                    produto["codigo"],
                    produto["nome"],
                    produto.get("categoria") or "",
                    produto["estoque"],
                    produto["estoque_minimo"],
                    produto["ponto_pedido"],
                    produto.get("curva_abc") or "",
                    f"{produto['demanda_media']:.2f}",
                    simbolo_status,
                    "Sim" if int(produto.get("ativo") or 0) == 1 else "Não",
                ),
            )

    def _produto_selecionado(self) -> dict | None:
        selecao = self._tree.selection()
        if not selecao:
            messagebox.showinfo("Selecionar produto", "Selecione um produto na tabela.")
            return None
        produto_id = int(selecao[0])
        return next((produto for produto in self._produtos if produto["id"] == produto_id), None)

    def _abrir_detalhe(self):
        produto = self._produto_selecionado()
        if not produto:
            return

        tema = obter_tema_atual()
        ativo_str = "Ativo" if int(produto.get("ativo") or 0) == 1 else "Inativo"
        subt = f"Código: {produto['codigo']} | Barras: {produto.get('cod_barras') or '-'} | {ativo_str}"

        win = BaseModal(self, title=produto["nome"], subtitle=subt, width=780, height=620)

        # Body - Cards de métricas
        grid = tk.Frame(win.body_frame, bg=tema["bg"])
        grid.pack(fill="x", pady=(0, 14))

        margem = 0.0
        preco = float(produto.get("preco") or 0)
        custo = float(produto.get("custo_unitario") or 0)
        if preco > 0 and custo > 0:
            margem = ((preco - custo) / preco) * 100
        cobertura = produto.get("cobertura_dias")

        dados = [
            ("Status", produto["status"]),
            ("Curva ABC", produto.get("curva_abc") or "-"),
            ("Categoria", produto.get("categoria") or "-"),
            ("Fornecedor", produto.get("fornecedor") or "-"),
            ("Preço Venda", moeda(preco)),
            ("Custo Unitário", moeda(custo)),
            ("Margem Estimada", f"{margem:.1f}%" if margem else "-"),
            ("Estoque Atual", str(produto.get("estoque") or 0)),
            ("Estoque Mínimo", str(produto.get("estoque_minimo") or 0)),
            ("Ponto de Pedido", str(produto.get("ponto_pedido") or 0)),
            ("Demanda Média/dia", f"{produto.get('demanda_media') or 0:.2f}"),
            ("Cobertura", f"{cobertura:.1f} dias" if cobertura else "Sem demanda"),
            ("Último Movimento", produto.get("ultimo_movimento") or "-"),
            ("Valor a Custo", moeda(float(produto.get("valor_a_custo") or 0))),
            ("Valor a Venda", moeda(float(produto.get("valor_a_venda") or 0))),
        ]

        for idx, (rotulo, valor) in enumerate(dados):
            box = Card(grid, padding=8)
            box.grid(row=idx // 4, column=idx % 4, sticky="ew", padx=(0, 6), pady=(0, 6))
            tk.Label(box, text=rotulo, bg=tema["surface"], fg=tema["text_muted"], font=FONTES["label_sm"]).pack(
                anchor="w"
            )
            tk.Label(box, text=valor, bg=tema["surface"], fg=tema["text"], font=FONTES["subtitulo"]).pack(
                anchor="w", pady=(1, 0)
            )
            grid.columnconfigure(idx % 4, weight=1)

        # Histórico de movimentações recentes
        tk.Label(
            win.body_frame,
            text="Movimentações Recentes",
            bg=tema["bg"],
            fg=tema["text"],
            font=FONTES["secao"],
        ).pack(anchor="w", pady=(4, 6))

        tbl_frame = Card(win.body_frame, padding=0)
        tbl_frame.pack(fill="both", expand=True)

        colunas = ("data", "tipo", "qtd", "saldo", "ref", "obs")
        tree = ttk.Treeview(tbl_frame, columns=colunas, show="headings", height=6)
        titulos = {
            "data": "Data",
            "tipo": "Tipo",
            "qtd": "Qtd",
            "saldo": "Saldo",
            "ref": "Referência",
            "obs": "Observação",
        }
        for col in colunas:
            tree.heading(col, text=titulos[col])
            tree.column(col, width=100, anchor="center")
        tree.column("obs", width=220, anchor="w")

        tree_scroll = ttk.Scrollbar(tbl_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        for mov in db.obter_movimentacoes_produto(produto["id"], limite=30):
            tree.insert(
                "",
                "end",
                values=(
                    f"{mov['data']} {mov['hora']}",
                    mov["tipo"],
                    mov["quantidade"],
                    mov["estoque_resultante"],
                    mov["referencia"] or "",
                    mov["observacao"] or "",
                ),
            )

        # Footer
        action_button(
            win.footer_frame,
            text="Editar Cadastro",
            command=lambda: [win.close(), self._editar_cadastro()],
            variant="primary",
        ).pack(side="right", padx=(8, 0))

        action_button(
            win.footer_frame,
            text="Fechar",
            command=win.close,
            variant="ghost",
        ).pack(side="right")

    def _novo_produto(self):
        dados = self._form_produto("Novo produto")
        if not dados:
            return
        try:
            db.criar_produto(dados)
        except Exception as erro:
            messagebox.showerror("Erro no cadastro", str(erro))
            return
        self.atualizar()

    def _editar_cadastro(self):
        produto = self._produto_selecionado()
        if not produto:
            return
        dados = self._form_produto("Editar produto", produto)
        if not dados:
            return
        try:
            db.atualizar_produto(produto["id"], dados)
        except Exception as erro:
            messagebox.showerror("Erro na edição", str(erro))
            return
        self.atualizar()

    def _form_produto(self, titulo: str, produto: dict | None = None) -> dict | None:
        win = BaseModal(self, title=titulo, width=640, height=680)

        canvas = tk.Canvas(win.body_frame, bg=obter_tema_atual()["bg"], highlightthickness=0)
        scroll = ttk.Scrollbar(win.body_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        frame = tk.Frame(canvas, bg=obter_tema_atual()["bg"])
        janela = canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(janela, width=e.width))

        if produto:
            tk.Label(
                frame,
                text=f"Estoque atual: {produto.get('estoque') or 0}. Use Entrada, Inventário ou Perda para alterar saldo.",
                bg=obter_tema_atual()["bg"],
                fg=obter_tema_atual()["text_muted"],
                font=FONTES["corpo"],
            ).pack(anchor="w", pady=(0, 10))

        campos: dict[str, tk.StringVar] = {}

        def criar_campo(label: str, chave: str, padrao: str = ""):
            var = tk.StringVar(value=str((produto or {}).get(chave) or padrao))
            lf = LabeledField(
                frame,
                label=label,
                widget_factory=lambda parent: StyledEntry(parent, textvariable=var),
                bg=obter_tema_atual()["bg"],
            )
            lf.widget.pack(fill="x", ipady=4)
            lf.pack(fill="x", pady=(0, 8))
            campos[chave] = var

        criar_campo("Código Interno", "codigo")
        criar_campo("Código de Barras", "cod_barras")
        criar_campo("Nome do Produto", "nome")
        criar_campo("Categoria", "categoria")
        criar_campo("Fornecedor", "fornecedor")
        criar_campo("Unidade", "unidade", "un")
        criar_campo("Preço de Venda (R$)", "preco", "0")
        criar_campo("Custo Unitário (R$)", "custo_unitario", "0")

        if not produto:
            criar_campo("Estoque Inicial", "estoque_inicial", "0")

        criar_campo("Estoque Mínimo", "estoque_minimo", "0")
        criar_campo("Ponto de Pedido", "ponto_pedido", "0")
        criar_campo("Lead Time em dias", "lead_time_dias", "7")
        criar_campo("Curva ABC Manual", "curva_abc")
        criar_campo("Observações Internas", "observacoes")

        ativo_var = tk.BooleanVar(value=bool(int((produto or {}).get("ativo", 1) or 0)))
        cb_ativo = tk.Checkbutton(
            frame,
            text="Produto ativo",
            variable=ativo_var,
            bg=obter_tema_atual()["bg"],
            fg=obter_tema_atual()["text"],
            selectcolor=obter_tema_atual()["surface_3"],
            activebackground=obter_tema_atual()["bg"],
            font=FONTES["corpo"],
        )
        cb_ativo.pack(anchor="w", pady=(4, 10))

        resultado = {"dados": None}

        def numero_float(chave: str) -> float:
            return float((campos[chave].get() or "0").replace(",", "."))

        def numero_int(chave: str) -> int:
            return int(campos[chave].get() or 0)

        def confirmar():
            try:
                dados = {
                    "codigo": campos["codigo"].get(),
                    "cod_barras": campos["cod_barras"].get(),
                    "nome": campos["nome"].get(),
                    "categoria": campos["categoria"].get(),
                    "fornecedor": campos["fornecedor"].get(),
                    "unidade": campos["unidade"].get(),
                    "preco": numero_float("preco"),
                    "custo_unitario": numero_float("custo_unitario"),
                    "estoque_minimo": numero_int("estoque_minimo"),
                    "ponto_pedido": numero_int("ponto_pedido"),
                    "lead_time_dias": numero_int("lead_time_dias"),
                    "curva_abc": campos["curva_abc"].get(),
                    "observacoes": campos["observacoes"].get(),
                    "ativo": 1 if ativo_var.get() else 0,
                }
                if not produto:
                    dados["estoque_inicial"] = numero_int("estoque_inicial")
            except ValueError:
                messagebox.showerror("Dados inválidos", "Revise os campos numéricos.")
                return
            resultado["dados"] = dados
            win.close()

        action_button(win.footer_frame, text="Cancelar", command=win.close, variant="ghost").pack(
            side="right", padx=(8, 0)
        )
        action_button(win.footer_frame, text="Salvar Produto", command=confirmar, variant="primary").pack(
            side="right"
        )

        self.wait_window(win)
        return resultado["dados"]

    def _dialog_produto_quantidade(self, titulo: str, pedir_custo: bool = False):
        produtos = self._produtos_filtrados() or self._produtos
        if not produtos:
            messagebox.showinfo("Sem produtos", "Nenhum produto encontrado.")
            return None

        tema = obter_tema_atual()
        win = BaseModal(self, title=titulo, subtitle="Selecione o produto e informe a quantidade", width=540, height=420)

        mapa = {f"{p['codigo']} - {p['nome']}": p for p in produtos}

        tk.Label(win.body_frame, text="Produto", bg=tema["bg"], fg=tema["text_muted"], font=FONTES["label_sm"]).pack(
            anchor="w", pady=(0, 2)
        )
        produto_var = tk.StringVar(value=f"{produtos[0]['codigo']} - {produtos[0]['nome']}")
        box_prod = ttk.Combobox(win.body_frame, textvariable=produto_var, values=list(mapa), state="readonly")
        box_prod.pack(fill="x", pady=(0, 10))

        qtd_var = tk.StringVar()
        lf_qtd = LabeledField(
            win.body_frame,
            label="Quantidade",
            widget_factory=lambda parent: StyledEntry(parent, textvariable=qtd_var),
            bg=tema["bg"],
        )
        lf_qtd.widget.pack(fill="x", ipady=4)
        lf_qtd.pack(fill="x", pady=(0, 10))

        custo_var = tk.StringVar()
        if pedir_custo:
            lf_custo = LabeledField(
                win.body_frame,
                label="Custo Unitário (Opcional - R$)",
                widget_factory=lambda parent: StyledEntry(parent, textvariable=custo_var),
                bg=tema["bg"],
            )
            lf_custo.widget.pack(fill="x", ipady=4)
            lf_custo.pack(fill="x", pady=(0, 10))

        obs_var = tk.StringVar()
        lf_obs = LabeledField(
            win.body_frame,
            label="Observação",
            widget_factory=lambda parent: StyledEntry(parent, textvariable=obs_var),
            bg=tema["bg"],
        )
        lf_obs.widget.pack(fill="x", ipady=4)
        lf_obs.pack(fill="x", pady=(0, 10))

        resultado = {"ok": False}

        def confirmar():
            resultado["ok"] = True
            win.close()

        action_button(win.footer_frame, text="Cancelar", command=win.close, variant="ghost").pack(
            side="right", padx=(8, 0)
        )
        action_button(win.footer_frame, text="Confirmar", command=confirmar, variant="primary").pack(
            side="right"
        )

        self.wait_window(win)
        if not resultado["ok"]:
            return None
        try:
            quantidade = int(qtd_var.get())
            custo = float(custo_var.get().replace(",", ".")) if custo_var.get().strip() else None
        except ValueError:
            messagebox.showerror("Dados inválidos", "Informe uma quantidade válida.")
            return None
        return mapa[produto_var.get()], quantidade, custo, obs_var.get()

    def _entrada(self):
        dados = self._dialog_produto_quantidade("Entrada de estoque", pedir_custo=True)
        if not dados:
            return
        produto, quantidade, custo, observacao = dados
        db.registrar_entrada_estoque(produto["id"], quantidade, custo_unitario=custo, observacao=observacao)
        self.atualizar()

    def _ajuste(self):
        dados = self._dialog_produto_quantidade("Ajuste por contagem (Inventário)")
        if not dados:
            return
        produto, quantidade, _custo, observacao = dados
        db.ajustar_estoque_por_contagem(produto["id"], quantidade, observacao=observacao)
        self.atualizar()

    def _perda(self):
        dados = self._dialog_produto_quantidade("Registrar perda de estoque")
        if not dados:
            return
        produto, quantidade, _custo, observacao = dados

        def _executar_perda():
            db.registrar_perda_estoque(produto["id"], quantidade, observacao=observacao)
            self.atualizar()

        confirmar_acao_sensivel(
            self,
            title="Confirmar Perda de Estoque",
            risk_description=f"Deseja registrar a saída de {quantidade} unidade(s) do produto '{produto['nome']}' como PERDA DE ESTOQUE?",
            confirm_label="Confirmar Perda",
            badge_type="CRITICO",
            on_confirm=_executar_perda,
        )

    def _alternar_ativo(self):
        produto = self._produto_selecionado()
        if not produto:
            return
        ativo = int(produto.get("ativo") or 0) == 1
        acao = "inativar" if ativo else "reativar"

        def _executar_toggle():
            if ativo:
                db.inativar_produto(produto["id"])
            else:
                db.reativar_produto(produto["id"])
            self.atualizar()

        confirmar_acao_sensivel(
            self,
            title=f"Confirmar {acao.capitalize()} Produto",
            risk_description=f"Deseja {acao} o produto '{produto['nome']}' (Código: {produto['codigo']})?",
            confirm_label=f"Confirmar {acao.capitalize()}",
            badge_type="ALERTA" if ativo else "OK",
            on_confirm=_executar_toggle,
        )

    def _abrir_movimentacoes(self):
        produto = self._produto_selecionado()
        if not produto:
            return

        tema = obter_tema_atual()
        win = BaseModal(
            self,
            title=f"Movimentações - {produto['nome']}",
            subtitle=f"Código {produto['codigo']} | Histórico detalhado de movimentações",
            width=880,
            height=520,
        )

        tbl_frame = Card(win.body_frame, padding=0)
        tbl_frame.pack(fill="both", expand=True)

        colunas = ("data", "tipo", "qtd", "saldo", "origem", "ref", "resp", "obs")
        tree = ttk.Treeview(tbl_frame, columns=colunas, show="headings", height=14)
        titulos = {
            "data": "Data/Hora",
            "tipo": "Tipo",
            "qtd": "Qtd",
            "saldo": "Saldo",
            "origem": "Origem",
            "ref": "Referência",
            "resp": "Responsável",
            "obs": "Observação",
        }
        for col in colunas:
            tree.heading(col, text=titulos[col])
            tree.column(col, width=95, anchor="center")
        tree.column("obs", width=200, anchor="w")

        scroll = ttk.Scrollbar(tbl_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        for mov in db.obter_movimentacoes_produto(produto["id"], limite=200):
            tree.insert(
                "",
                "end",
                values=(
                    f"{mov['data']} {mov['hora']}",
                    mov["tipo"],
                    mov["quantidade"],
                    mov["estoque_resultante"],
                    mov["origem"] or "",
                    mov["referencia"] or "",
                    mov["responsavel"] or "",
                    mov["observacao"] or "",
                ),
            )

        action_button(win.footer_frame, text="Fechar", command=win.close, variant="ghost").pack(side="right")

    def _recalcular_abc(self):
        config = db.configuracoes()
        with db.get_conn() as conn:
            total = calculos.classificar_abc(conn, config)
        self.atualizar()
        messagebox.showinfo("ABC recalculado", f"{total} produtos classificados.")

    def _exportar(self):
        pasta = filedialog.askdirectory(title="Salvar relatório de estoque em...")
        if not pasta:
            return
        caminho = relatorio_estoque.gerar_posicao_estoque(self._produtos_filtrados(), pasta)
        messagebox.showinfo("Relatório gerado", f"Arquivo salvo em:\n{caminho}")
