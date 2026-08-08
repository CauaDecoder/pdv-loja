from app import database
from app import main as package_main
from app.__main__ import main
from app.paths import BACKUPS_DIR, DATA_DIR, IMPORTS_DIR, PROJECT_ROOT, REPORTS_DIR
from scripts import higienizar_produtos


def test_caminhos_operacionais_partem_da_raiz_do_projeto():
    assert DATA_DIR == PROJECT_ROOT / "data"
    assert IMPORTS_DIR == DATA_DIR / "imports"
    assert BACKUPS_DIR == PROJECT_ROOT / "backups"
    assert REPORTS_DIR == PROJECT_ROOT / "relatorios"
    assert database.DB_PATH == DATA_DIR / "loja.db"


def test_entrypoint_legado_delega_ao_entrypoint_do_pacote():
    assert package_main.main is main


def test_script_de_importacao_usa_caminho_centralizado():
    assert higienizar_produtos.IMPORTS_DIR == IMPORTS_DIR


def test_raiz_contem_somente_arquivos_operacionais():
    permitidos = {
        ".env",
        ".env.example",
        ".gitignore",
        "AGENTS.md",
        "CONTEXT.md",
        "main.py",
        "README.md",
        "requirements.txt",
    }
    arquivos_na_raiz = {path.name for path in PROJECT_ROOT.iterdir() if path.is_file()}

    assert arquivos_na_raiz <= permitidos
