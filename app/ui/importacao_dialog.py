"""Dialog de conferencia e escolha do modo de importacao."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import tema as theme
from app.services.importacao_service import MODOS
from app.ui.components import Card, PageHeader, bind_escape_to_close, configure_styles
from tema import moeda


def _valor(valor) -> str:
    return "Nao informado" if valor is None else moeda(float(valor))


def confirmar_importacao(parent, previa: dict) -> str | None:
    dialog = tk.Toplevel(parent)
    dialog.title("Conferencia da importacao")
    dialog.geometry("760x680")
    dialog.minsize(680, 560)
    dialog.configure(bg=theme.FUNDO)
    dialog.transient(parent)
    dialog.grab_set()
    bind_escape_to_close(dialog)
    configure_styles(dialog)
    resultado = {"modo": None}

    PageHeader(dialog, "Conferência da importação", "Revise o mapeamento e os totais antes de gravar.").pack(fill="x", padx=18, pady=(16, 10))

    card = Card(dialog, padding=0)
    card.pack(fill="both", expand=True, padx=18)
    texto = tk.Text(card, bg=theme.BRANCO, fg=theme.TEXTO, relief="flat", padx=14, pady=12, wrap="word", borderwidth=0)
    texto.pack(fill="both", expand=True)
    diferenca = previa.get("diferenca_custo")
    linhas = [
        f"Colunas detectadas: {', '.join(previa['colunas_detectadas'])}",
        f"Colunas mapeadas: {previa['colunas_mapeadas']}",
        "",
        f"Produtos lidos: {previa['total_linhas']}",
        f"Insercoes previstas: {previa['produtos_inseridos_previstos']}",
        f"Atualizacoes previstas: {previa['produtos_atualizados_previstos']}",
        f"Ignorados previstos: {previa['produtos_ignorados_previstos']}",
        f"Divergencias contra o banco atual: {previa['produtos_com_divergencia_banco']}",
        f"Soma da coluna Disponivel: {previa['soma_estoque_disponivel']}",
        "",
        f"Custo Total da planilha: {_valor(previa.get('custo_total_planilha'))}",
        f"Valor a custo calculado: {_valor(previa.get('valor_custo_calculado'))}",
        f"Valor a venda calculado: {_valor(previa.get('valor_venda_calculado'))}",
        f"Diferenca de custo: {_valor(diferenca)}",
        f"Impacto das divergencias no banco atual: {_valor(previa.get('valor_divergencia_banco'))}",
        f"Produtos ativos fora da planilha: {previa['produtos_ativos_fora_da_planilha']}",
        f"Valor a custo fora da planilha: {_valor(previa.get('valor_produtos_fora_da_planilha'))}",
        "",
        f"Sem SKU: {previa['produtos_sem_sku']}",
        f"Sem nome: {previa['produtos_sem_nome']}",
        f"Sem preco: {previa['produtos_sem_preco']}",
        f"Sem custo: {previa['produtos_sem_custo']}",
        f"Estoque invalido: {previa['produtos_com_estoque_invalido']}",
        f"Duplicados: {previa['produtos_duplicados']}",
        "",
        f"Estoque mapeado: {'Sim' if previa['estoque_mapeado'] else 'Nao'} ({previa['coluna_estoque'] or '-'})",
        f"Custo medio mapeado: {'Sim' if previa['custo_mapeado'] else 'Nao'} ({previa['coluna_custo'] or '-'})",
        f"Custo total usado apenas para conferencia: {previa['coluna_custo_total'] or '-'}",
    ]
    texto.insert("1.0", "\n".join(linhas))
    texto.configure(state="disabled")

    rodape = tk.Frame(dialog, bg=theme.FUNDO, padx=18, pady=14)
    rodape.pack(fill="x")
    tk.Label(rodape, text="Modo de estoque", bg=theme.FUNDO, fg=theme.TEXTO, font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w")
    modo_rotulo = tk.StringVar(value=next(iter(MODOS)))
    ttk.Combobox(rodape, textvariable=modo_rotulo, values=list(MODOS), state="readonly", width=32).grid(row=0, column=1, sticky="w", padx=8)
    rodape.grid_columnconfigure(2, weight=1)

    def confirmar():
        if previa.get("alerta_diferenca_custo") and not messagebox.askyesno(
            "Diferenca de custo",
            "A diferenca entre o Custo Total da planilha e o valor a custo calculado "
            "e maior que R$ 0,05.\n\nDeseja importar mesmo assim?",
            parent=dialog,
        ):
            return
        resultado["modo"] = MODOS[modo_rotulo.get()]
        dialog.destroy()

    tk.Button(rodape, text="Cancelar", bg=theme.BRANCO, fg=theme.MUTED, relief="flat", command=dialog.destroy, padx=14, pady=8).grid(row=0, column=4, sticky="e", padx=(8, 0))
    tk.Button(rodape, text="Importar", bg=theme.VERDE_ESC, fg=theme.BRANCO, relief="flat", command=confirmar, padx=16, pady=8).grid(row=0, column=5, sticky="e")
    if previa.get("alerta_diferenca_custo"):
        tk.Label(rodape, text="Diferença financeira acima de R$ 0,05", bg=theme.FUNDO, fg=theme.VERMELHO).grid(row=1, column=0, columnspan=6, sticky="w", pady=(8, 0))

    parent.wait_window(dialog)
    return resultado["modo"]
