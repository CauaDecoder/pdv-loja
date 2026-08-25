"""Backup e restauracao segura do banco SQLite."""

from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from app.contracts import validar_contrato_banco


def _conectar_somente_leitura(caminho: Path) -> sqlite3.Connection:
    return sqlite3.connect(caminho.resolve().as_uri() + "?mode=ro", uri=True)


def _copiar_sqlite(origem_path: Path, destino_path: Path) -> None:
    origem = _conectar_somente_leitura(origem_path)
    destino = sqlite3.connect(destino_path)
    try:
        origem.backup(destino)
    finally:
        destino.close()
        origem.close()

def criar_backup(db_path: Path, backups_dir: Path) -> Path:
    if not db_path.exists():
        raise FileNotFoundError(f"Banco de dados nao encontrado: {db_path}")
    backups_dir.mkdir(parents=True, exist_ok=True)
    destino = backups_dir / f"loja_{datetime.now():%Y%m%d_%H%M%S_%f}.db"
    staging = backups_dir / f".{uuid.uuid4().hex}.staging.db"
    try:
        _copiar_sqlite(db_path, staging)
        validar_backup(staging)
        staging.replace(destino)
    except Exception:
        staging.unlink(missing_ok=True)
        raise
    return destino


def validar_backup(caminho: Path) -> None:
    if not caminho.exists():
        raise FileNotFoundError(f"Backup nao encontrado: {caminho}")
    conn = _conectar_somente_leitura(caminho)
    try:
        validar_contrato_banco(conn)
    finally:
        conn.close()


def restaurar_backup(caminho_backup: Path, db_path: Path, backups_dir: Path) -> Path | None:
    validar_backup(caminho_backup)
    backup_anterior = criar_backup(db_path, backups_dir) if db_path.exists() else None
    db_path.parent.mkdir(parents=True, exist_ok=True)
    staging = db_path.with_name(f".{db_path.name}.{uuid.uuid4().hex}.restore.db")
    rollback_staging = db_path.with_name(
        f".{db_path.name}.{uuid.uuid4().hex}.rollback.db"
    )
    try:
        _copiar_sqlite(caminho_backup, staging)
        validar_backup(staging)
        os.replace(staging, db_path)
        validar_backup(db_path)
    except Exception:
        if backup_anterior is not None:
            _copiar_sqlite(backup_anterior, rollback_staging)
            validar_backup(rollback_staging)
            os.replace(rollback_staging, db_path)
            validar_backup(db_path)
        raise
    finally:
        staging.unlink(missing_ok=True)
        rollback_staging.unlink(missing_ok=True)
    return backup_anterior
