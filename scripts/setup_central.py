"""Prepara banco, HTTPS e dois Terminais para a instalação central."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import shutil
import socket
import subprocess
import getpass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def _local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return socket.gethostbyname(socket.gethostname())


def _certificate(directory: Path, host: str, ips: str | list[str]) -> tuple[Path, Path]:
    """Generate a private key and certificate for every explicit address."""
    directory.mkdir(parents=True, exist_ok=True)
    ip_values = [ips] if isinstance(ips, str) else ips
    if not ip_values:
        raise ValueError("Informe pelo menos um IPv4 para o certificado.")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject).issuer_name(issuer).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=5))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1825))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName(host)]
                + [x509.IPAddress(ipaddress.ip_address(ip)) for ip in ip_values]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    key_path = directory / "server-key.pem"
    cert_path = directory / "server.crt"
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    return cert_path, key_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", action="append", help="IPv4 para SAN; pode ser repetido")
    parser.add_argument("--host", default=socket.gethostname())
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    ips = args.ip or [_local_ip()]
    root = Path(__file__).resolve().parent.parent
    central = root / "data" / "central"
    output = root / "setup-output"
    if (central / "loja.db").exists():
        raise SystemExit("Central já configurada. Arquive a pasta data/central antes de recriar.")
    central.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=True)
    cert, key = _certificate(central, args.host, ips)
    db_path = central / "loja.db"
    os.environ["CAIXA_DB_PATH"] = str(db_path)
    from app import database
    from app.api import criar_terminal

    database.DB_PATH = db_path
    database.inicializar()
    terminals = (("Caixa", True), ("Financeiro", False))
    for name, offline in terminals:
        terminal_id, token = criar_terminal(name, offline)
        target = output / name.lower()
        target.mkdir(exist_ok=True)
        shutil.copy2(cert, target / "central-ca.crt")
        (target / "terminal-config.json").write_text(json.dumps({
            "url": f"https://{ips[-1]}:{args.port}", "token": token,
            "ca_cert": "central-ca.crt", "permite_offline": offline,
            "terminal_id": terminal_id, "nome": name,
        }, indent=2), encoding="utf-8")
    (central / "server-config.json").write_text(json.dumps({
        "db_path": str(db_path), "port": args.port,
        "tls_cert": str(cert), "tls_key": str(key),
    }, indent=2), encoding="utf-8")
    if os.name == "nt":
        subprocess.run(["icacls", str(central), "/inheritance:r", "/grant:r", f"{getpass.getuser()}:(OI)(CI)F", "/grant:r", "SYSTEM:(OI)(CI)F"], check=False, capture_output=True)
    print(f"Central pronta em https://{ips[-1]}:{args.port}")
    print(f"Configurações dos Terminais: {output}")


if __name__ == "__main__":
    main()
