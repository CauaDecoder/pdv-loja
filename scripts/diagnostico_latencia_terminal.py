"""Measure Terminal transport stages without exposing credentials or business data."""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import statistics
import sys
import time
from pathlib import Path
from typing import TextIO
from urllib.parse import urlparse, urlunparse

import httpx


def collect_samples(config: dict, repetitions: int) -> list[dict]:
    """Colete medições sanitizadas, preservando falhas como resultados."""
    parsed = urlparse(config["url"])
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Diagnóstico exige URL HTTPS válida.")
    ca_file = Path(config["ca_cert"])
    if not ca_file.is_absolute() and config.get("config_dir"):
        ca_file = Path(config["config_dir"]) / ca_file
    port = parsed.port or 443
    samples: list[dict] = []
    for _ in range(repetitions):
        started = time.perf_counter()
        try:
            addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
            status = "ok"
        except OSError as error:
            addresses = []
            status = type(error).__name__
        samples.append({"stage": "dns", "status": status, "seconds": time.perf_counter() - started})

        started = time.perf_counter()
        try:
            family, socktype, proto, _, address = addresses[0]
            with socket.socket(family, socktype, proto) as raw:
                raw.settimeout(2.0)
                raw.connect(address)
            status = "ok"
        except (OSError, IndexError) as error:
            status = type(error).__name__
        samples.append({"stage": "tcp", "status": status, "seconds": time.perf_counter() - started})

        context = ssl.create_default_context(cafile=str(ca_file))
        started = time.perf_counter()
        try:
            with socket.create_connection((parsed.hostname, port), timeout=2.0) as raw:
                with context.wrap_socket(raw, server_hostname=parsed.hostname):
                    pass
            status = "ok"
        except (OSError, ssl.SSLError) as error:
            status = type(error).__name__
        samples.append({"stage": "tls", "status": status, "seconds": time.perf_counter() - started})

        headers = {"Authorization": f"Bearer {config['token']}"} if config.get("token") else {}
        timeout = httpx.Timeout(connect=2.0, read=10.0, write=10.0, pool=2.0)
        with httpx.Client(base_url=config["url"], verify=context, headers=headers, timeout=timeout) as client:
            for stage, method, path, payload in (
                ("health", "GET", "/health", None),
                ("rpc", "POST", "/rpc/database/configuracoes", {"args": [], "kwargs": {}}),
            ):
                started = time.perf_counter()
                try:
                    response = client.request(method, path, json=payload)
                    status = response.status_code
                except httpx.RequestError as error:
                    status = type(error).__name__
                samples.append({"stage": stage, "status": status, "seconds": time.perf_counter() - started})
    return samples


def render_report(config: dict, samples: list[dict], output: TextIO = sys.stdout) -> None:
    """Render only shareable transport metadata and aggregate timings."""
    parsed = urlparse(config.get("url", ""))
    print(f"Terminal: {config.get('nome', 'não identificado')}", file=output)
    print(f"Destino: {parsed.hostname or 'inválido'}:{parsed.port or 443}", file=output)
    for sample in samples:
        print(
            f"etapa={sample.get('stage')} status={sample.get('status')} tempo_ms={sample.get('seconds', 0) * 1000:.1f}",
            file=output,
        )
    for stage in sorted({sample.get("stage") for sample in samples}):
        durations = [sample["seconds"] * 1000 for sample in samples if sample.get("stage") == stage]
        print(
            f"resumo={stage} mediana_ms={statistics.median(durations):.1f} pior_ms={max(durations):.1f}",
            file=output,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnóstico sanitizado de latência do Terminal.")
    parser.add_argument("--repeticoes", type=int, default=3)
    parser.add_argument("--config", type=Path, default=Path("data/terminal-config.json"))
    parser.add_argument("--destino", action="append", help="Hostname ou IP alternativo para comparação")
    args = parser.parse_args()
    if args.repeticoes < 1:
        raise SystemExit("repetições deve ser maior que zero")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    config["config_dir"] = str(args.config.resolve().parent)
    destinations = args.destino or [urlparse(config["url"]).hostname]
    for destination in destinations:
        parsed = urlparse(config["url"])
        target = dict(config)
        target["url"] = urlunparse(parsed._replace(netloc=f"{destination}:{parsed.port or 443}"))
        render_report(target, collect_samples(target, args.repeticoes))


if __name__ == "__main__":
    main()
