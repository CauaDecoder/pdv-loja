from pathlib import Path

from app import database
from app.services import backup_service


def test_backup_e_restauracao(tmp_path: Path, monkeypatch):
    banco = tmp_path / "data" / "loja.db"
    monkeypatch.setattr(database, "DB_PATH", banco)
    database.inicializar()
    produto_id = database.criar_produto(
        {"codigo": "P1", "nome": "Antes", "preco": 10, "estoque_inicial": 0}
    )

    backup = backup_service.criar_backup(banco, tmp_path / "backups")
    with database.get_conn() as conn:
        conn.execute("UPDATE produtos SET nome = 'Depois' WHERE id = ?", (produto_id,))

    seguranca = backup_service.restaurar_backup(backup, banco, tmp_path / "backups")
    with database.get_conn() as conn:
        nome = conn.execute("SELECT nome FROM produtos").fetchone()[0]

    assert nome == "Antes"
    assert seguranca is not None and seguranca.exists()
