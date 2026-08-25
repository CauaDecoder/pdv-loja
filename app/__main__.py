"""Ponto de entrada executável com ``python -m app``."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.runtime import Runtime, configure_runtime
from app.single_instance import SingleInstanceLock


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="PDV da Loja da Basílica")
    parser.add_argument("--central", action="store_true", help="Conectar explicitamente à Central")
    parser.add_argument("--config", type=Path, help="Configuração do Terminal para modo Central")
    parser.add_argument("--database", type=Path, help="Banco SQLite local alternativo")
    args = parser.parse_args(argv)
    if args.central and args.database:
        parser.error("--database não pode ser usado com --central")
    if args.config and not args.central:
        parser.error("--config exige --central")

    lock = SingleInstanceLock()
    if not lock.acquire():
        parser.error("o PDV já está aberto neste computador")
    try:
        configure_runtime(Runtime.central(args.config) if args.central else Runtime.local(args.database))
        from app.ui.app_window import CaixaApp, StartupError

        try:
            app = CaixaApp()
        except StartupError:
            return
        app.mainloop()
    finally:
        lock.release()


if __name__ == "__main__":
    main()
