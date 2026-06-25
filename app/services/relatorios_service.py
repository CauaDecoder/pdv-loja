"""Fachada incremental para geracao de relatorios."""

from estoque.relatorio_estoque import gerar_posicao_estoque
from relatorio import gerar_relatorio

__all__ = ["gerar_posicao_estoque", "gerar_relatorio"]
