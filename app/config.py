"""Carrega configuração operacional sem misturar segredos ao código."""

from __future__ import annotations

import json
import os
from pathlib import Path

from app.paths import DATA_DIR


def terminal_config(config_path: str | Path | None = None) -> dict:
    """Carrega configuração de Terminal somente quando solicitada."""
    path = Path(config_path or os.getenv("CAIXA_TERMINAL_CONFIG", DATA_DIR / "terminal-config.json"))
    if not path.exists():
        return {}
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("ca_cert") and not Path(config["ca_cert"]).is_absolute():
        config["ca_cert"] = str(path.parent / config["ca_cert"])
    return config


def server_config() -> dict:
    path = Path(os.getenv("CAIXA_SERVER_CONFIG", DATA_DIR / "central" / "server-config.json"))
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
