"""Backup e restauracao segura do banco SQLite."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


def criar_backup(db_path: Path, backups_dir: Path) -> Path:
    if not db_path.exists():
        raise FileNotFoundError(f"Banco de dados nao encontrado: {db_path}")
    backups_dir.mkdir(parents=True, exist_ok=True)
    destino = backups_dir / f"loja_{datetime.now():%Y%m%d_%H%M%S_%f}.db"
    with sqlite3.connect(db_path) as origem, sqlite3.connect(destino) as backup:
        origem.backup(backup)
    return destino


def validar_backup(caminho: Path) -> None:
    if not caminho.exists():
        raise FileNotFoundError(f"Backup nao encontrado: {caminho}")
    with sqlite3.connect(caminho) as conn:
        resultado = conn.execute("PRAGMA integrity_check").fetchone()
        if not resultado or resultado[0] != "ok":
            raise ValueError("O arquivo selecionado nao e um backup SQLite integro.")
        tabelas = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        if "produtos" not in tabelas:
            raise ValueError("O backup selecionado nao pertence ao sistema da loja.")


def restaurar_backup(caminho_backup: Path, db_path: Path, backups_dir: Path) -> Path | None:
    validar_backup(caminho_backup)
    backup_anterior = criar_backup(db_path, backups_dir) if db_path.exists() else None
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(caminho_backup) as origem, sqlite3.connect(db_path) as destino:
        origem.backup(destino)
    return backup_anterior
