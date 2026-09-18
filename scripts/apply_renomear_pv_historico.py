#!/usr/bin/env python3
"""Reescreve a numeração antiga de PV no histórico de CARs. Dry-run por padrão.

Troca o número citado após "nº" (ex.: `Ref. ao pedido de venda nº 4`) pelo número atual
do PV. Sem `--cars`, age em todas as CARs do snapshot cujo histórico cite um número do mapa.

Se o PUT da CAR falhar com erro 84 (forma de pagamento inativa), reativa a forma
temporariamente, refaz o PUT e restaura a situação da forma (ver `specs/api-docs/api-baixas.md`).

Mapa (exemplo):
{ "4": 2026003, "6": 2026005, "7": 2026008, "11": 2026011, "12": 2026012 }

Uso: python3 scripts/apply_renomear_pv_historico.py --map mapa.json [--cars 123,456] [--execute]
"""
import argparse
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import DATA_DIR, car_put_body, load_json  # noqa: E402
from bling import BlingClient  # noqa: E402

NUM_RE = re.compile(r"(n[ºo°]\.?\s*)(\d+)(?!\d)", re.I)


def rename(historico, mapa):
    """Troca o número após "nº" quando ele está no mapa. Retorna (novo, mudou)."""
    changed = False

    def repl(m):
        nonlocal changed
        novo = mapa.get(m.group(2))
        if novo is None or str(novo) == m.group(2):
            return m.group(0)
        changed = True
        return f"{m.group(1)}{novo}"

    return NUM_RE.sub(repl, historico or ""), changed


def erro_84(body):
    fields = ((body or {}).get("error") or {}).get("fields") or []
    return any(f.get("code") == 84 for f in fields)


def set_forma_situacao(client, fid, situacao):
    _, d = client.get(f"/formas-pagamentos/{fid}")
    body = dict(d["data"])
    body["situacao"] = situacao
    body.pop("id", None)
    return client.request("PUT", f"/formas-pagamentos/{fid}", body=body)


def put_car(client, car, historico):
    """PUT da CAR; se erro 84, reativa a forma, refaz e restaura a situação."""
    path = f"/contas/receber/{car['id']}"
    st, body = client.request("PUT", path, body=car_put_body(car, historico))
    if st == 400 and erro_84(body):
        fid = (car.get("formaPagamento") or {}).get("id")
        _, d = client.get(f"/formas-pagamentos/{fid}")
        orig = d["data"].get("situacao")
        set_forma_situacao(client, fid, 1)
        time.sleep(0.4)
        try:
            st, body = client.request("PUT", path, body=car_put_body(car, historico))
        finally:
            set_forma_situacao(client, fid, orig)
            time.sleep(0.4)
    return st, body


def main():
    ap = argparse.ArgumentParser(description="Renomeia a numeração antiga de PV no histórico de CARs.")
    ap.add_argument("--map", required=True, help="JSON {numero_antigo: numero_novo}")
    ap.add_argument("--cars", help="ids de CAR (csv); default: todas do snapshot que casem o mapa")
    ap.add_argument("--data-dir", default=DATA_DIR, help="diretório dos snapshots")
    ap.add_argument("--execute", action="store_true", help="aplica de fato (default: dry-run)")
    args = ap.parse_args()

    mapa = {str(k): v for k, v in load_json(args.map).items()}
    cars = load_json(os.path.join(args.data_dir, "contas_receber.json"))
    car_by_id = {str(c["id"]): c for c in cars}

    if args.cars:
        ids = [s.strip() for s in args.cars.split(",") if s.strip()]
    else:
        ids = [str(c["id"]) for c in cars if rename(c.get("historico"), mapa)[1]]

    client = BlingClient() if args.execute else None
    n = 0
    for cid in ids:
        if args.execute:
            st, data = client.request("GET", f"/contas/receber/{cid}")
            car = data["data"] if st == 200 and isinstance(data, dict) else None
        else:
            car = car_by_id.get(cid)
        if not car:
            print(f"  CAR {cid}: não encontrada", file=sys.stderr)
            continue
        novo, mudou = rename(car.get("historico"), mapa)
        if not mudou:
            continue
        n += 1
        print(f"\nCAR {cid} (venc. {car.get('vencimento')})")
        print(f"  antes: {car.get('historico')!r}")
        print(f"  depois: {novo!r}")
        if args.execute:
            st, body = put_car(client, car, novo)
            print("  PUT", st if st in (200, 204) else (st, body))
            time.sleep(0.5)

    print("\n" + (f"aplicado em {n} CARs" if args.execute else f"{n} CARs a alterar (dry-run; use --execute)"))


if __name__ == "__main__":
    main()
