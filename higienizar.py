"""Converte a exportação de produtos do Conta Azul para o formato legado."""

from __future__ import annotations

import csv
import re
from pathlib import Path


def higienizar_produtos(entrada: Path, saida: Path) -> None:
    """Higieniza produtos e grava um CSV compatível com o importador legado."""
    with entrada.open(encoding="utf-8") as infile, saida.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as outfile:
        reader = csv.DictReader(infile, delimiter=";")
        writer = csv.DictWriter(
            outfile,
            fieldnames=["codigo", "nome", "preco", "estoque"],
            delimiter=",",
        )
        writer.writeheader()
        produtos_vistos: set[str] = set()

        for row in reader:
            codigo = row.get("Código", "").strip()
            nome = row.get("Nome do Produto", "").strip()
            if not codigo or not nome or nome.upper() in produtos_vistos:
                continue
            produtos_vistos.add(nome.upper())

            preco = re.sub(r"[^\d,]", "", row.get("Valor de Venda", "0"))
            writer.writerow(
                {
                    "codigo": codigo,
                    "nome": nome,
                    "preco": preco.replace(",", ".") or "0.00",
                    "estoque": row.get("Qt. Estoque", "0").strip() or "0",
                }
            )


def main() -> None:
    """Executa a conversão usando os caminhos padrão do projeto."""
    higienizar_produtos(Path("products.csv"), Path("produtos_limpo.csv"))
    print("Higienização concluída! O arquivo 'produtos_limpo.csv' foi gerado.")


if __name__ == "__main__":
    main()
