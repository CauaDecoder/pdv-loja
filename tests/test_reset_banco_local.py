import hashlib
import sqlite3
from pathlib import Path

import pytest

from app import database
from app.contracts import SCHEMA_VERSION
from scripts import resetar_banco_local as reset_module
from scripts.resetar_banco_local import resetar_banco


def _criar_legado_vazio(caminho, com_produto=False):
    conn = sqlite3.connect(caminho)
    try:
        conn.execute("CREATE TABLE produtos (id INTEGER PRIMARY KEY, nome TEXT)")
        conn.execute("CREATE TABLE vendas (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE movimentacoes_estoque (id INTEGER PRIMARY KEY)")
        if com_produto:
            conn.execute("INSERT INTO produtos (nome) VALUES ('Não pode apagar')")
        conn.commit()
    finally:
        conn.close()


def test_reset_vazio_gera_backup_hash_schema_v2_e_seeds(tmp_path, monkeypatch):
    banco = tmp_path / "loja.db"
    _criar_legado_vazio(banco)
    sidecars = [Path(f"{banco}{sufixo}") for sufixo in ("-wal", "-shm")]
    for sidecar in sidecars:
        sidecar.touch()

    resultado = resetar_banco(banco, tmp_path / "backups")

    backup = resultado["backup"]
    assert backup.exists()
    assert hashlib.sha256(backup.read_bytes()).hexdigest() == resultado["sha256"]
    monkeypatch.setattr(database, "DB_PATH", banco)
    database.inicializar()
    with database.get_conn() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert conn.execute("SELECT COUNT(*) FROM produtos").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM vendas_cabecalho").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM movimentacoes_estoque").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM destinos_financeiros").fetchone()[0] == 3
    assert database.reconciliar_integridade_banco()["ok"] is True
    assert all(not sidecar.exists() for sidecar in sidecars)


def test_reset_recusa_banco_com_dado_operacional(tmp_path):
    banco = tmp_path / "loja.db"
    _criar_legado_vazio(banco, com_produto=True)

    with pytest.raises(ValueError, match="não está vazio"):
        resetar_banco(banco, tmp_path / "backups")

    with sqlite3.connect(banco) as conn:
        assert conn.execute("SELECT COUNT(*) FROM produtos").fetchone()[0] == 1
    assert not (tmp_path / "backups").exists()


def test_reset_aceita_periodo_residual_sem_vendas(tmp_path):
    banco = tmp_path / "loja.db"
    _criar_legado_vazio(banco)
    conn = sqlite3.connect(banco)
    try:
        conn.execute(
            "CREATE TABLE periodos_caixa (id INTEGER PRIMARY KEY, data TEXT)"
        )
        conn.execute("INSERT INTO periodos_caixa (data) VALUES ('19/08/2026')")
        conn.commit()
    finally:
        conn.close()

    resetar_banco(banco, tmp_path / "backups")

    with sqlite3.connect(banco) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert conn.execute("SELECT COUNT(*) FROM periodos_caixa").fetchone()[0] == 0


def test_reset_reverte_banco_anterior_se_validacao_pos_troca_falhar(
    tmp_path, monkeypatch
):
    banco = tmp_path / "loja.db"
    _criar_legado_vazio(banco)
    replace_real = reset_module.os.replace
    corrompeu = False

    def substituir_e_corromper(origem, destino):
        nonlocal corrompeu
        replace_real(origem, destino)
        if not corrompeu and Path(destino) == banco:
            corrompeu = True
            Path(destino).write_bytes(b"nao e sqlite")

    monkeypatch.setattr(reset_module.os, "replace", substituir_e_corromper)

    with pytest.raises(Exception):
        resetar_banco(banco, tmp_path / "backups")

    with sqlite3.connect(banco) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM produtos").fetchone()[0] == 0
