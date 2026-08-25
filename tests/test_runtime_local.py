import json

import pytest

from app import database
from app import runtime as runtime_module
from app.runtime import RemoteDatabase, Runtime


def test_runtime_local_ignora_configuracao_central_invalida(tmp_path, monkeypatch):
    config = tmp_path / "terminal-config.json"
    config.write_text("{", encoding="utf-8")
    monkeypatch.setenv("CAIXA_TERMINAL_CONFIG", str(config))
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "original.db")

    runtime = Runtime.local(tmp_path / "local.db")

    assert runtime.client is None
    assert runtime.database is database
    assert not (tmp_path / "local.db").exists()


def test_runtime_central_so_e_criado_explicitamente(tmp_path):
    config = tmp_path / "terminal-config.json"
    config.write_text(json.dumps({"url": "http://127.0.0.1:8765"}), encoding="utf-8")

    runtime = Runtime.central(config)

    assert runtime.client is not None
    assert runtime.database is not database
    runtime.client.close()


def test_importacao_local_repassa_operador_lote_e_hash(tmp_path, monkeypatch):
    recebido = {}

    def importar(path, **kwargs):
        recebido.update(path=path, **kwargs)
        return {"lote_id": kwargs["lote_id"]}

    monkeypatch.setattr(database, "importar_csv", importar)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "baseline.db")
    runtime_module.configure_runtime(Runtime.local(tmp_path / "local.db"))

    resultado = runtime_module.execute_import(
        "produtos.xlsx",
        "INVENTARIO_INICIAL",
        responsavel="Ana",
        lote_id="lote-1",
        hash_arquivo="abc123",
    )

    assert resultado == {"lote_id": "lote-1"}
    assert recebido == {
        "path": "produtos.xlsx",
        "modo_estoque": "INVENTARIO_INICIAL",
        "responsavel": "Ana",
        "lote_id": "lote-1",
        "hash_arquivo": "abc123",
    }


def test_adapter_central_arredonda_preco_unitario_antes_de_somar():
    class Client:
        payload = None

        def create_sale(self, payload):
            self.payload = payload
            return {"total_centavos": payload["pagamentos"][0]["valor_centavos"]}

    client = Client()
    adapter = RemoteDatabase(client, "database")

    resultado = adapter.registrar_venda(
        1,
        1,
        [{"codigo": "P1", "nome": "Produto", "quantidade": 2, "preco_unit": "0.015"}],
        "Pix",
        responsavel="Ana",
        chave_idempotencia="venda-1",
    )

    assert resultado["total_centavos"] == 4
    assert client.payload["pagamentos"][0]["valor_centavos"] == 4


def test_adapter_central_exige_operador_e_uuid():
    adapter = RemoteDatabase(object(), "database")

    with pytest.raises(ValueError, match="Operador"):
        adapter.registrar_venda(1, 1, [], "Pix", chave_idempotencia="venda-1")
    with pytest.raises(ValueError, match="idempotente"):
        adapter.registrar_venda(1, 1, [], "Pix", responsavel="Ana")
