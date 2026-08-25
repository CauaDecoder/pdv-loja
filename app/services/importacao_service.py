"""Fachada de importacao para manter regras fora da interface."""

from __future__ import annotations

from app import database as local_db
from app.runtime import execute_import, preview_import


MODOS = {
    "Atualizar estoque pelo Disponivel": local_db.MODO_ESTOQUE_ATUALIZAR,
    "Preservar estoque atual": local_db.MODO_ESTOQUE_PRESERVAR,
    "Inventario inicial": local_db.MODO_ESTOQUE_INVENTARIO,
}


def previsualizar(caminho: str) -> dict:
    return preview_import(caminho)


def importar(
    caminho: str,
    modo_estoque: str,
    *,
    responsavel: str,
    lote_id: str,
    hash_arquivo: str,
) -> dict:
    operador = (responsavel or "").strip()
    if not operador:
        raise ValueError("Operador responsavel pela importacao e obrigatorio.")
    return execute_import(
        caminho,
        modo_estoque,
        responsavel=operador,
        lote_id=lote_id,
        hash_arquivo=hash_arquivo,
    )
