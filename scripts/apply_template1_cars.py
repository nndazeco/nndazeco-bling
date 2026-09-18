#!/usr/bin/env python3
"""Aplica o Template 1 (histórico) nas CARs de uma lista de PVs. Dry-run por padrão.

Histórico montado por CAR (template default):
  Ref. ao pedido de venda nº {numero}
  | Obras: {obras}
  | Cliente: {cliente}
  | Valor da venda: {valor}
  | Parcelas: {i}/{n}

Plano (exemplo):
{
  "pvs": [2026001, 2026010, 2026016],
  "cars_manuais": {"20260047": [26870217984, 26870220339]},
  "excluir_regex": "moldura|impress|transporte"
}

Uso: python3 scripts/apply_template1_cars.py --plan plano.json [--execute]
"""
import argparse
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import DATA_DIR, car_put_body, load_json, money  # noqa: E402
from bling import BlingClient  # noqa: E402

DEFAULT_TEMPLATE = (
    "Ref. ao pedido de venda nº {numero}\n"
    "| Obras: {obras}\n"
    "| Cliente: {cliente}\n"
    "| Valor da venda: {valor}\n"
    "| Parcelas: {i}/{n}"
)


def car_ids_for_pv(number, cars, manual_map):
    if str(number) in manual_map:
        return list(manual_map[str(number)])
    return [c["id"] for c in cars
            if (c.get("origem") or {}).get("tipoOrigem") == "venda"
            and str((c.get("origem") or {}).get("numero")) == str(number)]


def main():
    ap = argparse.ArgumentParser(description="Aplica o Template 1 de histórico nas CARs de PVs.")
    ap.add_argument("--plan", required=True, help="plano JSON (pvs/cars_manuais/excluir_regex)")
    ap.add_argument("--data-dir", default=DATA_DIR, help="diretório dos snapshots")
    ap.add_argument("--template", help="arquivo com o template do histórico ({numero},{obras},...)")
    ap.add_argument("--excluir-regex", help="regex p/ excluir descrições de itens das 'Obras'")
    ap.add_argument("--execute", action="store_true", help="aplica de fato (default: dry-run)")
    args = ap.parse_args()

    plan = load_json(args.plan)
    numbers = plan.get("pvs") or []
    manual_map = {str(k): v for k, v in (plan.get("cars_manuais") or {}).items()}
    excluir = re.compile(args.excluir_regex or plan.get("excluir_regex") or r"moldura|impress|transporte", re.I)
    template = open(args.template, encoding="utf-8").read() if args.template else DEFAULT_TEMPLATE

    pvs = load_json(os.path.join(args.data_dir, "pedidos_venda.json"))
    cars = load_json(os.path.join(args.data_dir, "contas_receber.json"))
    pv_by_num = {p["numero"]: p for p in pvs}
    car_by_id = {c["id"]: c for c in cars}

    missing = [n for n in numbers if n not in pv_by_num]
    if missing:
        print("PVs não encontrados no snapshot:", missing, file=sys.stderr)
        return 1

    client = BlingClient()
    total_put = 0
    for number in numbers:
        pv = pv_by_num[number]
        descricoes = [i.get("descricao") or "" for i in pv.get("itens") or []]
        obras = "; ".join(d for d in descricoes if d and not excluir.search(d)) \
            or "; ".join(d for d in descricoes if d)
        cliente = (pv.get("contato") or {}).get("nome") or ""
        total = pv.get("total") or 0

        ids = sorted(car_ids_for_pv(number, cars, manual_map),
                     key=lambda cid: (car_by_id.get(cid, {}).get("vencimento") or ""))
        detalhes = []
        for cid in ids:
            car = car_by_id.get(cid)
            if not car:
                status, data = client.request("GET", f"/contas/receber/{cid}")
                car = data["data"] if status == 200 and isinstance(data, dict) else None
            if car:
                detalhes.append(car)
            time.sleep(0.15)
        detalhes.sort(key=lambda c: c.get("vencimento") or "")
        n = len(detalhes)
        print(f"\n=== PV {number} | {cliente} | {money(total)} | {n} CARs ===")
        print("  Obras:", obras)
        for i, car in enumerate(detalhes, 1):
            historico = template.format(numero=number, obras=obras, cliente=cliente,
                                        valor=money(total), i=i, n=n)
            print(f"  -> CAR {car['id']} ({car.get('vencimento')}) Parcelas {i}/{n}")
            if args.execute:
                st, body = client.request("PUT", f"/contas/receber/{car['id']}", body=car_put_body(car, historico))
                print("     PUT", st if st in (200, 204) else (st, body))
                total_put += 1
                time.sleep(0.5)
    print("\n" + (f"aplicado em {total_put} CARs" if args.execute else "(dry-run; use --execute)"))


if __name__ == "__main__":
    main()
