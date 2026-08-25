import json
import io
from pathlib import Path

import pytest
from cryptography import x509

from scripts.rotate_central_tls import rotate_tls
from scripts.diagnostico_latencia_terminal import render_report
from scripts.setup_central import _certificate
from scripts.update_terminal_connection import update_connection


HOST = "DESKTOP-IBK9C7I"
IPS = ["192.168.0.106", "192.168.1.112"]


def _sans(cert_path: Path) -> set[tuple[str, str]]:
    certificate = x509.load_pem_x509_certificate(cert_path.read_bytes())
    extension = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    return {
        *(("DNS", value) for value in extension.get_values_for_type(x509.DNSName)),
        *(("IP", str(value)) for value in extension.get_values_for_type(x509.IPAddress)),
    }


def test_certificate_contains_hostname_and_all_explicit_ips(tmp_path):
    cert, _ = _certificate(tmp_path, HOST, IPS)

    assert _sans(cert) == {
        ("DNS", HOST),
        ("IP", "192.168.0.106"),
        ("IP", "192.168.1.112"),
    }


def test_rotate_tls_backs_up_and_replaces_only_tls_material(tmp_path):
    central = tmp_path / "central"
    backups = tmp_path / "backups"
    central.mkdir()
    old_cert, old_key = _certificate(tmp_path / "old", "old-host", ["10.0.0.1"])
    (central / "server.crt").write_bytes(old_cert.read_bytes())
    (central / "server-key.pem").write_bytes(old_key.read_bytes())
    database = central / "loja.db"
    config = central / "server-config.json"
    database.write_bytes(b"database-must-not-change")
    config.write_text('{"port": 8765}', encoding="utf-8")

    result = rotate_tls(central, backups, HOST, IPS)

    assert _sans(central / "server.crt") == {
        ("DNS", HOST),
        ("IP", "192.168.0.106"),
        ("IP", "192.168.1.112"),
    }
    assert database.read_bytes() == b"database-must-not-change"
    assert config.read_text(encoding="utf-8") == '{"port": 8765}'
    assert (result.backup_dir / "server.crt").read_bytes() == old_cert.read_bytes()
    assert (result.backup_dir / "server-key.pem").read_bytes() == old_key.read_bytes()


def test_rotate_tls_restores_old_pair_when_second_replace_fails(tmp_path, monkeypatch):
    central = tmp_path / "central"
    central.mkdir()
    old_cert, old_key = _certificate(tmp_path / "old", "old-host", ["10.0.0.1"])
    active_cert = central / "server.crt"
    active_key = central / "server-key.pem"
    active_cert.write_bytes(old_cert.read_bytes())
    active_key.write_bytes(old_key.read_bytes())
    original_replace = Path.replace

    def fail_key_replace(source, target):
        if source.name == "server-key.pem" and source.parent.name.startswith("tls-staging-"):
            raise OSError("simulated replace failure")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_key_replace)
    with pytest.raises(OSError, match="simulated"):
        rotate_tls(central, tmp_path / "backups", HOST, IPS)

    assert active_cert.read_bytes() == old_cert.read_bytes()
    assert active_key.read_bytes() == old_key.read_bytes()


def test_update_connection_preserves_terminal_identity_and_rejects_wrong_san(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    config_path = data / "terminal-config.json"
    original = {
        "url": "https://old-host:8765",
        "token": "secret-token",
        "ca_cert": "old-ca.crt",
        "permite_offline": True,
        "terminal_id": 7,
        "nome": "Caixa",
    }
    config_path.write_text(json.dumps(original), encoding="utf-8")
    (data / "old-ca.crt").write_text("old certificate", encoding="utf-8")
    cert, _ = _certificate(tmp_path / "new", HOST, IPS)

    backup = update_connection(config_path, "https://192.168.1.112:8765", cert)

    updated = json.loads(config_path.read_text(encoding="utf-8"))
    assert {key: updated[key] for key in ("token", "permite_offline", "terminal_id", "nome")} == {
        key: original[key] for key in ("token", "permite_offline", "terminal_id", "nome")
    }
    assert updated["url"] == "https://192.168.1.112:8765"
    assert updated["ca_cert"] == "central-ca.crt"
    assert (data / "central-ca.crt").read_bytes() == cert.read_bytes()
    assert (backup / "terminal-config.json").exists()
    assert (backup / "old-ca.crt").exists()

    wrong_cert, _ = _certificate(tmp_path / "wrong", HOST, ["192.168.0.106"])
    with pytest.raises(ValueError, match="192.168.1.112"):
        update_connection(config_path, "https://192.168.1.112:8765", wrong_cert)


def test_latency_report_never_renders_token_headers_or_response_data():
    output = io.StringIO()
    render_report(
        {"nome": "Caixa", "url": "https://192.168.1.112:8765", "token": "secret-token"},
        [
            {"stage": "health", "status": 200, "seconds": 0.12, "body": {"product": "sensitive"}},
            {"stage": "rpc", "status": 200, "seconds": 0.25, "authorization": "Bearer secret-token"},
        ],
        output,
    )

    report = output.getvalue()
    assert "Caixa" in report
    assert "192.168.1.112" in report
    assert "secret-token" not in report
    assert "Authorization" not in report
    assert "sensitive" not in report
