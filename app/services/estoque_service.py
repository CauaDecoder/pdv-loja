"""Fachada das operacoes auditaveis de estoque."""

from app.runtime import database


def _operador_obrigatorio(responsavel: str) -> str:
    operador = (responsavel or "").strip()
    if not operador:
        raise ValueError("Operador responsavel pela movimentacao e obrigatorio.")
    return operador


def registrar_entrada_estoque(
    produto_id: int,
    quantidade: int,
    custo_unitario: float | None = None,
    data: str | None = None,
    referencia: str = "",
    observacao: str = "",
    responsavel: str = "",
) -> int:
    return database.registrar_entrada_estoque(
        produto_id,
        quantidade,
        custo_unitario=custo_unitario,
        data=data,
        referencia=referencia,
        observacao=observacao,
        responsavel=_operador_obrigatorio(responsavel),
    )


def registrar_movimentacao_estoque(
    produto_id: int,
    tipo: str,
    quantidade: int,
    observacao: str = "",
    referencia: str = "",
    responsavel: str = "",
    origem: str = "MANUAL",
) -> int:
    return database.registrar_movimentacao_estoque(
        produto_id,
        tipo,
        quantidade,
        observacao=observacao,
        referencia=referencia,
        responsavel=_operador_obrigatorio(responsavel),
        origem=origem,
    )


def ajustar_estoque_por_contagem(
    produto_id: int,
    quantidade_contada: int,
    observacao: str = "",
    responsavel: str = "",
) -> int:
    return database.ajustar_estoque_por_contagem(
        produto_id,
        quantidade_contada,
        observacao=observacao,
        responsavel=_operador_obrigatorio(responsavel),
    )


def registrar_perda_estoque(
    produto_id: int,
    quantidade: int,
    observacao: str = "",
    responsavel: str = "",
) -> int:
    return database.registrar_perda_estoque(
        produto_id,
        quantidade,
        observacao=observacao,
        responsavel=_operador_obrigatorio(responsavel),
    )


def reconciliar_integridade_banco() -> dict:
    return database.reconciliar_integridade_banco()

__all__ = [
    "ajustar_estoque_por_contagem",
    "reconciliar_integridade_banco",
    "registrar_entrada_estoque",
    "registrar_movimentacao_estoque",
    "registrar_perda_estoque",
]
