"""Caminhos operacionais da aplicacao, independentes do diretorio atual."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
IMPORTS_DIR = DATA_DIR / "imports"
BACKUPS_DIR = PROJECT_ROOT / "backups"
REPORTS_DIR = PROJECT_ROOT / "relatorios"
