"""Adapter HTTP para Terminais que não hospedam o banco central."""

from __future__ import annotations

import ssl
from pathlib import Path
from urllib.parse import urlencode

import httpx


class CentralUnavailable(ConnectionError):
    """Indica que o Terminal não conseguiu alcançar a API central."""


class CentralRejected(ValueError):
    """Indica que a API rejeitou uma operação válida de transporte."""


class CentralClient:
    """Cliente pequeno para a interface central do PDV."""

    def __init__(
        self,
        base_url: str,
        credential: str = "",
        timeout: float | None = None,
        ca_file: str = "",
        connect_timeout: float = 1.5,
        read_timeout: float = 5.0,
        long_read_timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.credential = credential
        self.connect_timeout = connect_timeout
        self.read_timeout = timeout if timeout is not None else read_timeout
        self.long_read_timeout = long_read_timeout
        verify: ssl.SSLContext | bool = ssl.create_default_context(cafile=ca_file) if ca_file else True
        headers = {"Accept": "application/json"}
        if credential:
            headers["Authorization"] = f"Bearer {credential}"
        self._client = httpx.Client(base_url=self.base_url, headers=headers, verify=verify)

    def request(self, method: str, path: str, payload: dict | None = None, *, long_running: bool = False):
        """Send one request through the process-owned connection pool."""
        timeout = httpx.Timeout(
            connect=self.connect_timeout,
            read=self.long_read_timeout if long_running else self.read_timeout,
            write=self.long_read_timeout if long_running else self.read_timeout,
            pool=self.connect_timeout,
        )
        try:
            response = self._client.request(method, path, json=payload, timeout=timeout)
            response.raise_for_status()
            return response.content, response.headers.get("content-type", "").split(";", 1)[0]
        except httpx.HTTPStatusError as error:
            raise CentralRejected(error.response.text) from error
        except httpx.RequestError as error:
            raise CentralUnavailable(str(error)) from error

    _request = request

    def rpc(self, namespace: str, operation: str, *args, **kwargs):
        data, _ = self.request("POST", f"/rpc/{namespace}/{operation}", {"args": args, "kwargs": kwargs})
        return httpx.Response(200, content=data).json()

    def destinations(self) -> list[dict]:
        data, _ = self.request("GET", "/destinations")
        return httpx.Response(200, content=data).json()

    def create_sale(self, payload: dict) -> dict:
        data, _ = self.request("POST", "/sales", payload)
        return httpx.Response(200, content=data).json()

    def download_sales_report(self, params: dict, destination: str | Path) -> Path:
        query = urlencode({key: value for key, value in params.items() if value is not None})
        data, _ = self.request("GET", f"/reports/sales.xlsx?{query}", long_running=True)
        target = Path(destination)
        target.write_bytes(data)
        return target

    def upload(self, path: str, source: str | Path, fields: dict | None = None):
        source = Path(source)
        try:
            timeout = httpx.Timeout(
                connect=self.connect_timeout,
                read=self.long_read_timeout,
                write=self.long_read_timeout,
                pool=self.connect_timeout,
            )
            with source.open("rb") as stream:
                response = self._client.post(
                    path,
                    data=fields or {},
                    files={"file": (source.name, stream, "application/octet-stream")},
                    timeout=timeout,
                )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as error:
            raise CentralRejected(error.response.text) from error
        except httpx.RequestError as error:
            raise CentralUnavailable(str(error)) from error

    def close(self) -> None:
        """Release pooled sockets owned by this client."""
        self._client.close()
