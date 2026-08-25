"""Caminhos operacionais da aplicacao, independentes do diretorio atual."""

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if getattr(sys, "frozen", False):
    # O executável instalado fica em uma pasta que pode ser substituída numa
    # atualização. Dados operacionais precisam sobreviver a essa troca.
    APP_DATA_DIR = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Loja da Basilica"
else:
    APP_DATA_DIR = PROJECT_ROOT

DATA_DIR = APP_DATA_DIR / "data"
IMPORTS_DIR = DATA_DIR / "imports"
BACKUPS_DIR = APP_DATA_DIR / "backups"
REPORTS_DIR = APP_DATA_DIR / "relatorios"
