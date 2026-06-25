"""Ponto de entrada compativel da aplicacao Caixa Basilica."""

from app.ui.app_window import CaixaApp


def main():
    app = CaixaApp()
    app.mainloop()


if __name__ == "__main__":
    main()
