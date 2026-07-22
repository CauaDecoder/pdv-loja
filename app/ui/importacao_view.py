"""View e fluxo guiado em etapas para a Importação de Produtos (Issue #14)."""

from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from app.services import importacao_service
from app.ui.components import Card, PageHeader, SectionHeader, StatusBadge, action_button
from tema import FONTES, TEMA_ATUAL, moeda


class ImportacaoGuidedView(tk.Frame):
    """Componente visual que gerencia a importação guiada de produtos em 4 etapas."""

    ETAPAS = [
        "1. Selecionar arquivo",
        "2. Escolher modo",
        "3. Conferência & Impactos",
        "4. Gravação & Confirmação",
    ]

    def __init__(self, parent: tk.Widget, on_import_complete: Callable | None = None):
        super().__init__(parent, bg=TEMA_ATUAL["fundo"], padx=18, pady=16)
        self._on_import_complete = on_import_complete

        self._etapa_atual = 1  # 1, 2, 3, 4
        self._caminho_arquivo: str | None = None
        self._modo_rotulo: str = list(importacao_service.MODOS.keys())[0]
        self._previa_dados: dict | None = None
        self._resultado_importacao: dict | None = None

        self._build_ui()

    def _build_ui(self):
        """Constrói o layout principal do fluxo guiado."""
        for w in self.winfo_children():
            w.destroy()

        PageHeader(
            self,
            "Importação de produtos",
            "Fluxo guiado em etapas para importar planilhas e conferir impactos no estoque.",
        ).pack(fill="x", pady=(0, 14))

        # --- STEPPER BAR ---
        self._build_stepper()

        # --- CONTEÚDO DA ETAPA ATUAL ---
        self._container_etapa = tk.Frame(self, bg=TEMA_ATUAL["fundo"])
        self._container_etapa.pack(fill="both", expand=True, pady=(0, 14))

        if self._resultado_importacao:
            self._render_resultado_sucesso()
        elif self._etapa_atual == 1:
            self._render_etapa_1_arquivo()
        elif self._etapa_atual == 2:
            self._render_etapa_2_modo()
        elif self._etapa_atual == 3:
            self._render_etapa_3_conferencia()
        elif self._etapa_atual == 4:
            self._render_etapa_4_confirmacao()

    def _build_stepper(self):
        """Renderiza a barra de progresso visual com os 4 passos."""
        card_stepper = Card(self, padding=12)
        card_stepper.pack(fill="x", pady=(0, 16))

        bar = tk.Frame(card_stepper, bg=TEMA_ATUAL["surface"])
        bar.pack(fill="x")

        for idx, rotulo in enumerate(self.ETAPAS, start=1):
            bar.columnconfigure(idx - 1, weight=1, uniform="stepper")

            sub_frame = tk.Frame(bar, bg=TEMA_ATUAL["surface"])
            sub_frame.grid(row=0, column=idx - 1, sticky="ew", padx=4)

            ativo = (self._etapa_atual == idx and not self._resultado_importacao)
            concluido = (self._etapa_atual > idx or self._resultado_importacao is not None)

            bg_step = TEMA_ATUAL["primary"] if ativo else (TEMA_ATUAL["primary_soft"] if concluido else TEMA_ATUAL["surface_2"])
            fg_step = "#FFFFFF" if ativo else (TEMA_ATUAL["primary"] if concluido else TEMA_ATUAL["texto_suave"])
            prefixo = "✓ " if concluido and not ativo else f"{idx}. "

            pill = tk.Label(
                sub_frame,
                text=f"{prefixo}{rotulo.split('. ')[1]}",
                bg=bg_step,
                fg=fg_step,
                font=FONTES["corpo_bold"] if ativo else FONTES["corpo"],
                padx=12,
                pady=6,
                anchor="center",
            )
            pill.pack(fill="x")

    # --- RENDERIZADORES DAS ETAPAS ---

    def _render_etapa_1_arquivo(self):
        """Etapa 1: Selecionar arquivo CSV/Excel."""
        card = Card(self._container_etapa, padding=24)
        card.pack(fill="both", expand=True)

        SectionHeader(
            card,
            "Etapa 1: Seleção da Planilha de Produtos",
            "Selecione um arquivo CSV (exportado do Conta Azul) ou planilha Excel (.xlsx) contendo os produtos.",
        ).pack(anchor="w", fill="x", pady=(0, 18))

        upload_box = tk.Frame(card, bg=TEMA_ATUAL["surface_2"], padx=24, pady=24, highlightthickness=1, highlightbackground=TEMA_ATUAL["border_soft"])
        upload_box.pack(fill="x", pady=(0, 20))

        if not self._caminho_arquivo:
            tk.Label(
                upload_box,
                text="📂 Nenhum arquivo selecionado",
                bg=TEMA_ATUAL["surface_2"],
                fg=TEMA_ATUAL["texto"],
                font=FONTES["subtitulo"],
            ).pack(anchor="center")

            tk.Label(
                upload_box,
                text="Formatos aceitos: CSV (*.csv) ou Excel (*.xlsx, *.xlsm)",
                bg=TEMA_ATUAL["surface_2"],
                fg=TEMA_ATUAL["texto_suave"],
                font=FONTES["corpo"],
            ).pack(anchor="center", pady=(4, 14))

            action_button(
                upload_box,
                text="📁 Procurar Planilha...",
                command=self._selecionar_arquivo,
                variant="primary",
                padx=20,
                pady=10,
            ).pack(anchor="center")
        else:
            p = Path(self._caminho_arquivo)
            tamanho_kb = os.path.getsize(self._caminho_arquivo) / 1024 if os.path.exists(self._caminho_arquivo) else 0

            hdr_file = tk.Frame(upload_box, bg=TEMA_ATUAL["surface_2"])
            hdr_file.pack(fill="x")

            tk.Label(
                hdr_file,
                text=f"📄 {p.name}",
                bg=TEMA_ATUAL["surface_2"],
                fg=TEMA_ATUAL["primary"],
                font=FONTES["secao"],
            ).pack(side="left")

            StatusBadge(hdr_file, "Arquivo Selecionado", bg=TEMA_ATUAL["primary_soft"], fg=TEMA_ATUAL["primary"]).pack(side="left", padx=(10, 0))

            tk.Label(
                upload_box,
                text=f"Caminho completo: {p}\nTamanho: {tamanho_kb:.1f} KB",
                bg=TEMA_ATUAL["surface_2"],
                fg=TEMA_ATUAL["texto_suave"],
                font=FONTES["corpo"],
                justify="left",
            ).pack(anchor="w", pady=(8, 12))

            action_button(
                upload_box,
                text="🔄 Trocar Arquivo",
                command=self._selecionar_arquivo,
                variant="secondary",
            ).pack(anchor="w")

        # Botões de Navegação
        bar_nav = tk.Frame(card, bg=TEMA_ATUAL["surface"])
        bar_nav.pack(fill="x", side="bottom", pady=(18, 0))

        action_button(
            bar_nav,
            text="Escolher Modo de Importação ➔",
            command=self._avancar_para_etapa_2,
            variant="primary" if self._caminho_arquivo else "secondary",
            state="normal" if self._caminho_arquivo else "disabled",
        ).pack(side="right")

    def _render_etapa_2_modo(self):
        """Etapa 2: Escolher modo de importação de estoque."""
        card = Card(self._container_etapa, padding=24)
        card.pack(fill="both", expand=True)

        SectionHeader(
            card,
            "Etapa 2: Escolha do Modo de Importação",
            "Defina como o sistema deve tratar os saldos de estoque e cadastros existentes.",
        ).pack(anchor="w", fill="x", pady=(0, 18))

        detalhes_modos = {
            "Atualizar estoque pelo Disponivel": (
                "Atualizar saldos pelo 'Disponível' (Recomendado)",
                "Atualiza os preços, dados cadastrais e ajusta as quantidades de estoque com base na coluna Disponível da planilha. Registra movimentações de ajuste.",
            ),
            "Preservar estoque atual": (
                "Preservar estoque atual",
                "Atualiza apenas os dados cadastrais (nome, código, preço de venda) sem alterar as quantidades de estoque atuais do caixa.",
            ),
            "Inventario inicial": (
                "Inventário Inicial",
                "Substitui e define a quantidade de estoque inicial diretamente a partir dos valores lidos da planilha.",
            ),
        }

        for rotulo_modo, (titulo, desc) in detalhes_modos.items():
            selecionado = (self._modo_rotulo == rotulo_modo)
            bg_card = TEMA_ATUAL["primary_soft"] if selecionado else TEMA_ATUAL["surface_2"]

            box_modo = tk.Frame(card, bg=bg_card, padx=16, pady=12, highlightthickness=2 if selecionado else 1, highlightbackground=TEMA_ATUAL["primary"] if selecionado else TEMA_ATUAL["border_soft"])
            box_modo.pack(fill="x", pady=(0, 12))

            rb = tk.Radiobutton(
                box_modo,
                text=titulo,
                value=rotulo_modo,
                variable=self._get_var_modo(),
                command=lambda m=rotulo_modo: self._selecionar_modo(m),
                bg=bg_card,
                fg=TEMA_ATUAL["texto"],
                font=FONTES["subtitulo"],
                activebackground=bg_card,
                activeforeground=TEMA_ATUAL["texto"],
                cursor="hand2",
            )
            rb.pack(anchor="w")

            tk.Label(
                box_modo,
                text=desc,
                bg=bg_card,
                fg=TEMA_ATUAL["texto_suave"],
                font=FONTES["corpo"],
                wraplength=700,
                justify="left",
            ).pack(anchor="w", padx=(24, 0), pady=(4, 0))

        bar_nav = tk.Frame(card, bg=TEMA_ATUAL["surface"])
        bar_nav.pack(fill="x", side="bottom", pady=(18, 0))

        action_button(
            bar_nav,
            text="⬅ Voltar (Arquivo)",
            command=lambda: self._ir_para_etapa(1),
            variant="secondary",
        ).pack(side="left")

        action_button(
            bar_nav,
            text="Calcular Conferência & Avançar ➔",
            command=self._avancar_para_etapa_3,
            variant="primary",
        ).pack(side="right")

    def _render_etapa_3_conferencia(self):
        """Etapa 3: Revisar conferência de impactos e riscos."""
        card = Card(self._container_etapa, padding=20)
        card.pack(fill="both", expand=True)

        SectionHeader(
            card,
            "Etapa 3: Conferência de Impactos e Riscos",
            "Revise o resumo do que foi lido da planilha e verifique inconsistências antes de autorizar a gravação.",
        ).pack(anchor="w", fill="x", pady=(0, 14))

        previa = self._previa_dados or {}

        # 4 Cards de Métricas no Topo
        grid_metrics = tk.Frame(card, bg=TEMA_ATUAL["surface"])
        grid_metrics.pack(fill="x", pady=(0, 14))
        for i in range(4):
            grid_metrics.columnconfigure(i, weight=1, uniform="m")

        metricas = [
            ("Produtos Novos", str(previa.get("produtos_inseridos_previstos", 0)), "Inserções", TEMA_ATUAL["primary_soft"], TEMA_ATUAL["primary"]),
            ("Atualizações", str(previa.get("produtos_atualizados_previstos", 0)), "Cadastros", TEMA_ATUAL["info_soft"], TEMA_ATUAL["info"]),
            ("Ignorados", str(previa.get("produtos_ignorados_previstos", 0)), "Sem alteração", TEMA_ATUAL["neutral_soft"], TEMA_ATUAL["text_muted"]),
            ("Divergências Banco", str(previa.get("produtos_com_divergencia_banco", 0)), "Diferenças saldo", TEMA_ATUAL["warning_soft"], TEMA_ATUAL["warning"]),
        ]

        for col_idx, (label, val, sub, bg_c, fg_c) in enumerate(metricas):
            c_box = tk.Frame(grid_metrics, bg=bg_c, padx=12, pady=10)
            c_box.grid(row=0, column=col_idx, sticky="nsew", padx=4)
            tk.Label(c_box, text=label, bg=bg_c, fg=fg_c, font=FONTES["label_sm"]).pack(anchor="w")
            tk.Label(c_box, text=val, bg=bg_c, fg=fg_c, font=FONTES["numero_card"]).pack(anchor="w", pady=(2, 0))
            tk.Label(c_box, text=sub, bg=bg_c, fg=fg_c, font=FONTES["corpo"]).pack(anchor="w")

        # Alertas de Risco Financeiro e Inconsistências
        diferenca = previa.get("diferenca_custo")
        tem_alerta_custo = previa.get("alerta_diferenca_custo", False)

        if tem_alerta_custo:
            alert_box = tk.Frame(card, bg=TEMA_ATUAL["danger_soft"], padx=14, pady=10)
            alert_box.pack(fill="x", pady=(0, 12))
            tk.Label(
                alert_box,
                text="⚠️ ALERTA FINANCEIRO: Diferença de Custo Total da Planilha",
                bg=TEMA_ATUAL["danger_soft"],
                fg=TEMA_ATUAL["danger"],
                font=FONTES["corpo_bold"],
            ).pack(anchor="w")
            tk.Label(
                alert_box,
                text=f"A diferença entre o custo total da planilha e o calculado excede R$ 0,05 ({_fmt_moeda(diferenca)}). Verifique os valores antes de prosseguir.",
                bg=TEMA_ATUAL["danger_soft"],
                fg=TEMA_ATUAL["texto"],
                font=FONTES["corpo"],
            ).pack(anchor="w", pady=(2, 0))

        # Quadro de Detalhes da Planilha
        box_info = tk.Frame(card, bg=TEMA_ATUAL["surface_2"], padx=14, pady=10)
        box_info.pack(fill="x", pady=(0, 14))

        custo_calculado = _fmt_moeda(previa.get("valor_custo_calculado"))
        venda_calculada = _fmt_moeda(previa.get("valor_venda_calculado"))

        tk.Label(
            box_info,
            text=f"• Total de linhas lidas: {previa.get('total_linhas', 0)}  |  Estoque Mapeado: {'Sim' if previa.get('estoque_mapeado') else 'Não'}\n"
                 f"• Valor Total a Custo: {custo_calculado}  |  Valor Total a Venda: {venda_calculada}\n"
                 f"• Duplicados: {previa.get('produtos_duplicados', 0)}  |  Sem SKU: {previa.get('produtos_sem_sku', 0)}  |  Sem Preço: {previa.get('produtos_sem_preco', 0)}",
            bg=TEMA_ATUAL["surface_2"],
            fg=TEMA_ATUAL["texto"],
            font=FONTES["corpo"],
            justify="left",
        ).pack(anchor="w")

        bar_nav = tk.Frame(card, bg=TEMA_ATUAL["surface"])
        bar_nav.pack(fill="x", side="bottom", pady=(10, 0))

        action_button(
            bar_nav,
            text="⬅ Voltar (Modo)",
            command=lambda: self._ir_para_etapa(2),
            variant="secondary",
        ).pack(side="left")

        action_button(
            bar_nav,
            text="Avançar para Confirmação ➔",
            command=lambda: self._ir_para_etapa(4),
            variant="primary",
        ).pack(side="right")

    def _render_etapa_4_confirmacao(self):
        """Etapa 4: Confirmar gravação no banco de dados."""
        card = Card(self._container_etapa, padding=24)
        card.pack(fill="both", expand=True)

        SectionHeader(
            card,
            "Etapa 4: Confirmação e Gravação no Banco de Dados",
            "Revise as informações finais e confirme a execução da importação.",
        ).pack(anchor="w", fill="x", pady=(0, 18))

        previa = self._previa_dados or {}
        p_name = Path(self._caminho_arquivo).name if self._caminho_arquivo else ""

        box_resumo = tk.Frame(card, bg=TEMA_ATUAL["surface_2"], padx=18, pady=16)
        box_resumo.pack(fill="x", pady=(0, 18))

        tk.Label(
            box_resumo,
            text="Resumo da Operação que será Gravada:",
            bg=TEMA_ATUAL["surface_2"],
            fg=TEMA_ATUAL["texto"],
            font=FONTES["subtitulo"],
        ).pack(anchor="w", pady=(0, 8))

        tk.Label(
            box_resumo,
            text=f"• Arquivo: {p_name}\n"
                 f"• Modo selecionado: {self._modo_rotulo}\n"
                 f"• Novas inserções de produtos: {previa.get('produtos_inseridos_previstos', 0)}\n"
                 f"• Atualizações de produtos existentes: {previa.get('produtos_atualizados_previstos', 0)}\n"
                 f"• Total de linhas processadas: {previa.get('total_linhas', 0)}",
            bg=TEMA_ATUAL["surface_2"],
            fg=TEMA_ATUAL["texto"],
            font=FONTES["corpo_bold"],
            justify="left",
        ).pack(anchor="w")

        # Warning Card
        box_warn = tk.Frame(card, bg=TEMA_ATUAL["warning_soft"], padx=16, pady=12)
        box_warn.pack(fill="x", pady=(0, 18))

        tk.Label(
            box_warn,
            text="⚠️ Atenção: Ao clicar em 'Confirmar e Gravar', as alterações de cadastro e os ajustes de estoque serão efetivados imediatamente no banco de dados do sistema.",
            bg=TEMA_ATUAL["warning_soft"],
            fg=TEMA_ATUAL["warning"],
            font=FONTES["corpo_bold"],
            wraplength=700,
            justify="left",
        ).pack(anchor="w")

        bar_nav = tk.Frame(card, bg=TEMA_ATUAL["surface"])
        bar_nav.pack(fill="x", side="bottom", pady=(10, 0))

        action_button(
            bar_nav,
            text="⬅ Voltar (Conferência)",
            command=lambda: self._ir_para_etapa(3),
            variant="secondary",
        ).pack(side="left")

        action_button(
            bar_nav,
            text="💾 Confirmar e Gravar no Banco de Dados",
            command=self._executar_importacao,
            variant="primary",
            padx=18,
            pady=10,
        ).pack(side="right")

    def _render_resultado_sucesso(self):
        """Tela de resultado pós-gravação."""
        card = Card(self._container_etapa, padding=24)
        card.pack(fill="both", expand=True)

        res = self._resultado_importacao or {}

        SectionHeader(
            card,
            "Importação Concluída com Sucesso! 🎉",
            "Os produtos e saldos foram gravados no banco de dados local.",
        ).pack(anchor="w", fill="x", pady=(0, 18))

        box_res = tk.Frame(card, bg=TEMA_ATUAL["primary_soft"], padx=20, pady=18)
        box_res.pack(fill="x", pady=(0, 20))

        tk.Label(
            box_res,
            text=f"• Produtos inseridos: {res.get('inseridos', 0)}\n"
                 f"• Produtos atualizados: {res.get('atualizados', 0)}\n"
                 f"• Ajustes de estoque registrados: {res.get('ajustados', 0)}\n"
                 f"• Linhas ignoradas: {res.get('ignorados', 0)}\n"
                 f"• Coluna de estoque utilizada: {res.get('coluna_estoque') or 'Nenhuma (preservado)'}",
            bg=TEMA_ATUAL["primary_soft"],
            fg=TEMA_ATUAL["primary"],
            font=FONTES["subtitulo"],
            justify="left",
        ).pack(anchor="w")

        action_button(
            card,
            text="✨ Iniciar Nova Importação",
            command=self._resetar_fluxo,
            variant="primary",
        ).pack(anchor="w")

    # --- AÇÕES E CALLBACKS ---

    def _get_var_modo(self) -> tk.StringVar:
        if not hasattr(self, "_var_modo_str"):
            self._var_modo_str = tk.StringVar(value=self._modo_rotulo)
        return self._var_modo_str

    def _selecionar_modo(self, modo_rotulo: str):
        self._modo_rotulo = modo_rotulo
        self._get_var_modo().set(modo_rotulo)
        self._build_ui()

    def _selecionar_arquivo(self):
        arquivo = filedialog.askopenfilename(
            title="Selecionar planilha de produtos",
            filetypes=[
                ("Planilhas", "*.csv *.xlsx *.xlsm *.xltx *.xltm"),
                ("CSV (Conta Azul)", "*.csv"),
                ("Excel", "*.xlsx *.xlsm *.xltx *.xltm"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if arquivo:
            self._caminho_arquivo = arquivo
            self._previa_dados = None
            self._resultado_importacao = None
            self._build_ui()

    def _ir_para_etapa(self, etapa: int):
        self._etapa_atual = etapa
        self._build_ui()

    def _avancar_para_etapa_2(self):
        if self._caminho_arquivo:
            self._ir_para_etapa(2)

    def _avancar_para_etapa_3(self):
        if not self._caminho_arquivo:
            return
        try:
            self._previa_dados = importacao_service.previsualizar(self._caminho_arquivo)
            self._ir_para_etapa(3)
        except Exception as erro:
            messagebox.showerror("Erro ao analisar arquivo", f"Não foi possível ler a planilha selecionada.\n\n{erro}")

    def _executar_importacao(self):
        if not self._caminho_arquivo:
            return
        modo_backend = importacao_service.MODOS.get(self._modo_rotulo)
        try:
            resultado = importacao_service.importar(self._caminho_arquivo, modo_backend)
            self._resultado_importacao = resultado
            self._build_ui()
            if self._on_import_complete:
                self._on_import_complete()
        except Exception as erro:
            messagebox.showerror("Erro na importação", f"Ocorreu uma falha ao gravar os dados no banco.\n\n{erro}")

    def _resetar_fluxo(self):
        self._etapa_atual = 1
        self._caminho_arquivo = None
        self._previa_dados = None
        self._resultado_importacao = None
        self._build_ui()


def _fmt_moeda(val) -> str:
    if val is None:
        return "N/A"
    try:
        return moeda(float(val))
    except (ValueError, TypeError):
        return str(val)
