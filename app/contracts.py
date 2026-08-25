"""Contratos persistentes compartilhados pelo PDV."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP


SCHEMA_VERSION = 2
FORMAS_PAGAMENTO = frozenset({"Dinheiro", "Pix", "Debito", "Credito"})
STATUS_VENDA_ATIVA = "Ativa"
STATUS_VENDA_CORRIGIDA = "Corrigida"
STATUS_VENDA_CANCELADA = "Cancelada"
STATUS_VENDA = frozenset(
    {STATUS_VENDA_ATIVA, STATUS_VENDA_CORRIGIDA, STATUS_VENDA_CANCELADA}
)


@dataclass(frozen=True, slots=True)
class ItemVenda:
    produto_id: int | None
    codigo: str
    nome: str
    quantidade: int
    preco_unit_centavos: int
    custo_unitario_centavos: int | None = None


@dataclass(frozen=True, slots=True)
class ParcelaPagamento:
    forma: str
    valor_centavos: int
    destino_id: int | None = None
    detalhe: str = ""
    valor_recebido_centavos: int | None = None
    troco_centavos: int | None = None


@dataclass(frozen=True, slots=True)
class RascunhoVenda:
    periodo_id: int
    itens: tuple[ItemVenda, ...]
    pagamentos: tuple[ParcelaPagamento, ...]
    responsavel: str
    chave_idempotencia: str


@dataclass(frozen=True, slots=True)
class ResultadoVenda:
    periodo_id: int
    num_venda: int
    total_centavos: int
    alertas_estoque: tuple[dict, ...] = ()

    def to_dict(self) -> dict:
        resultado = asdict(self)
        resultado["alertas_estoque"] = list(self.alertas_estoque)
        return resultado


@dataclass(frozen=True, slots=True)
class PreviaImportacao:
    sha256: str
    produtos_duplicados: int
    codigos_barras_duplicados: int
    produtos_com_estoque_negativo: int
    pode_inventario_inicial: bool


@dataclass(frozen=True, slots=True)
class ResumoFechamento:
    periodo_id: int
    total_vendas_centavos: int
    total_pagamentos_centavos: int
    divergencia_centavos: int


@dataclass(frozen=True, slots=True)
class RelatorioReconciliacao:
    ok: bool
    schema_erros: tuple[str, ...]
    integrity_check: tuple[str, ...]
    foreign_keys: tuple[tuple, ...]
    pagamentos_divergentes: int | None
    estoque_divergente: int | None
    vendas_divergentes: int | None

    def to_dict(self) -> dict:
        return asdict(self)


class DatabaseContractError(ValueError):
    """Indica que um banco não atende ao contrato persistente atual."""


class DatabaseUpgradeRequired(DatabaseContractError):
    """Indica que o banco precisa de migração ou recriação explícita."""


class DatabaseValidationError(DatabaseContractError):
    """Indica falha de integridade estrutural ou lógica."""


def valor_para_centavos(valor: int | float | str | Decimal) -> int:
    """Converte valor monetário decimal para centavos com arredondamento comercial."""
    decimal = Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(decimal * 100)


_COLUNAS_OBRIGATORIAS = {
    "produtos": {"id", "codigo", "preco_centavos", "custo_unitario_centavos", "estoque"},
    "periodos_caixa": {"id", "aberto_em", "fechado_em"},
    "vendas_cabecalho": {"id", "uuid", "periodo_id", "num_venda", "status"},
    "vendas_itens": {
        "id",
        "venda_id",
        "produto_id",
        "quantidade",
        "preco_unit_centavos",
        "subtotal_centavos",
        "custo_unitario_centavos",
    },
    "pagamentos_venda": {
        "id",
        "venda_id",
        "destino_id",
        "valor_centavos",
    },
    "movimentacoes_estoque": {"id", "produto_id", "estoque_resultante"},
    "destinos_financeiros": {"id", "nome", "ativo"},
    "fechamentos_periodo": {
        "id",
        "periodo_id",
        "responsavel",
        "fechado_em",
        "snapshot_json",
    },
}


def _erros_schema(conn: sqlite3.Connection) -> list[str]:
    versao = int(conn.execute("PRAGMA user_version").fetchone()[0])
    erros = [] if versao == SCHEMA_VERSION else [f"user_version={versao}"]
    tabelas = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    for tabela, obrigatorias in _COLUNAS_OBRIGATORIAS.items():
        if tabela not in tabelas:
            erros.append(f"tabela ausente: {tabela}")
            continue
        colunas = {row[1] for row in conn.execute(f"PRAGMA table_info({tabela})")}
        faltantes = sorted(obrigatorias - colunas)
        if faltantes:
            erros.append(f"{tabela} sem colunas: {', '.join(faltantes)}")
    return erros


def reconciliar_integridade(conn: sqlite3.Connection) -> RelatorioReconciliacao:
    """Reconcilia integridade física, referencial e saldos canônicos."""
    erros_schema = _erros_schema(conn)
    integrity_check = [row[0] for row in conn.execute("PRAGMA integrity_check")]
    foreign_keys = [tuple(row) for row in conn.execute("PRAGMA foreign_key_check")]
    if erros_schema:
        return RelatorioReconciliacao(
            False,
            tuple(erros_schema),
            tuple(integrity_check),
            tuple(foreign_keys),
            None,
            None,
            None,
        )

    pagamentos_divergentes = conn.execute(
        """
        SELECT COUNT(*)
        FROM vendas_cabecalho h
        WHERE COALESCE((SELECT SUM(p.valor_centavos) FROM pagamentos_venda p
                        WHERE p.venda_id = h.id), 0)
              <> COALESCE((SELECT SUM(i.subtotal_centavos) FROM vendas_itens i
                           WHERE i.venda_id = h.id), 0)
        """
    ).fetchone()[0]
    estoque_divergente = conn.execute(
        """
        WITH cadeia AS (
            SELECT
                m.produto_id,
                m.quantidade,
                m.estoque_resultante,
                LAG(m.estoque_resultante, 1, 0) OVER (
                    PARTITION BY m.produto_id ORDER BY m.id
                ) AS estoque_anterior
            FROM movimentacoes_estoque m
        )
        SELECT COUNT(*)
        FROM produtos p
        WHERE (
              NOT EXISTS (
                  SELECT 1 FROM movimentacoes_estoque m WHERE m.produto_id = p.id
              )
              AND p.estoque <> 0
          )
          OR (
              EXISTS (
                  SELECT 1 FROM movimentacoes_estoque m WHERE m.produto_id = p.id
              )
              AND (
              p.estoque <> (
                  SELECT m.estoque_resultante
                  FROM movimentacoes_estoque m
                  WHERE m.produto_id = p.id
                  ORDER BY m.id DESC LIMIT 1
              )
              OR EXISTS (
                  SELECT 1
                  FROM cadeia c
                  WHERE c.produto_id = p.id
                    AND c.estoque_resultante
                        <> c.estoque_anterior + c.quantidade
              )
              )
          )
        """
    ).fetchone()[0]
    vendas_divergentes = conn.execute(
        """
        SELECT COUNT(*)
        FROM vendas_cabecalho h
        WHERE NOT EXISTS (SELECT 1 FROM vendas_itens i WHERE i.venda_id = h.id)
           OR EXISTS (
               SELECT 1 FROM vendas_itens i
               WHERE i.venda_id = h.id
                 AND i.subtotal_centavos <> i.quantidade * i.preco_unit_centavos
           )
        """
    ).fetchone()[0]
    ok = (
        integrity_check == ["ok"]
        and not foreign_keys
        and pagamentos_divergentes == 0
        and estoque_divergente == 0
        and vendas_divergentes == 0
    )
    return RelatorioReconciliacao(
        ok,
        (),
        tuple(integrity_check),
        tuple(foreign_keys),
        pagamentos_divergentes,
        estoque_divergente,
        vendas_divergentes,
    )


def validar_contrato_banco(conn: sqlite3.Connection) -> RelatorioReconciliacao:
    """Valida schema v2 e reconciliação completa, levantando erro se inválido."""
    resultado = reconciliar_integridade(conn)
    if resultado.schema_erros:
        raise DatabaseValidationError(
            "Banco não atende ao schema v2: " + "; ".join(resultado.schema_erros)
        )
    if resultado.integrity_check != ("ok",):
        raise DatabaseValidationError("Banco falhou no integrity_check.")
    if resultado.foreign_keys:
        raise DatabaseValidationError("Banco possui violações de chave estrangeira.")
    if not resultado.ok:
        raise DatabaseValidationError("Banco possui divergência de reconciliação.")
    return resultado
