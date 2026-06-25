"""Fachada incremental para operacoes de estoque."""

from database import (
    ajustar_estoque_por_contagem,
    registrar_entrada_estoque,
    registrar_movimentacao_estoque,
    registrar_perda_estoque,
)

__all__ = [
    "ajustar_estoque_por_contagem",
    "registrar_entrada_estoque",
    "registrar_movimentacao_estoque",
    "registrar_perda_estoque",
]
