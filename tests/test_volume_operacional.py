import time

from app import database


def test_volume_realista_mantem_busca_e_snapshot_rapidos(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "volume.db")
    database.inicializar()
    with database.get_conn() as conn:
        conn.executemany(
            """INSERT INTO produtos
               (codigo, cod_barras, nome, preco_centavos,
                custo_unitario_centavos, estoque)
               VALUES (?, ?, ?, 1000, 600, 100)""",
            [
                (
                    f"SKU{indice:04d}",
                    f"789{indice:010d}",
                    f"Produto {indice:04d}",
                )
                for indice in range(1600)
            ],
        )
    periodo = database.obter_ou_criar_periodo_aberto("19/08/2026")
    for numero in range(1, 1001):
        indice = (numero - 1) % 1600
        database.registrar_venda(
            periodo["id"],
            numero,
            [{
                "produto_id": indice + 1,
                "codigo": f"SKU{indice:04d}",
                "nome": f"Produto {indice:04d}",
                "quantidade": 1,
                "preco_unit_centavos": 1000,
            }],
            "Pix",
            pagamentos=[{"forma": "Pix", "valor_centavos": 1000}],
            responsavel="Teste de volume",
            chave_idempotencia=f"volume-{numero}",
        )

    database.buscar_produto("SKU1599")
    inicio = time.perf_counter()
    resultado = database.buscar_produto("SKU1599")
    duracao_busca = time.perf_counter() - inicio

    inicio = time.perf_counter()
    snapshot = database.snapshot_dashboard_estoque()
    duracao_snapshot = time.perf_counter() - inicio

    assert [row["codigo"] for row in resultado] == ["SKU1599"]
    assert duracao_busca < 0.05
    assert duracao_snapshot < 2.0
    assert snapshot["resumo"]["skus_ativos"] == 1600
