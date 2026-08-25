"""Cria snapshot consistente e copia para destino externo."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

from app.config import server_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination")
    args = parser.parse_args()
    config = server_config()
    os.environ["CAIXA_DB_PATH"] = config["db_path"]
    from app import database
    from app.services.backup_service import criar_backup

    database.DB_PATH = Path(config["db_path"])
    staging = database.DB_PATH.parent / "backups"
    backup = criar_backup(database.DB_PATH, staging)
    destination = Path(args.destination)
    destination.mkdir(parents=True, exist_ok=True)
    copied = shutil.copy2(backup, destination / backup.name)
    print(copied)


if __name__ == "__main__":
    main()
