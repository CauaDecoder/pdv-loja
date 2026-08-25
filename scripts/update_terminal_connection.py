"""Update only a Terminal URL and trusted public certificate."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from cryptography import x509


def _certificate_accepts(cert_path: Path, host: str) -> bool:
    certificate = x509.load_pem_x509_certificate(cert_path.read_bytes())
    sans = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    values = set(sans.get_values_for_type(x509.DNSName))
    values.update(str(value) for value in sans.get_values_for_type(x509.IPAddress))
    return host in values


def update_connection(config_path: Path, url: str, ca_file: Path) -> Path:
    """Preserve Terminal identity while updating its validated HTTPS destination."""
    config_path = config_path.resolve()
    ca_file = ca_file.resolve()
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("URL deve usar HTTPS e não pode conter credencial.")
    if not ca_file.is_file() or not _certificate_accepts(ca_file, parsed.hostname):
        raise ValueError(f"Certificado não contém SAN para {parsed.hostname}.")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("verify") is False:
        raise ValueError("Configuração verify=False não é permitida.")

    data_dir = config_path.parent
    old_ca = Path(config.get("ca_cert", ""))
    if old_ca and not old_ca.is_absolute():
        old_ca = data_dir / old_ca
    backup = data_dir / "backups" / f"connection-{datetime.now():%Y%m%d-%H%M%S-%f}"
    backup.mkdir(parents=True)
    shutil.copy2(config_path, backup / config_path.name)
    if old_ca.is_file():
        shutil.copy2(old_ca, backup / old_ca.name)

    target_ca = data_dir / "central-ca.crt"
    with tempfile.NamedTemporaryFile(dir=data_dir, delete=False) as temporary_cert:
        temporary_cert.write(ca_file.read_bytes())
        temporary_cert_path = Path(temporary_cert.name)
    updated = dict(config)
    updated["url"] = url.rstrip("/")
    updated["ca_cert"] = target_ca.name
    with tempfile.NamedTemporaryFile("w", dir=data_dir, encoding="utf-8", delete=False) as temporary_config:
        json.dump(updated, temporary_config, ensure_ascii=False, indent=2)
        temporary_config.write("\n")
        temporary_config_path = Path(temporary_config.name)
    temporary_cert_path.replace(target_ca)
    temporary_config_path.replace(config_path)
    if os.name == "nt":
        os.chmod(config_path, 0o600)
    return backup


def main() -> None:
    parser = argparse.ArgumentParser(description="Atualiza somente URL e certificado público do Terminal.")
    parser.add_argument("--url", required=True)
    parser.add_argument("--ca-file", required=True, type=Path)
    parser.add_argument("--config", type=Path, default=Path("data/terminal-config.json"))
    args = parser.parse_args()
    backup = update_connection(args.config, args.url, args.ca_file)
    print(f"Conexão atualizada. Backup: {backup}")


if __name__ == "__main__":
    main()
