"""Fila local de vendas para contingência do Terminal de venda."""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

from app.remote import CentralClient, CentralUnavailable


class OfflineQueue:
    """Persiste comandos localmente e sincroniza cada chave uma vez."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS vendas_fila (chave TEXT PRIMARY KEY, payload TEXT NOT NULL, criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            conn.execute("CREATE TABLE IF NOT EXISTS cache (chave TEXT PRIMARY KEY, valor TEXT NOT NULL, atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")

    def enqueue_sale(self, payload: dict) -> str:
        chave = payload.setdefault("chave_idempotencia", str(uuid.uuid4()))
        with sqlite3.connect(self.path) as conn:
            conn.execute("INSERT OR IGNORE INTO vendas_fila (chave, payload) VALUES (?, ?)", (chave, json.dumps(payload)))
        return chave

    def pending(self) -> list[dict]:
        with sqlite3.connect(self.path) as conn:
            return [json.loads(row[0]) for row in conn.execute("SELECT payload FROM vendas_fila ORDER BY criado_em, chave")]

    def sync(self, client: CentralClient) -> int:
        enviados = 0
        for payload in self.pending():
            try:
                client.create_sale(payload)
            except CentralUnavailable:
                break
            with sqlite3.connect(self.path) as conn:
                conn.execute("DELETE FROM vendas_fila WHERE chave = ?", (payload["chave_idempotencia"],))
            enviados += 1
        return enviados

    def cache_set(self, key: str, value) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT INTO cache (chave, valor) VALUES (?, ?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor, atualizado_em=CURRENT_TIMESTAMP",
                (key, json.dumps(value)),
            )

    def cache_get(self, key: str):
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT valor FROM cache WHERE chave = ?", (key,)).fetchone()
        if row is None:
            raise CentralUnavailable("Dado não disponível no cache offline.")
        return json.loads(row[0])
