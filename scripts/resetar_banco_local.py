"""Recria explicitamente um banco local vazio no schema atual."""

from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from app import database
from app.contracts import validar_contrato_banco
from app.paths import BACKUPS_DIR
from app.single_instance import SingleInstanceLock


TABELAS_OPERACIONAIS = (
    "produtos",
    "vendas",
    "vendas_cabecalho",
    "vendas_itens",
    "pagamentos_venda",
    "movimentacoes_estoque",
    "vendas_correcoes",
    "periodos_caixa",
    "importacoes_lotes",
    "fechamentos_periodo",
)


def _conectar_somente_leitura(caminho: Path) -> sqlite3.Connection:
    return sqlite3.connect(caminho.resolve().as_uri() + "?mode=ro", uri=True)


def _confirmar_banco_vazio(
    caminho: Path,
    *,
    permitir_periodos_residuais: bool = False,
) -> None:
    conn = _conectar_somente_leitura(caminho)
    try:
        if [row[0] for row in conn.execute("PRAGMA integrity_check")] != ["ok"]:
            raise ValueError("Banco local falhou no integrity_check.")
        if conn.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Banco local possui violações de chave estrangeira.")
        tabelas = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        tabelas_verificadas = (
            tabela
            for tabela in TABELAS_OPERACIONAIS
            if not (permitir_periodos_residuais and tabela == "periodos_caixa")
        )
        ocupadas = [
            tabela
            for tabela in tabelas_verificadas
            if tabela in tabelas
            and conn.execute(f"SELECT EXISTS(SELECT 1 FROM {tabela})").fetchone()[0]
        ]
    finally:
        conn.close()
    if ocupadas:
        raise ValueError(
            "Banco local não está vazio; reset recusado. Tabelas com dados: "
            + ", ".join(ocupadas)
        )


def _criar_snapshot(origem_path: Path, destino_path: Path) -> None:
    origem = _conectar_somente_leitura(origem_path)
    destino = sqlite3.connect(destino_path)
    try:
        origem.backup(destino)
    finally:
        destino.close()
        origem.close()


def _sha256(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def resetar_banco(db_path: Path, backups_dir: Path) -> dict:
    """Substitui banco comprovadamente vazio por schema v2 e preserva snapshot."""
    db_path = Path(db_path).resolve()
    backups_dir = Path(backups_dir).resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"Banco local não encontrado: {db_path}")
    lock = SingleInstanceLock()
    if not lock.acquire():
        raise ValueError("Feche o PDV completamente antes de executar o reset.")
    try:
        _confirmar_banco_vazio(db_path, permitir_periodos_residuais=True)

        backups_dir.mkdir(parents=True, exist_ok=True)
        backup = backups_dir / f"loja_antes_reset_v2_{datetime.now():%Y%m%d_%H%M%S_%f}.db"
        _criar_snapshot(db_path, backup)
        hash_backup = _sha256(backup)

        staging = db_path.with_name(f".{db_path.name}.{uuid.uuid4().hex}.staging")
        rollback_staging = db_path.with_name(
            f".{db_path.name}.{uuid.uuid4().hex}.rollback"
        )
        original = database.DB_PATH
        substituido = False
        try:
            database.DB_PATH = staging
            database.inicializar()
            conn = _conectar_somente_leitura(staging)
            try:
                validar_contrato_banco(conn)
            finally:
                conn.close()
            conn = sqlite3.connect(staging)
            try:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                conn.execute("PRAGMA journal_mode=DELETE").fetchone()
            finally:
                conn.close()
            os.replace(staging, db_path)
            substituido = True
            for sufixo in ("-wal", "-shm"):
                Path(f"{db_path}{sufixo}").unlink(missing_ok=True)
            conn = _conectar_somente_leitura(db_path)
            try:
                validar_contrato_banco(conn)
            finally:
                conn.close()
            _confirmar_banco_vazio(db_path)
        except Exception:
            if substituido:
                _criar_snapshot(backup, rollback_staging)
                os.replace(rollback_staging, db_path)
                for sufixo in ("-wal", "-shm"):
                    Path(f"{db_path}{sufixo}").unlink(missing_ok=True)
            raise
        finally:
            database.DB_PATH = original
            staging.unlink(missing_ok=True)
            rollback_staging.unlink(missing_ok=True)
        return {"backup": backup, "sha256": hash_backup, "banco": db_path}
    finally:
        lock.release()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=database.DB_PATH)
    parser.add_argument("--backups-dir", type=Path, default=BACKUPS_DIR)
    parser.add_argument("--confirm", metavar="PALAVRA", required=True)
    args = parser.parse_args()
    if args.confirm != "ZERAR":
        parser.error("Use --confirm ZERAR após fechar o PDV e conferir o banco vazio.")
    resultado = resetar_banco(args.db, args.backups_dir)
    print(f"Backup: {resultado['backup']}")
    print(f"SHA-256: {resultado['sha256']}")
    print(f"Banco v2: {resultado['banco']}")


if __name__ == "__main__":
    main()
