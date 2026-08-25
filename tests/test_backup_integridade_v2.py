import sqlite3
from pathlib import Path

import pytest

from app import database
from app.contracts import DatabaseValidationError
from app.services import backup_service


def test_validacao_rejeita_sqlite_integro_sem_schema_v2(tmp_path):
    arquivo = tmp_path / "incompleto.db"
    with sqlite3.connect(arquivo) as conn:
        conn.execute("CREATE TABLE produtos (id INTEGER PRIMARY KEY)")

    with pytest.raises(DatabaseValidationError, match="schema v2"):
        backup_service.validar_backup(arquivo)


def test_backup_v2_usa_staging_e_rejeita_divergencia_financeira(
    tmp_path, monkeypatch
):
    banco = tmp_path / "loja.db"
    monkeypatch.setattr(database, "DB_PATH", banco)
    database.inicializar()
    periodo = database.obter_ou_criar_periodo_aberto("19/08/2026")
    database.registrar_venda(
        periodo["id"],
        1,
        [{"codigo": "X", "nome": "Avulso", "quantidade": 1, "preco_unit": 5}],
        "Pix",
        pagamentos=[{"forma": "Pix", "valor_centavos": 500}],
        responsavel="Ana",
        chave_idempotencia="venda-backup",
    )

    backup = backup_service.criar_backup(banco, tmp_path / "backups")
    backup_service.validar_backup(backup)
    with sqlite3.connect(banco) as conn:
        conn.execute("UPDATE pagamentos_venda SET valor_centavos = 499")

    with pytest.raises(DatabaseValidationError, match="reconciliação"):
        backup_service.criar_backup(banco, tmp_path / "backups-invalidos")
    assert not list((tmp_path / "backups-invalidos").glob("*.db"))


def test_restauracao_reverte_banco_anterior_se_reabertura_falhar(
    tmp_path, monkeypatch
):
    banco = tmp_path / "loja.db"
    monkeypatch.setattr(database, "DB_PATH", banco)
    database.inicializar()
    database.criar_produto(
        {"codigo": "ATUAL", "nome": "Atual", "preco": 10, "estoque_inicial": 0}
    )
    backup_restaurado = backup_service.criar_backup(banco, tmp_path / "origens")
    database.criar_produto(
        {"codigo": "NOVO", "nome": "Novo", "preco": 20, "estoque_inicial": 0}
    )

    replace_real = backup_service.os.replace
    corrompeu = False

    def substituir_e_corromper(origem, destino):
        nonlocal corrompeu
        replace_real(origem, destino)
        if not corrompeu and Path(destino) == banco:
            corrompeu = True
            Path(destino).write_bytes(b"nao e sqlite")

    monkeypatch.setattr(backup_service.os, "replace", substituir_e_corromper)

    with pytest.raises(Exception):
        backup_service.restaurar_backup(
            backup_restaurado, banco, tmp_path / "seguranca"
        )

    backup_service.validar_backup(banco)
    with database.get_conn() as conn:
        codigos = {
            row[0] for row in conn.execute("SELECT codigo FROM produtos").fetchall()
        }
    assert codigos == {"ATUAL", "NOVO"}
