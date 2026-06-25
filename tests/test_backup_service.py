import sqlite3
from pathlib import Path

from app.services import backup_service


def test_backup_e_restauracao(tmp_path: Path):
    banco = tmp_path / "data" / "loja.db"
    banco.parent.mkdir()
    with sqlite3.connect(banco) as conn:
        conn.execute("CREATE TABLE produtos (id INTEGER PRIMARY KEY, nome TEXT)")
        conn.execute("INSERT INTO produtos (nome) VALUES ('Antes')")

    backup = backup_service.criar_backup(banco, tmp_path / "backups")
    with sqlite3.connect(banco) as conn:
        conn.execute("UPDATE produtos SET nome = 'Depois'")

    seguranca = backup_service.restaurar_backup(backup, banco, tmp_path / "backups")
    with sqlite3.connect(banco) as conn:
        nome = conn.execute("SELECT nome FROM produtos").fetchone()[0]

    assert nome == "Antes"
    assert seguranca is not None and seguranca.exists()
