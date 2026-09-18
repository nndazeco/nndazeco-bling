#!/usr/bin/env python3
"""Lista Contas a Pagar de um ou mais grupos de categorias.

Uso:
  python3 scripts/check_lancamentos_artistas.py --grupos grupos.json
  python3 scripts/check_lancamentos_artistas.py --categoria 14735928273 --categoria 14735928285

`grupos.json` é um mapa {categoria_id: "Rótulo"}. `--categoria` (repetível) usa o id como rótulo.
Imprime os lançamentos agrupados pela categoria. Não altera dados.
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

SIT = {1: "Aberto", 2: "Pago", 3: "Vencido"}


def build_groups(args):
    groups = {}
    if args.grupos:
        groups.update({int(k): v for k, v in load_json(args.grupos).items()})
    for cid in args.categoria or []:
        groups.setdefault(cid, str(cid))
    return groups


def main():
    ap = argparse.ArgumentParser(description="Lista CAPs de grupos de categorias.")
    ap.add_argument("--grupos", help="JSON {categoria_id: rótulo}")
    ap.add_argument("--categoria", type=int, action="append", help="id de categoria (repetível)")
    args = ap.parse_args()

    groups = build_groups(args)
    if not groups:
        ap.error("informe --grupos e/ou --categoria")

    client = BlingClient()
    print("Buscando contas a pagar...", flush=True)
    lancamentos = client.paginate("/contas/pagar")
    print(f"Total de lançamentos: {len(lancamentos)}", flush=True)

    encontrados = []
    for i, l in enumerate(lancamentos, 1):
        status, data = client.request("GET", f"/contas/pagar/{l['id']}")
        if status == 200 and isinstance(data, dict):
            det = data["data"]
            cat_id = (det.get("categoria") or {}).get("id") or 0
            if cat_id in groups:
                encontrados.append({
                    "id": det["id"], "categoria": groups[cat_id], "categoriaId": cat_id,
                    "vencimento": det.get("vencimento", ""), "valor": det.get("valor", 0),
                    "competencia": det.get("competencia", ""),
                    "historico": (det.get("historico") or "")[:100],
                    "contato": (det.get("contato") or {}).get("id", ""),
                    "situacao": det.get("situacao", ""),
                })
        if i % 100 == 0:
            print(f"  {i}/{len(lancamentos)}", flush=True)
        time.sleep(0.02)

    print("\n" + "=" * 90)
    print(f"LANÇAMENTOS NOS GRUPOS INFORMADOS: {len(encontrados)}")
    print("=" * 90)
    por_cat = defaultdict(lambda: {"n": 0, "valor": 0})
    total = 0
    for e in encontrados:
        por_cat[e["categoria"]]["n"] += 1
        por_cat[e["categoria"]]["valor"] += e["valor"]
        total += e["valor"]

    for cat, s in sorted(por_cat.items()):
        print(f"\n  [{cat}]  {s['n']} lançamento(s) | {s['valor']:.2f}")
        for e in [x for x in encontrados if x["categoria"] == cat]:
            sit = SIT.get(e["situacao"], e["situacao"])
            print(f"     id={e['id']} | {e['vencimento']} | {e['valor']:.2f} | {sit} | "
                  f"contato={e['contato']} | {e['historico'][:70]}")

    print(f"\nTOTAL GERAL: {len(encontrados)} lançamentos | {total:.2f}")


if __name__ == "__main__":
    main()
