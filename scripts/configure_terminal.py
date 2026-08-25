"""Instala no computador atual um pacote gerado por setup_central."""

from __future__ import annotations

import argparse
import getpass
import os
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", help="Pasta caixa ou financeiro criada em setup-output")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    package = Path(args.package).resolve()
    data = root / "data"
    data.mkdir(exist_ok=True)
    shutil.copy2(package / "terminal-config.json", data / "terminal-config.json")
    shutil.copy2(package / "central-ca.crt", data / "central-ca.crt")
    if os.name == "nt":
        subprocess.run(["icacls", str(data / "terminal-config.json"), "/inheritance:r", "/grant:r", f"{getpass.getuser()}:F"], check=False, capture_output=True)
    print("Terminal configurado. Execute: python -m app")


if __name__ == "__main__":
    main()
