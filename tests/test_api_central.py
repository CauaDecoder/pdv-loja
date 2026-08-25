import asyncio
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

import httpx

from app import api, database


@asynccontextmanager
async def _api_client():
    transport = httpx.ASGITransport(app=api.app)
    async with api.app.router.lifespan_context(api.app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


def _run(coro):
    return asyncio.run(coro)


def test_api_expoe_destinos_e_rejeita_pagamento_inconsistente():
    async def scenario():
        original = database.DB_PATH
        with tempfile.TemporaryDirectory() as directory:
            database.DB_PATH = Path(directory) / "central.db"
            async with _api_client() as client:
                destinos = await client.get("/destinations")
                assert destinos.status_code == 200
                response = await client.post(
                    "/sales",
                    json={
                        "itens": [{"codigo": "A", "nome": "A", "quantidade": 1, "preco_unit": 10}],
                        "pagamentos": [{"forma": "Pix", "valor_centavos": 999}],
                        "responsavel": "Operadora",
                        "chave_idempotencia": "api-test",
                        "data": "2026-08-12",
                    },
                )
                assert response.status_code == 422
        database.DB_PATH = original

    _run(scenario())


def test_api_exige_token_quando_terminal_foi_cadastrado():
    async def scenario():
        original = database.DB_PATH
        with tempfile.TemporaryDirectory() as directory:
            database.DB_PATH = Path(directory) / "central.db"
            database.inicializar()
            _, token = api.criar_terminal("Caixa", True)
            async with _api_client() as client:
                assert (await client.get("/destinations")).status_code == 401
                response = await client.get("/destinations", headers={"Authorization": f"Bearer {token}"})
                assert response.status_code == 200
        database.DB_PATH = original

    _run(scenario())


def test_dois_terminais_compartilham_produto_venda_e_relatorio():
    async def scenario():
        original = database.DB_PATH
        with tempfile.TemporaryDirectory() as directory:
            database.DB_PATH = Path(directory) / "central.db"
            database.inicializar()
            _, token_caixa = api.criar_terminal("Caixa", True)
            _, token_financeiro = api.criar_terminal("Financeiro", False)
            caixa = {"Authorization": f"Bearer {token_caixa}"}
            financeiro = {"Authorization": f"Bearer {token_financeiro}"}
            async with _api_client() as client:
                produto = await client.post("/rpc/database/criar_produto", headers=financeiro, json={
                    "args": [{"codigo": "P1", "nome": "Produto", "preco": 10, "estoque": 5}], "kwargs": {}
                })
                assert produto.status_code == 200
                busca = await client.post("/rpc/database/buscar_produto", headers=caixa, json={"args": ["P1"], "kwargs": {}})
                assert busca.json()[0]["nome"] == "Produto"
                payload = {
                    "itens": [{"produto_id": produto.json(), "codigo": "P1", "nome": "Produto", "quantidade": 1, "preco_unit": 10}],
                    "pagamentos": [{"forma": "Pix", "valor_centavos": 1000}],
                    "responsavel": "Operadora",
                    "chave_idempotencia": "compartilhada", "data": "2026-08-12",
                }
                venda = await client.post("/sales", headers=caixa, json=payload)
                assert venda.status_code == 200
                repetida = await client.post("/sales", headers=caixa, json=payload)
                assert repetida.json() == venda.json()
                relatorio = await client.get("/reports/sales.xlsx?data_inicial=2026-08-12&data_final=2026-08-12", headers=financeiro)
                assert relatorio.status_code == 200
                assert relatorio.content.startswith(b"PK")
            assert len(database.vendas_do_periodo(venda.json()["periodo_id"])) == 1
        database.DB_PATH = original

    _run(scenario())


def test_api_expoe_contexto_de_venda_e_snapshots_de_estoque_agregados():
    async def scenario():
        original = database.DB_PATH
        with tempfile.TemporaryDirectory() as directory:
            database.DB_PATH = Path(directory) / "central.db"
            async with _api_client() as client:
                context = await client.post(
                    "/rpc/database/contexto_inicial_venda_no_caixa",
                    json={"args": ["18/08/2026"], "kwargs": {}},
                )
                dashboard = await client.post(
                    "/rpc/database/snapshot_dashboard_estoque",
                    json={"args": [], "kwargs": {}},
                )
                operational = await client.post(
                    "/rpc/database/snapshot_operacional_estoque",
                    json={"args": [], "kwargs": {}},
                )

            assert context.status_code == 200
            assert set(context.json()) == {"periodo", "totais", "proximo_num_venda", "destinos"}
            assert set(dashboard.json()) == {
                "resumo", "status", "curva_abc", "categorias", "valor_parado", "vendidos", "movimentacoes"
            }
            assert set(operational.json()) == {"produtos", "categorias", "fornecedores"}
        database.DB_PATH = original

    _run(scenario())
