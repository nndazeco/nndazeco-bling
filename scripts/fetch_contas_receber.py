#!/usr/bin/env python3
"""Busca contas a receber (lista + detalhe) e grava data/contas_receber.json.

Uso: python3 scripts/fetch_contas_receber.py
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bling import BlingClient  # noqa: E402

OUT = os.path.join(ROOT, "data", "contas_receber.json")
SITUACOES = (1, 2)  # Aberto, Pago


def fetch(client, situacoes=SITUACOES, sleep=0.2):
    """Lista as CARs por situação e busca o detalhe de cada uma."""
    car_list = []
    for sit in situacoes:
        car_list.extend(client.paginate("/contas/receber", {"situacoes[]": sit}))
        time.sleep(0.4)

    full = []
    total = len(car_list)
    for i, car in enumerate(car_list, 1):
        status, data = client.get(f"/contas/receber/{car['id']}")
        if status == 200 and isinstance(data, dict):
            full.append(data["data"])
        else:
            full.append(car)
        if i % 25 == 0:
            print(f"  {i}/{total}", flush=True)
        time.sleep(sleep)
    return full


def main():
    client = BlingClient()
    print("CARs (lista + detalhe)...", flush=True)
    full = fetch(client)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False)
    print(f"gravou {OUT} ({len(full)})", flush=True)


if __name__ == "__main__":
    main()
