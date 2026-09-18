#!/usr/bin/env python3
"""Detecta lançamentos duplicados entre dois grupos de categorias.

Uso:
  python3 scripts/check_duplicacao_lancamentos.py --a grupo_a.json --b grupo_b.json

Cada arquivo é um mapa {categoria_id: "Rótulo"}. Dois lançamentos são considerados
duplicados quando casam contato + valor + vencimento + competência. Não altera dados.
"""
import argparse
import os
import sys
import time
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import load_json  # noqa: E402
from bling import BlingClient  # noqa: E402


def key(row):
    return (row["contato"], round(row["valor"], 2), row["vencimento"], row["competencia"])


def main():
    ap = argparse.ArgumentParser(description="Duplicatas de lançamentos entre dois grupos de categorias.")
    ap.add_argument("--a", required=True, help="JSON {categoria_id: rótulo} do grupo A")
    ap.add_argument("--b", required=True, help="JSON {categoria_id: rótulo} do grupo B")
    args = ap.parse_args()

    group_a = {int(k): v for k, v in load_json(args.a).items()}
    group_b = {int(k): v for k, v in load_json(args.b).items()}

    client = BlingClient()
    print("Buscando lançamentos...", flush=True)
    lancamentos = client.paginate("/contas/pagar")
    print(f"Total: {len(lancamentos)}", flush=True)

    rows_a, rows_b = [], []
    for i, l in enumerate(lancamentos, 1):
        status, data = client.request("GET", f"/contas/pagar/{l['id']}")
        if status != 200 or not isinstance(data, dict):
            continue
        d = data["data"]
        cat = (d.get("categoria") or {}).get("id") or 0
        row = {"id": d.get("id"), "categoria": cat, "valor": d.get("valor", 0),
               "vencimento": d.get("vencimento", ""), "competencia": d.get("competencia", ""),
               "contato": (d.get("contato") or {}).get("id", ""),
               "historico": (d.get("historico") or "").strip()}
        if cat in group_a:
            rows_a.append((group_a[cat], row))
        if cat in group_b:
            rows_b.append((group_b[cat], row))
        if i % 100 == 0:
            print(f"  {i}/{len(lancamentos)}", flush=True)
        time.sleep(0.02)

    print(f"\nLançamentos no grupo A: {len(rows_a)} | no grupo B: {len(rows_b)}")

    b_by_key = defaultdict(list)
    for label, row in rows_b:
        b_by_key[key(row)].append((label, row))

    duplicados = [(label, b_by_key[key(row)], row) for label, row in rows_a if key(row) in b_by_key]

    print("=" * 90)
    print("DUPLICAÇÃO: mesmo lançamento nos grupos A e B")
    print("=" * 90)
    print(f"Lançamentos de A com par em B: {len(duplicados)}")
    print(f"Valor total duplicado: {sum(r['valor'] for _, _, r in duplicados):.2f}")
    for label_a, pairs, row in sorted(duplicados, key=lambda x: x[0]):
        for label_b, rb in pairs:
            print(f"  A: {label_a} | id={row['id']} | {row['valor']:.2f} | {row['vencimento']} | contato={row['contato']}")
            print(f"  B: {label_b} | id={rb['id']} | {rb['valor']:.2f} | {rb['vencimento']} | contato={rb['contato']}")
            print(f"     hist A: {row['historico'][:90]}")
            print(f"     hist B: {rb['historico'][:90]}\n")

    a_keys = {key(row) for _, row in rows_a}
    so_a = [(label, row) for label, row in rows_a if key(row) not in b_by_key]
    so_b = [(label, row) for label, row in rows_b if key(row) not in a_keys]
    print("=" * 90)
    print(f"SÓ no grupo A (sem par em B): {len(so_a)} | total {sum(r['valor'] for _, r in so_a):.2f}")
    for label, row in so_a[:20]:
        print(f"  {label} | id={row['id']} | {row['valor']:.2f} | {row['vencimento']} | {row['historico'][:70]}")
    print(f"SÓ no grupo B (sem par em A): {len(so_b)} | total {sum(r['valor'] for _, r in so_b):.2f}")
    for label, row in so_b[:20]:
        print(f"  {label} | id={row['id']} | {row['valor']:.2f} | {row['vencimento']} | {row['historico'][:70]}")


if __name__ == "__main__":
    main()
