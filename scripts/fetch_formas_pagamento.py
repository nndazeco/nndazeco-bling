#!/usr/bin/env python3
"""Busca as formas de pagamento (lista + detalhe com `destino`) em data/formas_pagamento.json.

O campo `destino` só vem no detalhe (`GET /formas-pagamentos/{id}`), por isso 1 chamada por
item. Use este snapshot para saber quais formas estão ativas e quais geram CAR/CAP
(`destino`=1) — em vez de hardcodar ids nas docs.

Uso: python3 scripts/fetch_formas_pagamento.py
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bling import BlingClient  # noqa: E402

OUT = os.path.join(ROOT, "data", "formas_pagamento.json")


def fetch(client, sleep=0.2):
    """Lista todas as formas e busca o detalhe (com `destino`) de cada uma."""
    forma_list = client.paginate("/formas-pagamentos")
    full = []
    total = len(forma_list)
    for i, forma in enumerate(forma_list, 1):
        status, data = client.get(f"/formas-pagamentos/{forma['id']}")
        full.append(data["data"] if status == 200 and isinstance(data, dict) else forma)
        if i % 25 == 0:
            print(f"  {i}/{total}", flush=True)
        time.sleep(sleep)
    return full


def main():
    client = BlingClient()
    print("formas de pagamento (lista + detalhe)...", flush=True)
    full = fetch(client)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False)
    ativas = sum(1 for x in full if str(x.get("situacao")) == "1")
    geram_car = sum(1 for x in full if str(x.get("destino")) == "1")
    print(f"gravou {OUT} ({len(full)} formas · {ativas} ativas · {geram_car} geram CAR)", flush=True)


if __name__ == "__main__":
    main()
