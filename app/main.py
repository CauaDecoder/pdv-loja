"""Ponto de entrada do pacote da aplicacao."""

from app.ui.app_window import CaixaApp


def main():
    app = CaixaApp()
    app.mainloop()


if __name__ == "__main__":
    main()
