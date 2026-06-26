"""Helpers para executar trabalho em background sem tocar widgets fora da UI."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any


Dispatcher = Callable[[int, Callable[[], None]], Any]


class AsyncTaskRunner:
    """Executa tarefas em background e entrega resultados na thread principal."""

    def __init__(self, dispatcher: Dispatcher):
        self._dispatcher = dispatcher
        self._lock = threading.Lock()
        self._versions: dict[str, int] = {}

    def submit(
        self,
        key: str,
        work: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        with self._lock:
            version = self._versions.get(key, 0) + 1
            self._versions[key] = version

        def target() -> None:
            try:
                result = work()
            except Exception as exc:  # pragma: no cover - depende do ambiente grafico
                self._dispatcher(0, lambda: self._deliver_error(key, version, exc, on_error))
                return
            self._dispatcher(0, lambda: self._deliver_success(key, version, result, on_success))

        threading.Thread(target=target, daemon=True, name=f"bg-{key}").start()

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._versions[key] = self._versions.get(key, 0) + 1

    def _is_current(self, key: str, version: int) -> bool:
        with self._lock:
            return self._versions.get(key) == version

    def _deliver_success(
        self,
        key: str,
        version: int,
        result: Any,
        on_success: Callable[[Any], None],
    ) -> None:
        if self._is_current(key, version):
            on_success(result)

    def _deliver_error(
        self,
        key: str,
        version: int,
        exc: Exception,
        on_error: Callable[[Exception], None] | None,
    ) -> None:
        if self._is_current(key, version) and on_error is not None:
            on_error(exc)
