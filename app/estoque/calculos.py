"""
Calculos do modulo de estoque.

Este arquivo nao cria interface. Ele transforma dados do banco em indicadores
para o painel, dashboard e relatorios.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP


STATUS_ORDEM = {"CRITICO": 0, "ALERTA": 1, "MORTO": 2, "OK": 3, "INATIVO": 4}


@dataclass(frozen=True)
class FiltrosEstoque:
    termo: str = ""
    status: str = "Todos"
    curva_abc: str = "Todos"
    categoria: str = "Todas"
    fornecedor: str = "Todos"
    ativos: str = "Todos"
    sem_custo: bool = False
    sem_minimo: bool = False
    sem_movimento: bool = False


def filtrar_produtos(
    produtos: list[dict],
    filtros: FiltrosEstoque,
) -> list[dict]:
    """Aplica critérios de estoque sem depender do estado da interface."""
    termo = filtros.termo.strip().lower()

    def corresponde(produto: dict) -> bool:
        campos_busca = (
            produto.get("nome"),
            produto.get("codigo"),
            produto.get("cod_barras"),
        )
        if termo and not any(
            termo in str(valor or "").lower()
            for valor in campos_busca
        ):
            return False
        if filtros.status != "Todos" and produto.get("status") != filtros.status:
            return False
        if (
            filtros.curva_abc != "Todos"
            and (produto.get("curva_abc") or "") != filtros.curva_abc
        ):
            return False
        if (
            filtros.categoria != "Todas"
            and (produto.get("categoria") or "") != filtros.categoria
        ):
            return False
        if (
            filtros.fornecedor != "Todos"
            and (produto.get("fornecedor") or "") != filtros.fornecedor
        ):
            return False

        ativo = int(produto.get("ativo") or 0)
        if filtros.ativos == "Ativos" and ativo != 1:
            return False
        if filtros.ativos == "Inativos" and ativo != 0:
            return False
        if filtros.sem_custo and produto.get("custo_unitario") is not None:
            return False
        if filtros.sem_minimo and int(produto.get("estoque_minimo") or 0) > 0:
            return False
        if filtros.sem_movimento and produto.get("status") != "MORTO":
            return False
        return True

    return [produto for produto in produtos if corresponde(produto)]


def _config_float(config: dict[str, str], chave: str, padrao: float) -> float:
    try:
        return float(config.get(chave, padrao))
    except (TypeError, ValueError):
        return padrao


def _config_int(config: dict[str, str], chave: str, padrao: int) -> int:
    try:
        return int(float(config.get(chave, padrao)))
    except (TypeError, ValueError):
        return padrao


def demanda_media_diaria(
    conn: sqlite3.Connection,
    produto_id: int,
    janela_dias: int = 30,
) -> float:
    data_limite = (datetime.now() - timedelta(days=janela_dias)).strftime("%Y-%m-%d")
    row = conn.execute(
        """
        SELECT COALESCE(SUM(i.quantidade), 0) AS total
        FROM vendas_itens i
        JOIN vendas_cabecalho h ON h.id = i.venda_id
        WHERE i.produto_id = ?
          AND h.status <> 'Cancelada'
          AND h.data >= ?
        """,
        (produto_id, data_limite),
    ).fetchone()
    total = float(row["total"] or 0)
    return total / max(janela_dias, 1)


def ultimo_movimento_iso(conn: sqlite3.Connection, produto_id: int) -> str:
    row = conn.execute(
        """
        SELECT MAX(data_iso) AS data_iso
        FROM movimentacoes_estoque
        WHERE produto_id = ?
        """,
        (produto_id,),
    ).fetchone()
    return row["data_iso"] or ""


def valor_estoque(produto: dict) -> float:
    """Compatibilidade: valor do estoque sempre significa valor a custo."""
    return valor_a_custo(produto)


def _valor_total_em_reais(
    produto: dict,
    campo_centavos: str,
    campo_legado: str,
) -> float:
    estoque = int(produto.get("estoque") or 0)
    centavos = produto.get(campo_centavos)
    if centavos is not None:
        total = Decimal(estoque * int(centavos)) / Decimal(100)
    else:
        unitario = Decimal(str(produto.get(campo_legado) or 0))
        total = Decimal(estoque) * unitario
    return float(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def valor_a_custo(produto: dict) -> float:
    return _valor_total_em_reais(
        produto,
        "custo_unitario_centavos",
        "custo_unitario",
    )


def valor_a_venda(produto: dict) -> float:
    return _valor_total_em_reais(produto, "preco_centavos", "preco")


def sugerir_estoque_minimo(demanda: float, fator_seguranca: float = 1.5) -> int:
    return int(math.ceil(demanda * 7 * fator_seguranca))


def calcular_ponto_pedido(produto: dict, demanda: float) -> int:
    lead_time = int(produto.get("lead_time_dias") or 7)
    minimo = int(produto.get("estoque_minimo") or 0)
    return int(math.ceil((demanda * lead_time) + minimo))


def status_estoque(
    produto: dict,
    demanda: float,
    ultimo_movimento: str,
    estoque_morto_dias: int = 90,
) -> str:
    if int(produto.get("ativo", 1) or 0) == 0:
        return "INATIVO"

    estoque = int(produto.get("estoque") or 0)
    minimo = int(produto.get("estoque_minimo") or 0)
    ponto = int(produto.get("ponto_pedido") or 0)

    if estoque <= minimo:
        return "CRITICO"
    if ponto and estoque <= ponto:
        return "ALERTA"

    if demanda == 0 and ultimo_movimento:
        try:
            ultima_data = datetime.strptime(ultimo_movimento, "%Y-%m-%d")
            if (datetime.now() - ultima_data).days >= estoque_morto_dias:
                return "MORTO"
        except ValueError:
            pass

    return "OK"


def indicadores_produtos(
    conn: sqlite3.Connection,
    produtos: list,
    config: dict[str, str],
) -> list[dict]:
    janela = _config_int(config, "demanda_janela_dias", 30)
    fator = _config_float(config, "fator_seguranca", 1.5)
    morto_dias = _config_int(config, "estoque_morto_dias", 90)
    indicadores = []

    for row in produtos:
        produto = dict(row)
        demanda = demanda_media_diaria(conn, produto["id"], janela)
        ultimo = ultimo_movimento_iso(conn, produto["id"])
        minimo = int(produto.get("estoque_minimo") or 0)
        ponto = int(produto.get("ponto_pedido") or 0)
        minimo_sugerido = sugerir_estoque_minimo(demanda, fator)
        ponto_sugerido = calcular_ponto_pedido(produto, demanda)

        if minimo <= 0:
            produto["estoque_minimo"] = minimo_sugerido
        if ponto <= 0:
            produto["ponto_pedido"] = ponto_sugerido

        produto["demanda_media"] = demanda
        produto["ultimo_movimento"] = ultimo
        produto["valor_estoque"] = valor_estoque(produto)
        produto["valor_a_custo"] = valor_a_custo(produto)
        produto["valor_a_venda"] = valor_a_venda(produto)
        produto["status"] = status_estoque(produto, demanda, ultimo, morto_dias)
        produto["cobertura_dias"] = (
            int(produto.get("estoque") or 0) / demanda if demanda > 0 else None
        )
        indicadores.append(produto)

    indicadores.sort(key=lambda p: (STATUS_ORDEM.get(p["status"], 9), p["nome"]))
    return indicadores


def classificar_abc(conn: sqlite3.Connection, config: dict[str, str]) -> int:
    limite_a = _config_float(config, "abc_limite_a", 0.80)
    limite_b = _config_float(config, "abc_limite_b", 0.95)
    produtos = [dict(row) for row in conn.execute("SELECT * FROM produtos WHERE ativo = 1").fetchall()]

    if config.get("abc_metodo") == "receita_vendas":
        receita_por_produto = {
            int(row["produto_id"]): int(row["receita_centavos"] or 0)
            for row in conn.execute(
                """
                SELECT i.produto_id, SUM(i.subtotal_centavos) AS receita_centavos
                FROM vendas_itens i
                JOIN vendas_cabecalho h ON h.id = i.venda_id
                WHERE h.status <> 'Cancelada'
                GROUP BY i.produto_id
                """
            ).fetchall()
        }
        metrica = lambda produto: receita_por_produto.get(int(produto["id"]), 0)
    else:
        metrica = valor_estoque

    produtos.sort(key=metrica, reverse=True)
    total = sum(max(metrica(produto), 0) for produto in produtos)

    acumulado = 0.0
    for produto in produtos:
        valor = max(metrica(produto), 0)
        percentual_anterior = (acumulado / total) if total else 1
        if percentual_anterior < limite_a:
            curva = "A"
        elif percentual_anterior < limite_b:
            curva = "B"
        else:
            curva = "C"
        acumulado += valor
        conn.execute("UPDATE produtos SET curva_abc = ? WHERE id = ?", (curva, produto["id"]))
    return len(produtos)


def resumo_estoque(indicadores: list[dict]) -> dict:
    resumo = {
        "ativos": 0,
        "criticos": 0,
        "alertas": 0,
        "mortos": 0,
        "valor_total": 0.0,
        "valor_total_custo": 0.0,
        "valor_total_venda": 0.0,
    }
    for produto in indicadores:
        if int(produto.get("ativo", 1) or 0) == 0:
            continue
        resumo["ativos"] += 1
        resumo["valor_total"] += float(produto.get("valor_estoque") or 0)
        resumo["valor_total_custo"] += float(produto.get("valor_a_custo") or 0)
        resumo["valor_total_venda"] += float(produto.get("valor_a_venda") or 0)
        if produto["status"] == "CRITICO":
            resumo["criticos"] += 1
        elif produto["status"] == "ALERTA":
            resumo["alertas"] += 1
        elif produto["status"] == "MORTO":
            resumo["mortos"] += 1
    return resumo
