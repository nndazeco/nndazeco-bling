#!/usr/bin/env python3
"""Busca as categorias de receitas/despesas (lista + detalhe com `situacao`).

Grava data/categorias_com_situacao.json. O `situacao` (1 ativa, 0 inativa) só vem no
detalhe (`GET /categorias/receitas-despesas/{id}`), por isso 1 chamada por item.

Uso: python3 scripts/fetch_categorias.py
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bling import BlingClient  # noqa: E402

OUT = os.path.join(ROOT, "data", "categorias_com_situacao.json")


def fetch(client, sleep=0.15):
    """Lista todas as categorias e busca o detalhe (com `situacao`) de cada uma."""
    cat_list = client.paginate("/categorias/receitas-despesas")
    full = []
    total = len(cat_list)
    for i, cat in enumerate(cat_list, 1):
        status, data = client.get(f"/categorias/receitas-despesas/{cat['id']}")
        full.append(data["data"] if status == 200 and isinstance(data, dict) else cat)
        if i % 25 == 0:
            print(f"  {i}/{total}", flush=True)
        time.sleep(sleep)
    return full


def main():
    client = BlingClient()
    print("categorias (lista + detalhe)...", flush=True)
    full = fetch(client)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False)
    ativas = sum(1 for x in full if str(x.get("situacao")) == "1")
    print(f"gravou {OUT} ({len(full)} categorias · {ativas} ativas)", flush=True)


if __name__ == "__main__":
    main()
