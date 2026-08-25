from __future__ import annotations

import sys
import uuid

import pytest

from app.single_instance import SingleInstanceLock


@pytest.mark.skipif(sys.platform != "win32", reason="Mutex nomeado é específico do Windows")
def test_trava_impede_segunda_instancia_e_libera_ao_final():
    name = f"Local\\LojaBasilicaTeste-{uuid.uuid4()}"
    primeira = SingleInstanceLock(name)
    segunda = SingleInstanceLock(name)
    terceira = SingleInstanceLock(name)

    try:
        assert primeira.acquire() is True
        assert segunda.acquire() is False
        primeira.release()
        assert terceira.acquire() is True
    finally:
        primeira.release()
        segunda.release()
        terceira.release()
