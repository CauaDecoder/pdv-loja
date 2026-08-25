"""Executa a API central no computador que hospeda o banco."""

import os

import uvicorn

from app.config import server_config


if __name__ == "__main__":
    config = server_config()
    if config.get("db_path"):
        os.environ["CAIXA_DB_PATH"] = config["db_path"]
    uvicorn.run(
        "app.api:app", host="0.0.0.0", port=int(os.getenv("CAIXA_PORT", config.get("port", 8765))), reload=False,
        ssl_certfile=os.getenv("CAIXA_TLS_CERT") or config.get("tls_cert"),
        ssl_keyfile=os.getenv("CAIXA_TLS_KEY") or config.get("tls_key"),
    )
