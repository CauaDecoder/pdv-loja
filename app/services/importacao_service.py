"""Fachada de importacao para manter regras fora da interface."""

from __future__ import annotations

import database as db


MODOS = {
    "Atualizar estoque pelo Disponivel": db.MODO_ESTOQUE_ATUALIZAR,
    "Preservar estoque atual": db.MODO_ESTOQUE_PRESERVAR,
    "Inventario inicial": db.MODO_ESTOQUE_INVENTARIO,
}


def previsualizar(caminho: str) -> dict:
    return db.previsualizar_importacao(caminho)


def importar(caminho: str, modo_estoque: str) -> dict:
    return db.importar_csv(caminho, modo_estoque=modo_estoque)
