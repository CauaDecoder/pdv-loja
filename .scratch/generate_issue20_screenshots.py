"""
Script para geracao de evidencias das 6 telas do PDV nos Temas Claro e Escuro para a Issue #20.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tempfile
import time
import tkinter as tk

import database
from app.ui.app_window import CaixaApp
from tema import definir_tema_atual


def run():
    out_dir = Path(r"C:\Users\Cauã\.gemini\antigravity-ide\brain\7dbdc782-6a41-49db-b7a4-9d78a308e821")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Gerando capturas das 6 telas...")


if __name__ == "__main__":
    run()
