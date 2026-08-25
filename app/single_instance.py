"""Trava de instância única do aplicativo no Windows."""

from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass
from ctypes import wintypes


ERROR_ALREADY_EXISTS = 183


@dataclass
class SingleInstanceLock:
    """Mantém um mutex nomeado enquanto o processo do PDV estiver ativo."""

    name: str = "Local\\LojaBasilicaCaixa"
    _handle: int | None = None

    def acquire(self) -> bool:
        if sys.platform != "win32":
            return True
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        handle = kernel32.CreateMutexW(None, False, self.name)
        if not handle:
            raise OSError(ctypes.get_last_error(), "Não foi possível criar a trava do aplicativo.")
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        if self._handle is None or sys.platform != "win32":
            return
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(self._handle)
        self._handle = None
