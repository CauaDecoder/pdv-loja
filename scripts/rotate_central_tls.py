"""Rotate Central TLS material without opening its database or configuration."""

from __future__ import annotations

import argparse
import ipaddress
import shutil
import socket
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization

from scripts.setup_central import _certificate


@dataclass(frozen=True)
class RotationResult:
    """Describe the recoverable output of a TLS rotation."""

    backup_dir: Path
    certificate: Path
    private_key: Path


def _validate_material(cert_path: Path, key_path: Path, host: str, ips: list[str]) -> None:
    certificate = x509.load_pem_x509_certificate(cert_path.read_bytes())
    private_key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    cert_public = certificate.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    key_public = private_key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    if cert_public != key_public:
        raise ValueError("Chave privada não corresponde ao certificado.")
    sans = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    dns_names = set(sans.get_values_for_type(x509.DNSName))
    ip_addresses = {str(value) for value in sans.get_values_for_type(x509.IPAddress)}
    missing = ({host} - dns_names) | (set(ips) - ip_addresses)
    if missing:
        raise ValueError(f"SANs ausentes: {', '.join(sorted(missing))}")
    now = datetime.now(timezone.utc)
    if hasattr(certificate, "not_valid_before_utc"):
        not_before = certificate.not_valid_before_utc
        not_after = certificate.not_valid_after_utc
    else:  # pragma: no cover - compatibilidade com cryptography antigo
        not_before = certificate.not_valid_before.replace(tzinfo=timezone.utc)
        not_after = certificate.not_valid_after.replace(tzinfo=timezone.utc)
    if not_before > now or not_after <= now:
        raise ValueError("Certificado fora da validade temporal.")


def rotate_tls(central_dir: Path, backups_dir: Path, host: str, ips: list[str]) -> RotationResult:
    """Generate, validate, back up, and atomically replace Central TLS files."""
    central_dir = central_dir.resolve()
    backups_dir = backups_dir.resolve()
    cert_path = central_dir / "server.crt"
    key_path = central_dir / "server-key.pem"
    if not cert_path.is_file() or not key_path.is_file():
        raise FileNotFoundError("Certificado e chave ativos são obrigatórios para rotação.")
    if not host.strip() or not ips:
        raise ValueError("Hostname e IPv4s explícitos são obrigatórios.")
    for value in ips:
        ipaddress.ip_address(value)

    with tempfile.TemporaryDirectory(prefix="tls-staging-", dir=central_dir) as staging_name:
        staged_cert, staged_key = _certificate(Path(staging_name), host, ips)
        _validate_material(staged_cert, staged_key, host, ips)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_dir = backups_dir / f"tls-{stamp}"
        backup_dir.mkdir(parents=True)
        shutil.copy2(cert_path, backup_dir / cert_path.name)
        shutil.copy2(key_path, backup_dir / key_path.name)
        try:
            staged_cert.replace(cert_path)
            staged_key.replace(key_path)
            _validate_material(cert_path, key_path, host, ips)
        except Exception:
            shutil.copy2(backup_dir / cert_path.name, cert_path)
            shutil.copy2(backup_dir / key_path.name, key_path)
            raise

    return RotationResult(backup_dir, cert_path, key_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rotaciona somente certificado e chave TLS do Central.")
    parser.add_argument("--host", default=socket.gethostname())
    parser.add_argument("--ip", action="append", required=True)
    parser.add_argument("--central-dir", type=Path, default=Path("data/central"))
    parser.add_argument("--backups-dir", type=Path, default=Path("backups"))
    args = parser.parse_args()
    result = rotate_tls(args.central_dir, args.backups_dir, args.host, args.ip)
    print(f"TLS rotacionado. Backup: {result.backup_dir}")


if __name__ == "__main__":
    main()
