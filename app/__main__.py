"""Ponto de entrada executavel com ``python -m app``."""

from app.ui.app_window import CaixaApp


def main() -> None:
    app = CaixaApp()
    app.mainloop()


if __name__ == "__main__":
    main()
