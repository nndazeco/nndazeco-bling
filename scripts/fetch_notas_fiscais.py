#!/usr/bin/env python3
"""Extrai o vínculo PV -> Nota Fiscal e grava data/notas_fiscais.json.

A NF já vem embutida no detalhe do PV (campo `notaFiscal`), por isso este
fetcher é offline: consome data/pedidos_venda.json (rode fetch_pedidos_venda.py antes).

Uso: python3 scripts/fetch_notas_fiscais.py [--live]
  --live  reconsulta cada PV na API em vez de usar o snapshot.
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bling import BlingClient  # noqa: E402

PV_FILE = os.path.join(ROOT, "data", "pedidos_venda.json")
OUT = os.path.join(ROOT, "data", "notas_fiscais.json")


def load_pvs():
    with open(PV_FILE, encoding="utf-8") as f:
        return json.load(f)


def fetch_live(pvs, sleep=0.3):
    client = BlingClient()
    rows = []
    for i, pv in enumerate(pvs, 1):
        status, data = client.get(f"/pedidos/vendas/{pv['id']}")
        if status == 200 and isinstance(data, dict):
            det = data["data"]
            nf = (det.get("notaFiscal") or {}).get("id") or 0
            rows.append({"numero": det.get("numero"), "id": pv["id"], "nf": nf,
                         "situacao": (det.get("situacao") or {}).get("id"),
                         "total": det.get("total"),
                         "contato": (det.get("contato") or {}).get("nome")})
        if i % 25 == 0:
            print(f"  {i}/{len(pvs)}", flush=True)
        time.sleep(sleep)
    return rows


def derive(pvs):
    return [{
        "numero": pv.get("numero"), "id": pv["id"],
        "nf": (pv.get("notaFiscal") or {}).get("id") or 0,
        "situacao": (pv.get("situacao") or {}).get("id"),
        "total": pv.get("total"), "contato": (pv.get("contato") or {}).get("nome"),
    } for pv in pvs]


def main():
    live = "--live" in sys.argv
    pvs = load_pvs()
    rows = fetch_live(pvs) if live else derive(pvs)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)

    com_nf = sum(1 for r in rows if r["nf"])
    print(f"gravou {OUT} ({len(rows)} PVs, {com_nf} com NF vinculada)", flush=True)


if __name__ == "__main__":
    main()
