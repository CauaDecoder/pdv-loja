"""Painel Tkinter do modulo de estoque."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import database as db
from estoque import calculos
from estoque import relatorio_estoque
from app.ui.components import Card, EmptyState, PageHeader, SectionHeader, StatusBadge
from tema import (
    AZUL,
    BORDA,
    BRANCO,
    ESPACOS,
    FONTES,
    FUNDO,
    FUNDO2,
    MUTED,
    STATUS_BG,
    TEXTO,
    VERDE_CLAR,
    VERDE_ESC,
    VERMELHO,
    moeda,
)


class PainelEstoque(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=FUNDO)
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
        self._build_ui()
        self.atualizar()

    def _build_ui(self):
        PageHeader(self, "Estoque", "Produtos, filtros e ações operacionais em uma mesma visão.", "Atualizar", self.atualizar).pack(
            fill="x", padx=ESPACOS["lg"], pady=ESPACOS["lg"]
        )

        cards = tk.Frame(self, bg=FUNDO, padx=ESPACOS["lg"])
        cards.pack(fill="x", pady=(0, 12))
        for chave, titulo in (
            ("ativos", "SKUs ativos"),
            ("inativos", "Inativos"),
            ("criticos", "Criticos"),
            ("alertas", "Em alerta"),
            ("sem_custo", "Sem custo"),
            ("mortos", "Sem giro"),
            ("valor_total_custo", "Valor a custo"),
            ("valor_total_venda", "Valor a venda"),
        ):
            card = Card(cards, padding=14)
            card.pack(side="left", fill="x", expand=True, padx=(0, 8))
            destaque = tk.Frame(card, bg=VERDE_CLAR, height=4)
            destaque.pack(fill="x", pady=(0, ESPACOS["sm"]))
            tk.Label(card, text=titulo, bg=BRANCO, fg=MUTED, font=FONTES["label_sm"]).pack(anchor="w")
            lbl = tk.Label(card, text="0", bg=BRANCO, fg=TEXTO, font=FONTES["numero_card"])
            lbl.pack(anchor="w", pady=(4, 0))
            self._resumo_labels[chave] = lbl

        filtros_card = Card(self, padding=ESPACOS["lg"])
        filtros_card.pack(fill="x", padx=ESPACOS["lg"], pady=(0, ESPACOS["sm"]))
        SectionHeader(filtros_card, "Busca e filtros", "Use a busca principal e refine por status, curva ABC, categoria e fornecedor.").pack(
            anchor="w"
        )
        filtros = tk.Frame(filtros_card, bg=BRANCO)
        filtros.pack(fill="x", pady=(0, 10))
        filtros.columnconfigure(0, weight=1)
        filtros.columnconfigure((1, 2, 3, 4, 5), weight=0)

        busca_frame = tk.Frame(filtros, bg=BRANCO)
        busca_frame.grid(row=0, column=0, columnspan=6, sticky="ew", pady=(0, 10))
        tk.Entry(
            busca_frame,
            textvariable=self._var_busca,
            font=("Segoe UI", 11),
            relief="flat",
            bg=FUNDO2,
            fg=TEXTO,
            insertbackground=VERDE_ESC,
        ).pack(side="left", fill="x", expand=True, ipady=9, ipadx=8)
        self._var_busca.trace_add("write", lambda *_: self._renderizar_tabela())

        self._status_box = ttk.Combobox(filtros, textvariable=self._var_status, values=["Todos", "CRITICO", "ALERTA", "OK", "MORTO"], state="readonly", width=12)
        self._status_box.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self._abc_box = ttk.Combobox(filtros, textvariable=self._var_abc, values=["Todos", "A", "B", "C"], state="readonly", width=10)
        self._abc_box.grid(row=1, column=1, sticky="ew", padx=(0, 8))
        self._categoria_box = ttk.Combobox(filtros, textvariable=self._var_categoria, values=self._categorias, state="readonly", width=16)
        self._categoria_box.grid(row=1, column=2, sticky="ew", padx=(0, 8))
        self._fornecedor_box = ttk.Combobox(filtros, textvariable=self._var_fornecedor, values=self._fornecedores, state="readonly", width=16)
        self._fornecedor_box.grid(row=1, column=3, sticky="ew", padx=(0, 8))
        self._ativos_box = ttk.Combobox(filtros, textvariable=self._var_ativos, values=["Ativos", "Inativos", "Todos"], state="readonly", width=10)
        self._ativos_box.grid(row=1, column=4, sticky="ew", padx=(0, 8))
        tk.Button(filtros, text="Buscar", bg=VERDE_ESC, fg=BRANCO, relief="flat", font=FONTES["botao"], padx=16, pady=9, command=self._renderizar_tabela).grid(row=1, column=5, sticky="ew")
        self._var_status.trace_add("write", lambda *_: self._renderizar_tabela())
        self._var_abc.trace_add("write", lambda *_: self._renderizar_tabela())
        self._var_categoria.trace_add("write", lambda *_: self._renderizar_tabela())
        self._var_fornecedor.trace_add("write", lambda *_: self._renderizar_tabela())
        self._var_ativos.trace_add("write", lambda *_: self._renderizar_tabela())

        filtros2 = tk.Frame(filtros_card, bg=BRANCO)
        filtros2.pack(fill="x", pady=(0, 8))
        for i, (texto, var) in enumerate(
            (
                ("Sem custo", self._var_sem_custo),
                ("Sem mínimo", self._var_sem_minimo),
                ("Sem movimentação recente", self._var_sem_movimento),
            )
        ):
            cb = tk.Checkbutton(
                filtros2,
                text=texto,
                variable=var,
                bg=BRANCO,
                fg=TEXTO,
                selectcolor=BRANCO,
                activebackground=BRANCO,
                command=self._renderizar_tabela,
                relief="flat",
                padx=8,
                pady=4,
                highlightthickness=0,
            )
            cb.grid(row=0, column=i, sticky="w", padx=(0, 10))

        self._lbl_resultados = tk.Label(
            filtros_card,
            text="0 produtos encontrados",
            bg=BRANCO,
            fg=MUTED,
            font=FONTES["corpo"],
        )
        self._lbl_resultados.pack(anchor="w")

        tabela_box = Card(self, padding=0)
        tabela_box.pack(fill="both", expand=True, padx=ESPACOS["lg"])
        colunas = ("codigo", "produto", "categoria", "qtd", "minimo", "pedido", "abc", "demanda", "status", "ativo")
        self._tree = ttk.Treeview(tabela_box, columns=colunas, show="headings", height=16)
        titulos = {
            "codigo": "Cod.",
            "produto": "Produto",
            "categoria": "Categoria",
            "qtd": "Qtd",
            "minimo": "Min.",
            "pedido": "Pedido",
            "abc": "ABC",
            "demanda": "Demanda/dia",
            "status": "Status",
            "ativo": "Ativo",
        }
        larguras = {
            "codigo": 90,
            "produto": 460,
            "categoria": 160,
            "qtd": 74,
            "minimo": 74,
            "pedido": 86,
            "abc": 62,
            "demanda": 120,
            "status": 120,
            "ativo": 72,
        }
        for coluna in colunas:
            self._tree.heading(coluna, text=titulos[coluna])
            self._tree.column(coluna, width=larguras[coluna], anchor="center")
        self._tree.column("produto", anchor="w")
        self._tree.column("categoria", anchor="w")
        self._tree.tag_configure("CRITICO", background="#FCEBEB", foreground="#A32D2D")
        self._tree.tag_configure("ALERTA", background="#FFF5DC", foreground="#A66A00")
        self._tree.tag_configure("OK", background="#FFFFFF", foreground="#1A1A1A")
        self._tree.tag_configure("MORTO", background="#EBEBEB", foreground="#767570")
        self._tree.tag_configure("INATIVO", background="#EBEBEB", foreground="#767570")
        self._tree.bind("<Double-1>", lambda _event: self._abrir_detalhe())
        scroll = ttk.Scrollbar(tabela_box, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        self._tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        acoes = tk.Frame(self, bg=FUNDO, padx=ESPACOS["lg"], pady=12)
        acoes.pack(fill="x")
        for i in range(9):
            acoes.grid_columnconfigure(i, weight=1)
        botoes = [
            ("Novo produto", VERDE_ESC, BRANCO, self._novo_produto),
            ("Editar cadastro", BRANCO, VERDE_ESC, self._editar_cadastro),
            ("Entrada", BRANCO, VERDE_ESC, self._entrada),
            ("Inventario", BRANCO, VERDE_ESC, self._ajuste),
            ("Perda", BRANCO, VERMELHO, self._perda),
            ("Inativar/Reativar", BRANCO, VERMELHO, self._alternar_ativo),
            ("Detalhes", BRANCO, MUTED, self._abrir_detalhe),
            ("Movimentacoes", BRANCO, MUTED, self._abrir_movimentacoes),
            ("Exportar XLSX", BRANCO, AZUL, self._exportar),
        ]
        for idx, (texto, bg, fg, cmd) in enumerate(botoes):
            tk.Button(acoes, text=texto, bg=bg, fg=fg, relief="flat", font=FONTES["botao"], padx=16, pady=10, command=cmd).grid(row=0, column=idx, sticky="ew", padx=4)


    def atualizar(self):
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
        self._resumo_labels["ativos"].config(text=str(ativos))
        self._resumo_labels["inativos"].config(text=str(inativos))
        self._resumo_labels["criticos"].config(text=str(resumo["criticos"]), fg=VERMELHO)
        self._resumo_labels["alertas"].config(text=str(resumo["alertas"]))
        self._resumo_labels["sem_custo"].config(text=str(sem_custo))
        self._resumo_labels["mortos"].config(text=str(resumo["mortos"]))
        self._resumo_labels["valor_total_custo"].config(text=moeda(resumo["valor_total_custo"]), fg=VERDE_ESC)
        self._resumo_labels["valor_total_venda"].config(text=moeda(resumo["valor_total_venda"]), fg=AZUL)
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
            if termo and termo not in produto["nome"].lower() and termo not in produto["codigo"].lower() and termo not in cod_barras:
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
        self._lbl_resultados.config(text=f"{len(produtos)} produtos encontrados")
        for item in self._tree.get_children():
            self._tree.delete(item)
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
                    "Sim" if int(produto.get("ativo") or 0) == 1 else "Nao",
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
        win = tk.Toplevel(self)
        win.title("Detalhe do produto")
        win.configure(bg=FUNDO)
        win.transient(self)
        win.geometry("760x620")
        frame = tk.Frame(win, bg=FUNDO, padx=18, pady=16)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text=produto["nome"], bg=FUNDO, fg=TEXTO, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ativo = "Ativo" if int(produto.get("ativo") or 0) == 1 else "Inativo"
        tk.Label(
            frame,
            text=f"Codigo {produto['codigo']} | Barras {produto.get('cod_barras') or '-'} | {ativo}",
            bg=FUNDO,
            fg=MUTED,
        ).pack(anchor="w", pady=(2, 12))

        grid = tk.Frame(frame, bg=FUNDO)
        grid.pack(fill="x")
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
            ("Preco venda", moeda(preco)),
            ("Custo", moeda(custo)),
            ("Margem estimada", f"{margem:.1f}%" if margem else "-"),
            ("Estoque atual", str(produto.get("estoque") or 0)),
            ("Estoque minimo", str(produto.get("estoque_minimo") or 0)),
            ("Ponto pedido", str(produto.get("ponto_pedido") or 0)),
            ("Demanda media/dia", f"{produto.get('demanda_media') or 0:.2f}"),
            ("Cobertura", f"{cobertura:.1f} dias" if cobertura else "Sem demanda"),
            ("Ultimo movimento", produto.get("ultimo_movimento") or "-"),
            ("Valor a custo", moeda(float(produto.get("valor_a_custo") or 0))),
            ("Valor a venda", moeda(float(produto.get("valor_a_venda") or 0))),
        ]
        for idx, (rotulo, valor) in enumerate(dados):
            box = tk.Frame(grid, bg=BRANCO, padx=10, pady=8, highlightbackground=BORDA, highlightthickness=1)
            box.grid(row=idx // 4, column=idx % 4, sticky="ew", padx=(0, 8), pady=(0, 8))
            tk.Label(box, text=rotulo, bg=BRANCO, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
            tk.Label(box, text=valor, bg=BRANCO, fg=TEXTO, font=("Segoe UI", 10, "bold")).pack(anchor="w")
            grid.columnconfigure(idx % 4, weight=1)

        tk.Label(frame, text="Movimentacoes recentes", bg=FUNDO, fg=TEXTO, font=("Segoe UI", 11, "bold")).pack(
            anchor="w", pady=(8, 4)
        )
        colunas = ("data", "tipo", "qtd", "saldo", "ref", "obs")
        tree = ttk.Treeview(frame, columns=colunas, show="headings", height=8)
        for coluna, titulo in {
            "data": "Data",
            "tipo": "Tipo",
            "qtd": "Qtd",
            "saldo": "Saldo",
            "ref": "Referencia",
            "obs": "Observacao",
        }.items():
            tree.heading(coluna, text=titulo)
            tree.column(coluna, width=110 if coluna != "obs" else 220, anchor="center")
        tree.pack(fill="both", expand=True)
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

        botoes = tk.Frame(frame, bg=FUNDO)
        botoes.pack(fill="x", pady=(10, 0))
        tk.Button(botoes, text="Editar cadastro", bg=VERDE_ESC, fg=BRANCO, relief="flat", command=lambda: [win.destroy(), self._editar_cadastro()]).pack(side="right")

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
            messagebox.showerror("Erro na edicao", str(erro))
            return
        self.atualizar()

    def _form_produto(self, titulo: str, produto: dict | None = None) -> dict | None:
        win = tk.Toplevel(self)
        win.title(titulo)
        win.configure(bg=FUNDO)
        win.geometry("620x680")
        win.transient(self)
        win.grab_set()

        canvas = tk.Canvas(win, bg=FUNDO, highlightthickness=0)
        scroll = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        frame = tk.Frame(canvas, bg=FUNDO, padx=18, pady=16)
        janela = canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(janela, width=e.width))
        self._bind_mousewheel_recursivo(canvas, lambda event: self._rolar_canvas(canvas, event))
        self._bind_mousewheel_recursivo(frame, lambda event: self._rolar_canvas(canvas, event))

        tk.Label(frame, text=titulo, bg=FUNDO, fg=TEXTO, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        if produto:
            tk.Label(
                frame,
                text=f"Estoque atual: {produto.get('estoque') or 0}. Use Entrada, Inventario ou Perda para alterar saldo.",
                bg=FUNDO,
                fg=MUTED,
                font=("Segoe UI", 9),
            ).pack(anchor="w", pady=(2, 10))

        campos: dict[str, tk.StringVar] = {}

        def campo(label: str, chave: str, padrao: str = ""):
            tk.Label(frame, text=label, bg=FUNDO, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(8, 2))
            var = tk.StringVar(value=str((produto or {}).get(chave) or padrao))
            tk.Entry(frame, textvariable=var, bg=BRANCO, fg=TEXTO, relief="flat", font=("Segoe UI", 10)).pack(fill="x", ipady=6)
            campos[chave] = var

        campo("Codigo interno", "codigo")
        campo("Codigo de barras", "cod_barras")
        campo("Nome do produto", "nome")
        campo("Categoria", "categoria")
        campo("Fornecedor", "fornecedor")
        campo("Unidade", "unidade", "un")
        campo("Preco de venda", "preco", "0")
        campo("Custo unitario", "custo_unitario", "0")
        if not produto:
            campo("Estoque inicial", "estoque_inicial", "0")
        campo("Estoque minimo", "estoque_minimo", "0")
        campo("Ponto de pedido", "ponto_pedido", "0")
        campo("Lead time em dias", "lead_time_dias", "7")
        campo("Curva ABC manual", "curva_abc")
        campo("Observacoes internas", "observacoes")

        ativo_var = tk.BooleanVar(value=bool(int((produto or {}).get("ativo", 1) or 0)))
        tk.Checkbutton(
            frame,
            text="Produto ativo",
            variable=ativo_var,
            bg=FUNDO,
            fg=TEXTO,
            selectcolor=BRANCO,
            activebackground=FUNDO,
        ).pack(anchor="w", pady=(10, 0))

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
                messagebox.showerror("Dados invalidos", "Revise os campos numericos.")
                return
            resultado["dados"] = dados
            win.destroy()

        botoes = tk.Frame(frame, bg=FUNDO)
        botoes.pack(fill="x", pady=(14, 0))
        tk.Button(botoes, text="Cancelar", bg=FUNDO2, fg=MUTED, relief="flat", command=win.destroy).pack(side="right", padx=(8, 0))
        tk.Button(botoes, text="Salvar", bg=VERDE_ESC, fg=BRANCO, relief="flat", command=confirmar).pack(side="right")
        self.wait_window(win)
        return resultado["dados"]

    def _rolar_canvas(self, canvas: tk.Canvas, event):
        if event.delta:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return
        if getattr(event, "num", None) == 4:
            canvas.yview_scroll(-1, "units")
        elif getattr(event, "num", None) == 5:
            canvas.yview_scroll(1, "units")

    def _bind_mousewheel_recursivo(self, widget, callback):
        if not widget:
            return

        def ao_rolar(event):
            callback(event)
            return "break"

        widget.bind("<MouseWheel>", ao_rolar, add="+")
        widget.bind("<Button-4>", ao_rolar, add="+")
        widget.bind("<Button-5>", ao_rolar, add="+")
        for child in widget.winfo_children():
            self._bind_mousewheel_recursivo(child, callback)

    def _dialog_produto_quantidade(self, titulo: str, pedir_custo: bool = False):
        produtos = self._produtos_filtrados() or self._produtos
        if not produtos:
            messagebox.showinfo("Sem produtos", "Nenhum produto encontrado.")
            return None
        win = tk.Toplevel(self)
        win.title(titulo)
        win.configure(bg=FUNDO)
        win.transient(self)
        win.grab_set()
        frame = tk.Frame(win, bg=FUNDO, padx=18, pady=16)
        frame.pack(fill="both", expand=True)
        produto_var = tk.StringVar(value=f"{produtos[0]['codigo']} - {produtos[0]['nome']}")
        mapa = {f"{p['codigo']} - {p['nome']}": p for p in produtos}
        ttk.Combobox(frame, textvariable=produto_var, values=list(mapa), state="readonly", width=60).pack(fill="x")
        qtd_var = tk.StringVar()
        tk.Label(frame, text="Quantidade", bg=FUNDO, fg=MUTED).pack(anchor="w", pady=(10, 2))
        tk.Entry(frame, textvariable=qtd_var, bg=BRANCO, fg=TEXTO, relief="flat").pack(fill="x", ipady=6)
        custo_var = tk.StringVar()
        if pedir_custo:
            tk.Label(frame, text="Custo unitario opcional", bg=FUNDO, fg=MUTED).pack(anchor="w", pady=(10, 2))
            tk.Entry(frame, textvariable=custo_var, bg=BRANCO, fg=TEXTO, relief="flat").pack(fill="x", ipady=6)
        obs_var = tk.StringVar()
        tk.Label(frame, text="Observacao", bg=FUNDO, fg=MUTED).pack(anchor="w", pady=(10, 2))
        tk.Entry(frame, textvariable=obs_var, bg=BRANCO, fg=TEXTO, relief="flat").pack(fill="x", ipady=6)
        resultado = {"ok": False}

        def confirmar():
            resultado["ok"] = True
            win.destroy()

        tk.Button(frame, text="Confirmar", bg=VERDE_ESC, fg=BRANCO, relief="flat", command=confirmar).pack(anchor="e", pady=(12, 0))
        self.wait_window(win)
        if not resultado["ok"]:
            return None
        try:
            quantidade = int(qtd_var.get())
            custo = float(custo_var.get().replace(",", ".")) if custo_var.get().strip() else None
        except ValueError:
            messagebox.showerror("Dados invalidos", "Informe uma quantidade valida.")
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
        dados = self._dialog_produto_quantidade("Ajuste por contagem")
        if not dados:
            return
        produto, quantidade, _custo, observacao = dados
        db.ajustar_estoque_por_contagem(produto["id"], quantidade, observacao=observacao)
        self.atualizar()

    def _perda(self):
        dados = self._dialog_produto_quantidade("Registrar perda")
        if not dados:
            return
        produto, quantidade, _custo, observacao = dados
        if not messagebox.askyesno("Confirmar perda", "Registrar esta saida como perda de estoque?"):
            return
        db.registrar_perda_estoque(produto["id"], quantidade, observacao=observacao)
        self.atualizar()

    def _alternar_ativo(self):
        produto = self._produto_selecionado()
        if not produto:
            return
        ativo = int(produto.get("ativo") or 0) == 1
        acao = "inativar" if ativo else "reativar"
        if not messagebox.askyesno("Confirmar", f"Deseja {acao} este produto?"):
            return
        if ativo:
            db.inativar_produto(produto["id"])
        else:
            db.reativar_produto(produto["id"])
        self.atualizar()

    def _abrir_movimentacoes(self):
        produto = self._produto_selecionado()
        if not produto:
            return
        win = tk.Toplevel(self)
        win.title("Movimentacoes do produto")
        win.configure(bg=FUNDO)
        win.geometry("860x420")
        win.transient(self)
        frame = tk.Frame(win, bg=FUNDO, padx=18, pady=16)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text=produto["nome"], bg=FUNDO, fg=TEXTO, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(frame, text=f"Codigo {produto['codigo']}", bg=FUNDO, fg=MUTED).pack(anchor="w", pady=(2, 10))

        colunas = ("data", "tipo", "qtd", "saldo", "origem", "ref", "resp", "obs")
        tree = ttk.Treeview(frame, columns=colunas, show="headings", height=14)
        titulos = {
            "data": "Data",
            "tipo": "Tipo",
            "qtd": "Qtd",
            "saldo": "Saldo",
            "origem": "Origem",
            "ref": "Referencia",
            "resp": "Responsavel",
            "obs": "Observacao",
        }
        for coluna in colunas:
            tree.heading(coluna, text=titulos[coluna])
            tree.column(coluna, width=100, anchor="center")
        tree.column("obs", width=220, anchor="w")
        tree.pack(fill="both", expand=True)
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

    def _recalcular_abc(self):
        config = db.configuracoes()
        with db.get_conn() as conn:
            total = calculos.classificar_abc(conn, config)
        self.atualizar()
        messagebox.showinfo("ABC recalculado", f"{total} produtos classificados.")

    def _exportar(self):
        pasta = filedialog.askdirectory(title="Salvar relatorio de estoque em...")
        if not pasta:
            return
        caminho = relatorio_estoque.gerar_posicao_estoque(self._produtos_filtrados(), pasta)
        messagebox.showinfo("Relatorio gerado", f"Arquivo salvo em:\n{caminho}")
