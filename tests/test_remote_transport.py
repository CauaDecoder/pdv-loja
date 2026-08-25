import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.remote import CentralClient, CentralUnavailable


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        self.server.connections.add(id(self.connection))
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length))
        if self.path.endswith("/slow"):
            time.sleep(0.15)
        body = json.dumps({"authorization": self.headers.get("Authorization"), "payload": payload}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        return


@pytest.fixture
def http_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.connections = set()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_client_reuses_connection_and_serializes_authenticated_rpc(http_server):
    client = CentralClient(f"http://127.0.0.1:{http_server.server_port}", "secret")

    first = client.rpc("database", "echo", 1, name="one")
    second = client.rpc("database", "echo", 2, name="two")
    client.close()

    assert first["authorization"] == "Bearer secret"
    assert second["payload"] == {"args": [2], "kwargs": {"name": "two"}}
    assert len(http_server.connections) == 1


def test_report_read_timeout_can_exceed_regular_rpc_timeout(http_server):
    client = CentralClient(
        f"http://127.0.0.1:{http_server.server_port}",
        read_timeout=0.05,
        long_read_timeout=0.5,
    )

    with pytest.raises(CentralUnavailable):
        client.rpc("database", "slow")
    data, _ = client.request("POST", "/rpc/database/slow", {"args": [], "kwargs": {}}, long_running=True)
    client.close()

    assert json.loads(data)["payload"] == {"args": [], "kwargs": {}}
