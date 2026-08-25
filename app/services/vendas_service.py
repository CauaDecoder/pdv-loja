"""Fachada de servico para Venda no caixa e Vendas e correcoes."""

from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from app.contracts import (
    STATUS_VENDA_ATIVA,
    STATUS_VENDA_CANCELADA,
    STATUS_VENDA_CORRIGIDA,
)
from app.payments import PAYMENT_METHODS
from app.database import _registrar_movimentacao_estoque, get_conn, registrar_venda

STATUS_VALIDOS = {"valid", "corrected", "cancelled"}
ACOES_CORRECAO = [
    "alter_payment",
    "alter_sale_date",
    "alter_item_quantity",
    "remove_item",
    "cancel_sale",
]
FORMAS_PAGAMENTO = set(PAYMENT_METHODS)
STATUS_PERSISTENTE = {
    "valid": STATUS_VENDA_ATIVA,
    "corrected": STATUS_VENDA_CORRIGIDA,
    "cancelled": STATUS_VENDA_CANCELADA,
}


def alterar_pagamento_venda(
    periodo_id: int,
    num_venda: int,
    pagamento: str,
    *,
    responsavel: str,
    pagamento_detalhe: str = "",
    valor_recebido: float | None = None,
    troco: float | None = None,
    destino_id: int | None = None,
    pagamentos: list[dict[str, Any]] | None = None,
    observacao: str = "",
) -> dict[str, Any]:
    """Corrige o pagamento de uma venda finalizada e preserva a auditoria."""
    pagamento = (pagamento or "").strip()
    pagamento_detalhe = (pagamento_detalhe or "").strip()

    if pagamento not in FORMAS_PAGAMENTO:
        raise ValueError("Forma de pagamento invalida.")
    valor_recebido = _normalizar_valor_pagamento(valor_recebido, "Valor recebido")
    troco = _normalizar_valor_pagamento(troco, "Troco")

    antes: dict[str, Any] = {}
    depois: dict[str, Any] = {}

    with _transacao_correcao(
        periodo_id=periodo_id,
        num_venda=num_venda,
        acao="alter_payment",
        responsavel=responsavel,
        antes=antes,
        depois=depois,
        novo_status="corrected",
        observacao=observacao,
    ) as conn:
        cabecalho = _obter_cabecalho(conn, periodo_id, num_venda)
        venda_id = int(cabecalho["id"])
        parcelas_antes = _obter_pagamentos_venda(conn, venda_id)
        antes.update(_contrato_pagamentos(parcelas_antes))
        total_centavos = int(
            conn.execute(
                """
                SELECT COALESCE(SUM(subtotal_centavos), 0)
                FROM vendas_itens i
                JOIN vendas_cabecalho h ON h.id = i.venda_id
                WHERE h.periodo_id = ? AND h.num_venda = ?
                """,
                (periodo_id, num_venda),
            ).fetchone()[0]
        )
        parcelas = _preparar_pagamentos_correcao(
            conn,
            total_centavos,
            pagamento,
            pagamento_detalhe,
            valor_recebido,
            troco,
            destino_id,
            pagamentos,
        )
        forma_legada, detalhe_legado, recebido_legado, troco_legado = (
            _resumo_pagamentos_legado(parcelas)
        )
        depois.update(
            _pagamento_estruturado_para_contrato(
                forma_legada,
                detalhe_legado,
                recebido_legado,
                troco_legado,
                parcelas,
            )
        )
        if antes == depois:
            raise ValueError("O novo pagamento deve ser diferente do atual.")

        _substituir_pagamentos(conn, venda_id, parcelas)

    detalhe = obter_detalhe_venda(periodo_id, num_venda)
    if detalhe is None:  # Protecao contra alteracao externa entre as transacoes.
        raise RuntimeError("Venda corrigida nao encontrada para consulta.")
    return detalhe


def alterar_quantidade_item_venda(
    periodo_id: int,
    num_venda: int,
    line_id: int,
    quantidade: int,
    *,
    responsavel: str,
    pagamentos: list[dict[str, Any]] | None = None,
    observacao: str = "",
) -> dict[str, Any]:
    """Corrige a quantidade de uma linha e ajusta apenas a diferenca no estoque."""
    quantidade = _normalizar_quantidade_item(quantidade)
    antes: dict[str, Any] = {}
    depois: dict[str, Any] = {}

    with _transacao_correcao(
        periodo_id=periodo_id,
        num_venda=num_venda,
        acao="alter_item_quantity",
        responsavel=responsavel,
        antes=antes,
        depois=depois,
        novo_status="corrected",
        observacao=observacao,
    ) as conn:
        item = _obter_item_venda(conn, periodo_id, num_venda, line_id)
        if pagamentos is not None:
            antes["payment"] = _contrato_pagamentos(
                _obter_pagamentos_venda(conn, int(item["venda_id"]))
            )
        quantidade_anterior = int(item["quantidade"])
        if quantidade == quantidade_anterior:
            raise ValueError("A nova quantidade deve ser diferente da atual.")

        antes.update(_item_para_contrato(item))
        depois.update(antes)
        depois["quantity"] = quantidade
        depois["subtotal"] = int(item["preco_unit_centavos"]) * quantidade / 100

        diferenca_estoque = quantidade_anterior - quantidade
        _registrar_ajuste_estoque_item(
            conn,
            item,
            diferenca_estoque,
            periodo_id=periodo_id,
            num_venda=num_venda,
            acao="QUANTIDADE",
            responsavel=responsavel,
        )
        conn.execute(
            """
            UPDATE vendas_itens
            SET quantidade = ?, subtotal_centavos = ?
            WHERE id = ? AND venda_id = ?
            """,
            (
                quantidade,
                int(item["preco_unit_centavos"]) * quantidade,
                int(item["id"]),
                int(item["venda_id"]),
            ),
        )
        _reconciliar_pagamento_apos_itens(
            conn, int(item["venda_id"]), novos_pagamentos=pagamentos
        )
        if pagamentos is not None:
            depois["payment"] = _contrato_pagamentos(
                _obter_pagamentos_venda(conn, int(item["venda_id"]))
            )

    detalhe = obter_detalhe_venda(periodo_id, num_venda)
    if detalhe is None:
        raise RuntimeError("Venda corrigida nao encontrada para consulta.")
    return detalhe


def remover_item_venda(
    periodo_id: int,
    num_venda: int,
    line_id: int,
    *,
    responsavel: str,
    pagamentos: list[dict[str, Any]] | None = None,
    observacao: str = "",
) -> dict[str, Any]:
    """Remove uma linha da venda, devolvendo sua quantidade ao estoque."""
    antes: dict[str, Any] = {}
    depois: dict[str, Any] = {}

    with _transacao_correcao(
        periodo_id=periodo_id,
        num_venda=num_venda,
        acao="remove_item",
        responsavel=responsavel,
        antes=antes,
        depois=depois,
        novo_status="corrected",
        observacao=observacao,
    ) as conn:
        item = _obter_item_venda(conn, periodo_id, num_venda, line_id)
        if pagamentos is not None:
            antes["payment"] = _contrato_pagamentos(
                _obter_pagamentos_venda(conn, int(item["venda_id"]))
            )
        total_itens = conn.execute(
            "SELECT COUNT(*) FROM vendas_itens WHERE venda_id = ?",
            (int(item["venda_id"]),),
        ).fetchone()[0]
        if total_itens <= 1:
            raise ValueError(
                "A venda deve manter ao menos um item; use Cancelar venda."
            )

        antes.update(_item_para_contrato(item))
        depois.update({"line_id": int(item["id"]), "removed": True})
        _registrar_ajuste_estoque_item(
            conn,
            item,
            int(item["quantidade"]),
            periodo_id=periodo_id,
            num_venda=num_venda,
            acao="REMOCAO",
            responsavel=responsavel,
        )
        conn.execute(
            "DELETE FROM vendas_itens WHERE id = ? AND venda_id = ?",
            (int(item["id"]), int(item["venda_id"])),
        )
        _reconciliar_pagamento_apos_itens(
            conn, int(item["venda_id"]), novos_pagamentos=pagamentos
        )
        if pagamentos is not None:
            depois["payment"] = _contrato_pagamentos(
                _obter_pagamentos_venda(conn, int(item["venda_id"]))
            )

    detalhe = obter_detalhe_venda(periodo_id, num_venda)
    if detalhe is None:
        raise RuntimeError("Venda corrigida nao encontrada para consulta.")
    return detalhe


def cancelar_venda(
    periodo_id: int,
    num_venda: int,
    *,
    responsavel: str,
    observacao: str = "",
    criado_em: str | None = None,
) -> dict[str, Any]:
    """Executa Cancelar venda e devolve ao estoque os itens vinculados."""
    devolucoes: list[dict[str, int]] = []
    antes: dict[str, Any] = {}
    depois: dict[str, Any] = {}
    momento_cancelamento = datetime.now()
    data = momento_cancelamento.strftime("%d/%m/%Y")
    hora = momento_cancelamento.strftime("%H:%M")

    with _transacao_correcao(
        periodo_id=periodo_id,
        num_venda=num_venda,
        acao="cancel_sale",
        responsavel=responsavel,
        antes=antes,
        depois=depois,
        novo_status="cancelled",
        observacao=observacao,
        criado_em=criado_em,
    ) as conn:
        cabecalho = _obter_cabecalho(conn, periodo_id, num_venda)
        venda_id = int(cabecalho["id"])
        linhas = conn.execute(
            """
            SELECT i.produto_id, SUM(i.quantidade) AS quantidade, h.status
            FROM vendas_cabecalho h
            JOIN vendas_itens i ON i.venda_id = h.id
            WHERE h.periodo_id = ? AND h.num_venda = ?
            GROUP BY i.produto_id, h.status
            """,
            (periodo_id, num_venda),
        ).fetchall()
        antes["status"] = _normalizar_status(linhas[0]["status"])
        antes["payment"] = _contrato_pagamentos(
            _obter_pagamentos_venda(conn, venda_id)
        )
        devolucoes.extend(
            {
                "product_id": int(linha["produto_id"]),
                "quantity": int(linha["quantidade"]),
            }
            for linha in linhas
            if linha["produto_id"] is not None
        )
        depois.update({"status": "cancelled", "stock_returned": devolucoes})

        for devolucao in devolucoes:
            produto_id = devolucao["product_id"]
            _registrar_movimentacao_estoque(
                conn,
                produto_id,
                "CANCELAMENTO",
                devolucao["quantity"],
                data,
                hora,
                referencia=f"CANCELAMENTO:{periodo_id}:{num_venda}:{produto_id}",
                observacao=f"Cancelamento da venda #{num_venda:03d}",
                responsavel=responsavel,
                origem="CORRECAO_POS_VENDA",
                alterar_saldo=True,
            )
    detalhe = obter_detalhe_venda(periodo_id, num_venda)
    if detalhe is None:
        raise RuntimeError("Venda cancelada nao encontrada para consulta.")
    return detalhe


def listar_vendas_correcoes(
    filtros: dict[str, Any] | None = None,
    limite: int = 100,
) -> list[dict[str, Any]]:
    """Lista vendas finalizadas, mantendo compatibilidade com o contrato antigo."""
    return consultar_vendas_correcoes(filtros, limite)["sales"]


def consultar_vendas_correcoes(
    filtros: dict[str, Any] | None = None,
    limite: int = 100,
) -> dict[str, Any]:
    """Consulta vendas e resumo financeiro usando filtros idênticos."""
    filtros = filtros or {}
    where, params = _montar_filtros(filtros)
    limite = max(1, int(limite))
    base_sql = """
        SELECT
            h.id AS venda_id,
            h.periodo_id,
            h.num_venda,
            h.data,
            h.hora,
            h.responsavel,
            h.status,
            COUNT(i.id) AS itens_diferentes,
            COALESCE(SUM(i.quantidade), 0) AS unidades,
            COALESCE(SUM(i.subtotal_centavos), 0) AS total_centavos
        FROM vendas_cabecalho h
        JOIN vendas_itens i ON i.venda_id = h.id
    """
    if where:
        base_sql += " WHERE " + " AND ".join(where)
    lista_sql = base_sql + """
        GROUP BY h.id
        ORDER BY (
            CASE
                WHEN instr(h.data, '/') > 0
                THEN substr(h.data, 7, 4) || '-' || substr(h.data, 4, 2) || '-' || substr(h.data, 1, 2)
                ELSE h.data
            END
        ) DESC,
        h.hora DESC,
        h.num_venda DESC
        LIMIT :limite
    """
    resumo_sql = """
        SELECT
            COUNT(*) AS matched_sales,
            COALESCE(SUM(CASE WHEN h.status != :status_cancelada THEN 1 ELSE 0 END), 0) AS financial_sales,
            COALESCE(SUM(CASE WHEN h.status = :status_cancelada THEN 1 ELSE 0 END), 0) AS cancelled_sales,
            COALESCE(SUM(CASE WHEN h.status != :status_cancelada THEN totais.total_centavos ELSE 0 END), 0) AS total_centavos
        FROM vendas_cabecalho h
        JOIN (
            SELECT venda_id, SUM(subtotal_centavos) AS total_centavos
            FROM vendas_itens
            GROUP BY venda_id
        ) totais ON totais.venda_id = h.id
    """
    if where:
        resumo_sql += " WHERE " + " AND ".join(where)
    parametros_lista = dict(params, limite=limite)
    parametros_resumo = dict(params, status_cancelada=STATUS_VENDA_CANCELADA)
    with get_conn() as conn:
        linhas = conn.execute(lista_sql, parametros_lista).fetchall()
        resumo = conn.execute(resumo_sql, parametros_resumo).fetchone()
        vendas = [
            _linha_lista_para_contrato(
                linha,
                _obter_pagamentos_venda(conn, int(linha["venda_id"])),
            )
            for linha in linhas
        ]
    encontrados = int(resumo["matched_sales"] or 0)
    return {
        "sales": vendas,
        "summary": {
            "matched_sales": encontrados,
            "shown_sales": len(vendas),
            "financial_sales": int(resumo["financial_sales"] or 0),
            "cancelled_sales": int(resumo["cancelled_sales"] or 0),
            "total_centavos": int(resumo["total_centavos"] or 0),
            "truncated": encontrados > len(vendas),
        },
    }


def alterar_data_venda(
    periodo_id: int,
    num_venda: int,
    nova_data: str,
    *,
    responsavel: str,
    observacao: str = "",
) -> dict[str, Any]:
    """Altera data efetiva sem mover Venda no caixa de Período da Loja."""
    data_iso = _normalizar_data_filtro(nova_data)
    if date.fromisoformat(data_iso) > date.today():
        raise ValueError("A Data da Venda no caixa não pode estar no futuro.")
    antes: dict[str, Any] = {}
    depois = {"date": data_iso}
    with _transacao_correcao(
        periodo_id=periodo_id,
        num_venda=num_venda,
        acao="alter_sale_date",
        responsavel=responsavel,
        antes=antes,
        depois=depois,
        novo_status="corrected",
        observacao=observacao,
    ) as conn:
        cabecalho = _obter_cabecalho(conn, periodo_id, num_venda)
        data_anterior = _normalizar_data_filtro(cabecalho["data"])
        if data_anterior == data_iso:
            raise ValueError("A nova data deve ser diferente da Data da Venda no caixa atual.")
        antes["date"] = data_anterior
        data_exibicao = _data_para_exibicao(data_iso)
        conn.execute(
            "UPDATE vendas_cabecalho SET data = ? WHERE id = ?",
            (data_exibicao, int(cabecalho["id"])),
        )
        conn.execute(
            """UPDATE movimentacoes_estoque
               SET data = ?, data_iso = ?
               WHERE tipo = 'VENDA' AND origem = 'PDV'
                 AND referencia LIKE ?""",
            (data_exibicao, data_iso, f"VENDA:{periodo_id}:{num_venda}:%"),
        )
    detalhe = obter_detalhe_venda(periodo_id, num_venda)
    if detalhe is None:
        raise RuntimeError("Venda corrigida não encontrada para consulta.")
    return detalhe


def obter_detalhe_venda(periodo_id: int, num_venda: int) -> dict[str, Any] | None:
    """Abre o detalhe de uma venda finalizada no contrato de integracao."""
    with get_conn() as conn:
        linhas = conn.execute(
            """
            SELECT
                i.id,
                i.venda_id,
                i.produto_id,
                i.codigo,
                i.nome,
                i.quantidade,
                i.preco_unit_centavos,
                i.subtotal_centavos,
                h.periodo_id,
                h.num_venda,
                h.data,
                h.hora,
                h.responsavel,
                h.status
            FROM vendas_cabecalho h
            JOIN vendas_itens i ON i.venda_id = h.id
            WHERE h.periodo_id = ? AND h.num_venda = ?
            ORDER BY i.id
            """,
            (periodo_id, num_venda),
        ).fetchall()
        if not linhas:
            return None

        historico = conn.execute(
            """
            SELECT *
            FROM vendas_correcoes
            WHERE periodo_id = ? AND num_venda = ?
            ORDER BY criado_em, id
            """,
            (periodo_id, num_venda),
        ).fetchall()
        pagamentos = _obter_pagamentos_venda(conn, int(linhas[0]["venda_id"]))

    return _linhas_detalhe_para_contrato(linhas, historico, pagamentos)


def registrar_correcao_venda(
    periodo_id: int,
    num_venda: int,
    acao: str,
    responsavel: str,
    antes: Any,
    depois: Any,
    novo_status: str = "corrected",
    observacao: str = "",
    criado_em: str | None = None,
) -> dict[str, Any]:
    """Persiste status e auditoria sem executar a mutacao de negocio da correcao.

    Os tickets de cancelamento, pagamento e itens usam ``_transacao_correcao``
    para incluir suas mutacoes na mesma transacao. Esta operacao cobre somente a
    base persistente definida para a issue de historico.
    """
    if (acao or "").strip() == "cancel_sale":
        return cancelar_venda(
            periodo_id,
            num_venda,
            responsavel=responsavel,
            observacao=observacao,
            criado_em=criado_em,
        )

    with _transacao_correcao(
        periodo_id=periodo_id,
        num_venda=num_venda,
        acao=acao,
        responsavel=responsavel,
        antes=antes,
        depois=depois,
        novo_status=novo_status,
        observacao=observacao,
        criado_em=criado_em,
    ):
        pass

    detalhe = obter_detalhe_venda(periodo_id, num_venda)
    if detalhe is None:  # Protege o contrato caso o banco seja alterado externamente.
        raise ValueError("Venda nao encontrada.")
    return detalhe


@contextmanager
def _transacao_correcao(
    periodo_id: int,
    num_venda: int,
    acao: str,
    responsavel: str,
    antes: Any,
    depois: Any,
    novo_status: str,
    observacao: str = "",
    criado_em: str | None = None,
) -> Iterator[sqlite3.Connection]:
    """Mantem mutacao futura, status e auditoria em uma unica transacao."""
    acao, responsavel, novo_status = _validar_dados_correcao(
        acao, responsavel, novo_status
    )
    criado_em = criado_em or datetime.now().isoformat(timespec="seconds")

    with get_conn() as conn:
        cabecalho = conn.execute(
            """SELECT h.id, h.status, pc.fechado_em
               FROM vendas_cabecalho h
               JOIN periodos_caixa pc ON pc.id = h.periodo_id
               WHERE h.periodo_id = ? AND h.num_venda = ?""",
            (periodo_id, num_venda),
        ).fetchone()
        if cabecalho is None:
            raise ValueError("Venda nao encontrada.")
        if cabecalho["fechado_em"] is not None:
            raise ValueError("Venda de Período da Loja fechado não pode ser corrigida.")
        status_atual = _normalizar_status(cabecalho["status"])
        if status_atual == "cancelled":
            raise ValueError("Venda cancelada nao pode receber nova correcao.")

        yield conn

        conn.execute(
            "UPDATE vendas_cabecalho SET status = ? WHERE periodo_id = ? AND num_venda = ?",
            (STATUS_PERSISTENTE[novo_status], periodo_id, num_venda),
        )
        conn.execute(
            """
            INSERT INTO vendas_correcoes
            (periodo_id, num_venda, acao, responsavel, criado_em,
             antes, depois, observacao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                periodo_id,
                num_venda,
                acao,
                responsavel,
                criado_em,
                _serializar_auditoria(antes),
                _serializar_auditoria(depois),
                observacao.strip(),
            ),
        )


def _validar_dados_correcao(
    acao: str,
    responsavel: str,
    novo_status: str,
) -> tuple[str, str, str]:
    acao = (acao or "").strip()
    responsavel = (responsavel or "").strip()
    novo_status = (novo_status or "").strip()
    if acao not in ACOES_CORRECAO:
        raise ValueError("Acao de correcao invalida.")
    if not responsavel:
        raise ValueError("Responsavel pela correcao e obrigatorio.")
    if novo_status not in {"corrected", "cancelled"}:
        raise ValueError("Status de correcao invalido.")
    if (acao == "cancel_sale") != (novo_status == "cancelled"):
        raise ValueError("Acao e status da correcao sao incompativeis.")
    return acao, responsavel, novo_status


def _serializar_auditoria(valor: Any) -> str:
    if isinstance(valor, str):
        return valor
    return json.dumps(
        valor,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _desserializar_auditoria(valor: str | None) -> Any:
    texto = valor or ""
    if not texto.startswith(("{", "[")):
        return texto
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        return texto


def _montar_filtros(filtros: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    where: list[str] = []
    params: dict[str, Any] = {}

    periodo_id = filtros.get("periodo_id")
    if periodo_id not in (None, ""):
        where.append("h.periodo_id = :periodo_id")
        params["periodo_id"] = int(periodo_id)

    num_venda = filtros.get("num_venda") or filtros.get("sale_number")
    if num_venda not in (None, ""):
        where.append("h.num_venda = :num_venda")
        params["num_venda"] = int(num_venda)

    data_sql = """CASE
        WHEN instr(h.data, '/') > 0
        THEN substr(h.data, 7, 4) || '-' || substr(h.data, 4, 2) || '-' || substr(h.data, 1, 2)
        ELSE h.data
    END"""
    data_inicio = (filtros.get("data_inicio") or "").strip()
    if data_inicio:
        where.append(f"{data_sql} >= :data_inicio")
        params["data_inicio"] = _normalizar_data_filtro(data_inicio)

    data_fim = (filtros.get("data_fim") or "").strip()
    if data_fim:
        where.append(f"{data_sql} <= :data_fim")
        params["data_fim"] = _normalizar_data_filtro(data_fim)
    if (
        params.get("data_inicio")
        and params.get("data_fim")
        and params["data_inicio"] > params["data_fim"]
    ):
        raise ValueError("A data inicial deve ser anterior ou igual à data final.")

    pagamento = (filtros.get("pagamento") or "").strip()
    if pagamento:
        where.append(
            "EXISTS (SELECT 1 FROM pagamentos_venda p "
            "WHERE p.venda_id = h.id AND p.forma = :pagamento)"
        )
        params["pagamento"] = pagamento

    responsavel = (filtros.get("responsavel") or "").strip()
    if responsavel:
        where.append("h.responsavel LIKE :responsavel")
        params["responsavel"] = f"%{responsavel}%"

    produto = (filtros.get("produto") or "").strip()
    if produto:
        where.append(
            "EXISTS (SELECT 1 FROM vendas_itens produto "
            "WHERE produto.venda_id = h.id "
            "AND (produto.nome LIKE :produto OR produto.codigo LIKE :produto))"
        )
        params["produto"] = f"%{produto}%"

    status = (filtros.get("status") or "").strip()
    if status:
        if status not in STATUS_VALIDOS:
            raise ValueError("Status de venda invalido.")
        where.append("h.status = :status")
        params["status"] = STATUS_PERSISTENTE[status]

    return where, params


def _normalizar_data_filtro(valor: str) -> str:
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(valor, formato).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError("Use datas no formato AAAA-MM-DD ou DD/MM/AAAA.")


def resolver_periodo_filtro(preset: str, hoje: date) -> tuple[str | None, str | None]:
    """Resolve preset temporal em ISO para a consulta de Vendas e correções."""
    nome = (preset or "").strip().lower()
    if nome in {"todo o histórico", "todo o historico", "histórico", "historico"}:
        return None, None
    if nome in {"esta semana", "semana"}:
        inicio = hoje - timedelta(days=hoje.weekday())
        fim = inicio + timedelta(days=6)
    elif nome in {"este mês", "este mes", "mês", "mes"}:
        inicio = hoje.replace(day=1)
        fim = date(hoje.year + (hoje.month == 12), hoje.month % 12 + 1, 1) - timedelta(days=1)
    elif nome in {"este ano", "ano"}:
        inicio, fim = date(hoje.year, 1, 1), date(hoje.year, 12, 31)
    else:
        raise ValueError("Preset de período inválido.")
    return inicio.isoformat(), fim.isoformat()


def _data_para_exibicao(valor: str) -> str:
    """Converte a data canônica ISO para o contrato público da UI."""
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(valor, formato).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return valor


def _linha_lista_para_contrato(
    linha: sqlite3.Row,
    pagamentos: list[sqlite3.Row],
) -> dict[str, Any]:
    status = _normalizar_status(linha["status"])
    total = int(linha["total_centavos"] or 0) / 100
    unidades = int(linha["unidades"] or 0)
    itens_diferentes = int(linha["itens_diferentes"] or 0)
    return {
        "sale_number": int(linha["num_venda"]),
        "period_id": linha["periodo_id"],
        "sold_at": {
            "date": _data_para_exibicao(linha["data"]),
            "time": linha["hora"],
        },
        "responsible": linha["responsavel"] or "",
        "payment_summary": _resumo_pagamentos_texto(pagamentos),
        "payment": _contrato_pagamentos(pagamentos),
        "total": total,
        "status": status,
        "item_summary": {
            "items": itens_diferentes,
            "units": unidades,
            "label": _resumo_itens(itens_diferentes, unidades),
        },
        "available_actions": _acoes_disponiveis(status),
    }


def _linhas_detalhe_para_contrato(
    linhas: list[sqlite3.Row],
    historico: list[sqlite3.Row],
    pagamentos: list[sqlite3.Row],
) -> dict[str, Any]:
    primeira = linhas[0]
    status = _normalizar_status(primeira["status"])
    total = sum(int(linha["subtotal_centavos"] or 0) for linha in linhas) / 100
    unidades = sum(int(linha["quantidade"] or 0) for linha in linhas)
    return {
        "identity": {
            "sale_number": int(primeira["num_venda"]),
            "period_id": primeira["periodo_id"],
        },
        "status": status,
        "responsible": primeira["responsavel"] or "",
        "timestamps": {
            "date": _data_para_exibicao(primeira["data"]),
            "time": primeira["hora"],
        },
        "payment": _contrato_pagamentos(pagamentos),
        "items": [_item_para_contrato(linha) for linha in linhas],
        "totals": {
            "items": len(linhas),
            "units": unidades,
            "total": total,
        },
        "correction_history": [_correcao_para_contrato(row) for row in historico],
        "available_actions": _acoes_disponiveis(status),
    }


def _contrato_pagamentos(pagamentos: list[sqlite3.Row]) -> dict[str, Any]:
    parcelas = [
        {
            "method": pagamento["forma"],
            "destination_id": int(pagamento["destino_id"]),
            "destination": pagamento["destino"],
            "value_centavos": int(pagamento["valor_centavos"]),
            "detail": pagamento["detalhe"] or "",
            "received_centavos": pagamento["valor_recebido_centavos"],
            "change_centavos": pagamento["troco_centavos"],
        }
        for pagamento in pagamentos
    ]
    forma, detalhe, recebido, troco = _resumo_pagamentos_legado(
        [
            {
                "forma": parcela["method"],
                "detalhe": parcela["detail"],
                "valor_recebido_centavos": parcela["received_centavos"],
                "troco_centavos": parcela["change_centavos"],
            }
            for parcela in parcelas
        ]
    ) if parcelas else ("", "", None, None)
    return {
        "method": forma,
        "detail": detalhe,
        "received": recebido,
        "change": troco,
        "installments": parcelas,
    }


def _obter_pagamentos_venda(
    conn: sqlite3.Connection,
    venda_id: int,
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT p.*, d.nome AS destino
        FROM pagamentos_venda p
        JOIN destinos_financeiros d ON d.id = p.destino_id
        WHERE p.venda_id = ?
        ORDER BY p.id
        """,
        (venda_id,),
    ).fetchall()


def _obter_cabecalho(
    conn: sqlite3.Connection,
    periodo_id: int,
    num_venda: int,
) -> sqlite3.Row:
    cabecalho = conn.execute(
        """SELECT * FROM vendas_cabecalho
           WHERE periodo_id = ? AND num_venda = ?""",
        (periodo_id, num_venda),
    ).fetchone()
    if cabecalho is None:
        raise ValueError("Venda nao encontrada.")
    return cabecalho


def _substituir_pagamentos(
    conn: sqlite3.Connection,
    venda_id: int,
    parcelas: list[dict[str, Any]],
) -> None:
    conn.execute("DELETE FROM pagamentos_venda WHERE venda_id = ?", (venda_id,))
    conn.executemany(
        """INSERT INTO pagamentos_venda
           (venda_id, forma, destino_id, valor_centavos, detalhe,
            valor_recebido_centavos, troco_centavos)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                venda_id,
                parcela["forma"],
                parcela["destino_id"],
                parcela["valor_centavos"],
                parcela["detalhe"],
                parcela["valor_recebido_centavos"],
                parcela["troco_centavos"],
            )
            for parcela in parcelas
        ],
    )


def _preparar_pagamentos_correcao(
    conn: sqlite3.Connection,
    total_centavos: int,
    pagamento: str,
    pagamento_detalhe: str,
    valor_recebido: float | None,
    troco: float | None,
    destino_id: int | None,
    pagamentos: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if pagamentos is None:
        if pagamento == "Mais de uma forma":
            raise ValueError("Informe duas ou mais parcelas para a Venda mista.")
        pagamentos = [
            {
                "forma": pagamento,
                "destino_id": destino_id,
                "valor_centavos": total_centavos,
                "detalhe": pagamento_detalhe,
                "valor_recebido_centavos": (
                    _moeda_para_centavos(valor_recebido)
                    if valor_recebido is not None
                    else None
                ),
                "troco_centavos": (
                    _moeda_para_centavos(troco) if troco is not None else None
                ),
            }
        ]
    if pagamento == "Mais de uma forma" and len(pagamentos) < 2:
        raise ValueError("A Venda mista deve ter duas ou mais parcelas.")

    parcelas: list[dict[str, Any]] = []
    for dados in pagamentos:
        forma = (dados.get("forma") or "").strip()
        if forma not in FORMAS_PAGAMENTO - {"Mais de uma forma"}:
            raise ValueError("Forma de pagamento invalida.")
        valor_centavos = _normalizar_centavos(
            dados.get("valor_centavos"), "Valor da parcela"
        )
        if valor_centavos <= 0:
            raise ValueError("Valor da parcela deve ser maior que zero.")
        destino = _obter_destino_compativel(
            conn,
            forma,
            dados.get("destino_id"),
        )
        recebido_centavos = _normalizar_centavos_opcional(
            dados.get("valor_recebido_centavos"), "Valor recebido"
        )
        troco_centavos = _normalizar_centavos_opcional(
            dados.get("troco_centavos"), "Troco"
        )
        if forma == "Dinheiro":
            if recebido_centavos is None or troco_centavos is None:
                raise ValueError(
                    "Valor recebido e troco são obrigatórios para Dinheiro."
                )
            if recebido_centavos - troco_centavos != valor_centavos:
                raise ValueError(
                    "Valor recebido menos troco deve ser igual ao valor em Dinheiro."
                )
        elif recebido_centavos is not None or troco_centavos is not None:
            raise ValueError(
                "Valor recebido e troco só podem ser informados para Dinheiro."
            )
        parcelas.append(
            {
                "forma": forma,
                "destino_id": int(destino["id"]),
                "destino": destino["nome"],
                "valor_centavos": valor_centavos,
                "detalhe": (dados.get("detalhe") or "").strip(),
                "valor_recebido_centavos": recebido_centavos,
                "troco_centavos": troco_centavos,
            }
        )

    if sum(parcela["valor_centavos"] for parcela in parcelas) != total_centavos:
        raise ValueError("A soma dos pagamentos deve ser igual ao total da venda.")
    return parcelas


def _obter_destino_compativel(
    conn: sqlite3.Connection,
    forma: str,
    destino_id: Any,
) -> sqlite3.Row:
    if destino_id in (None, ""):
        destino = conn.execute(
            """
            SELECT d.id, d.nome
            FROM destinos_financeiros d
            JOIN destino_formas_pagamento f ON f.destino_id = d.id
            WHERE d.ativo = 1 AND f.forma = ?
            ORDER BY f.padrao DESC, d.id
            LIMIT 1
            """,
            (forma,),
        ).fetchone()
    else:
        try:
            identificador = int(destino_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Destino financeiro invalido.") from exc
        destino = conn.execute(
            """
            SELECT d.id, d.nome
            FROM destinos_financeiros d
            JOIN destino_formas_pagamento f ON f.destino_id = d.id
            WHERE d.id = ? AND d.ativo = 1 AND f.forma = ?
            """,
            (identificador, forma),
        ).fetchone()
    if destino is None:
        raise ValueError(f"Destino financeiro ativo e compatível com {forma} não encontrado.")
    return destino


def _resumo_pagamentos_legado(
    parcelas: list[dict[str, Any]],
) -> tuple[str, str, float | None, float | None]:
    forma = parcelas[0]["forma"] if len(parcelas) == 1 else "Mais de uma forma"
    descricoes = []
    for parcela in parcelas:
        detalhe = parcela["detalhe"]
        descricoes.append(
            f"{parcela['forma']} ({detalhe})" if detalhe else parcela["forma"]
        )
    recebidos = [
        parcela["valor_recebido_centavos"]
        for parcela in parcelas
        if parcela["valor_recebido_centavos"] is not None
    ]
    trocos = [
        parcela["troco_centavos"]
        for parcela in parcelas
        if parcela["troco_centavos"] is not None
    ]
    return (
        forma,
        parcelas[0]["detalhe"] if len(parcelas) == 1 else " + ".join(descricoes),
        sum(recebidos) / 100 if recebidos else None,
        sum(trocos) / 100 if trocos else None,
    )


def _pagamento_estruturado_para_contrato(
    forma: str,
    detalhe: str,
    recebido: float | None,
    troco: float | None,
    parcelas: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "method": forma,
        "detail": detalhe,
        "received": recebido,
        "change": troco,
        "installments": [
            {
                "method": parcela["forma"],
                "destination_id": parcela["destino_id"],
                "destination": parcela["destino"],
                "value_centavos": parcela["valor_centavos"],
                "detail": parcela["detalhe"],
                "received_centavos": parcela["valor_recebido_centavos"],
                "change_centavos": parcela["troco_centavos"],
            }
            for parcela in parcelas
        ],
    }


def _moeda_para_centavos(valor: float) -> int:
    try:
        decimal = Decimal(str(valor))
    except InvalidOperation as exc:
        raise ValueError("Valor monetario invalido.") from exc
    return int((decimal * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _normalizar_centavos(valor: Any, campo: str) -> int:
    if isinstance(valor, bool):
        raise ValueError(f"{campo} invalido.")
    try:
        decimal = Decimal(str(valor))
        centavos = int(decimal)
    except (InvalidOperation, TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{campo} invalido.") from exc
    if not decimal.is_finite() or decimal != centavos:
        raise ValueError(f"{campo} deve ser informado em centavos inteiros.")
    return centavos


def _normalizar_centavos_opcional(valor: Any, campo: str) -> int | None:
    if valor is None:
        return None
    centavos = _normalizar_centavos(valor, campo)
    if centavos < 0:
        raise ValueError(f"{campo} nao pode ser negativo.")
    return centavos


def _normalizar_valor_pagamento(valor: float | None, campo: str) -> float | None:
    if valor is None:
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{campo} invalido.") from exc
    if not math.isfinite(numero):
        raise ValueError(f"{campo} invalido.")
    if numero < 0:
        raise ValueError(f"{campo} nao pode ser negativo.")
    return numero


def _reconciliar_pagamento_apos_itens(
    conn: sqlite3.Connection,
    venda_id: int,
    *,
    novos_pagamentos: list[dict[str, Any]] | None = None,
) -> None:
    """Ajusta venda simples ou substitui parcelas mistas informadas."""
    pagamentos = conn.execute(
        """SELECT id, forma, valor_centavos, valor_recebido_centavos,
                  troco_centavos
           FROM pagamentos_venda WHERE venda_id = ? ORDER BY id""",
        (venda_id,),
    ).fetchall()
    if not pagamentos:
        return
    total_centavos = int(
        conn.execute(
            "SELECT COALESCE(SUM(subtotal_centavos), 0) FROM vendas_itens WHERE venda_id = ?",
            (venda_id,),
        ).fetchone()[0]
    )
    if len(pagamentos) > 1:
        if novos_pagamentos is None:
            if sum(int(item["valor_centavos"]) for item in pagamentos) != total_centavos:
                raise ValueError(
                    "Informe as novas parcelas da venda mista para manter a conciliação."
                )
            return
        parcelas = _preparar_pagamentos_correcao(
            conn,
            total_centavos,
            "Mais de uma forma",
            "",
            None,
            None,
            None,
            novos_pagamentos,
        )
        _substituir_pagamentos(conn, venda_id, parcelas)
        return
    if novos_pagamentos is not None:
        raise ValueError("Novas parcelas só são necessárias para Venda mista.")
    if len(pagamentos) == 1:
        pagamento = pagamentos[0]
        if pagamento["forma"] == "Dinheiro":
            recebido = pagamento["valor_recebido_centavos"]
            if recebido is None or int(recebido) < total_centavos:
                raise ValueError(
                    "Informe novamente valor recebido e troco para manter a conciliação."
                )
            conn.execute(
                """UPDATE pagamentos_venda
                   SET valor_centavos = ?, troco_centavos = ? WHERE id = ?""",
                (total_centavos, int(recebido) - total_centavos, pagamento["id"]),
            )
        else:
            conn.execute(
                "UPDATE pagamentos_venda SET valor_centavos = ? WHERE id = ?",
                (total_centavos, pagamento["id"]),
            )


def _normalizar_quantidade_item(valor: Any) -> int:
    if isinstance(valor, bool):
        raise ValueError("Quantidade do item deve ser um numero inteiro positivo.")
    try:
        numero = float(valor)
        quantidade = int(numero)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            "Quantidade do item deve ser um numero inteiro positivo."
        ) from exc
    if not numero.is_integer() or quantidade <= 0:
        raise ValueError("Quantidade do item deve ser um numero inteiro positivo.")
    return quantidade


def _obter_item_venda(
    conn: sqlite3.Connection,
    periodo_id: int,
    num_venda: int,
    line_id: int,
) -> sqlite3.Row:
    try:
        line_id = int(line_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("Item da venda nao encontrado.") from exc
    item = conn.execute(
        """
        SELECT i.*, h.periodo_id, h.num_venda
        FROM vendas_itens i
        JOIN vendas_cabecalho h ON h.id = i.venda_id
        WHERE i.id = ? AND h.periodo_id = ? AND h.num_venda = ?
        """,
        (line_id, periodo_id, num_venda),
    ).fetchone()
    if item is None:
        raise ValueError("Item da venda nao encontrado.")
    return item


def _registrar_ajuste_estoque_item(
    conn: sqlite3.Connection,
    item: sqlite3.Row,
    quantidade: int,
    *,
    periodo_id: int,
    num_venda: int,
    acao: str,
    responsavel: str,
) -> None:
    produto_id = item["produto_id"]
    if produto_id is None or quantidade == 0:
        return
    agora = datetime.now()
    _registrar_movimentacao_estoque(
        conn,
        int(produto_id),
        "AJUSTE",
        quantidade,
        agora.strftime("%d/%m/%Y"),
        agora.strftime("%H:%M"),
        referencia=(
            f"CORRECAO_ITEM:{periodo_id}:{num_venda}:{int(item['id'])}:"
            f"{agora.isoformat(timespec='microseconds')}"
        ),
        observacao=(
            f"{acao.title()} do item da venda #{num_venda:03d}"
        ),
        responsavel=responsavel,
        origem="CORRECAO_POS_VENDA",
        alterar_saldo=True,
    )


def _item_para_contrato(linha: sqlite3.Row) -> dict[str, Any]:
    return {
        "line_id": int(linha["id"]),
        "product_id": linha["produto_id"],
        "code": linha["codigo"],
        "name": linha["nome"],
        "quantity": int(linha["quantidade"]),
        "unit_price": int(linha["preco_unit_centavos"]) / 100,
        "subtotal": int(linha["subtotal_centavos"]) / 100,
    }


def _correcao_para_contrato(linha: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(linha["id"]),
        "action": linha["acao"],
        "responsible": linha["responsavel"] or "",
        "created_at": linha["criado_em"],
        "before": _desserializar_auditoria(linha["antes"]),
        "after": _desserializar_auditoria(linha["depois"]),
        "note": linha["observacao"] or "",
    }


def _normalizar_status(status: str | None) -> str:
    persistente_para_publico = {
        STATUS_VENDA_ATIVA: "valid",
        STATUS_VENDA_CORRIGIDA: "corrected",
        STATUS_VENDA_CANCELADA: "cancelled",
        "valid": "valid",
        "corrected": "corrected",
        "cancelled": "cancelled",
    }
    return persistente_para_publico.get((status or "").strip(), "valid")


def _acoes_disponiveis(status: str) -> list[str]:
    if status == "cancelled":
        return []
    return list(ACOES_CORRECAO)


def _resumo_pagamentos_texto(pagamentos: list[sqlite3.Row]) -> str:
    return _contrato_pagamentos(pagamentos)["detail"] or _contrato_pagamentos(
        pagamentos
    )["method"]


def _resumo_itens(itens: int, unidades: int) -> str:
    sufixo_itens = "item" if itens == 1 else "itens"
    sufixo_unidades = "unidade" if unidades == 1 else "unidades"
    return f"{itens} {sufixo_itens}, {unidades} {sufixo_unidades}"


__all__ = [
    "ACOES_CORRECAO",
    "FORMAS_PAGAMENTO",
    "STATUS_VALIDOS",
    "alterar_quantidade_item_venda",
    "alterar_data_venda",
    "cancelar_venda",
    "alterar_pagamento_venda",
    "listar_vendas_correcoes",
    "consultar_vendas_correcoes",
    "obter_detalhe_venda",
    "registrar_correcao_venda",
    "registrar_venda",
    "remover_item_venda",
    "resolver_periodo_filtro",
]
