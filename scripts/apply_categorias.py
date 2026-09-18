#!/usr/bin/env python3
"""Aplica categorias em PVs e CARs conforme um plano JSON. Dry-run por padrão.

Plano (exemplo):
{
  "pvs":          {"2026010": 14734130713},   # altera o PV E as CARs dele
  "pv_only":      {"2026004": 14734130713},   # altera apenas o PV
  "excluir_cars": [26644610113]               # CARs a ignorar na associação
}

Uso: python3 scripts/apply_categorias.py --plan plano.json [--execute]
Backups em backups/backups_categorias_<ts>/.
"""
import argparse
import datetime
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import BACKUPS_DIR, DATA_DIR, associate_cars, load_json, save_json  # noqa: E402
from bling import BlingClient  # noqa: E402


def pv_body(pv, categoria):
    itens = []
    for i in pv.get("itens") or []:
        net = i.get("valor") or 0
        desc = i.get("desconto") or 0
        gross = round(net / (1 - desc / 100), 2) if desc else net
        itens.append({"codigo": i.get("codigo") or "", "descricao": i.get("descricao") or "",
                      "unidade": i.get("unidade") or "UN", "quantidade": i.get("quantidade"),
                      "valor": gross, "desconto": desc,
                      "descricaoDetalhada": i.get("descricaoDetalhada") or "",
                      "produto": {"id": (i.get("produto") or {}).get("id") or 0}})
    parcelas = [{"dataVencimento": x.get("dataVencimento"), "valor": x.get("valor"),
                 "observacoes": x.get("observacoes") or "",
                 "formaPagamento": {"id": (x.get("formaPagamento") or {}).get("id")}}
                for x in pv.get("parcelas") or []]
    body = {"contato": {"id": (pv.get("contato") or {}).get("id")}, "data": pv.get("data"),
            "dataSaida": pv.get("dataSaida"), "dataPrevista": pv.get("dataPrevista"),
            "numero": pv.get("numero"), "numeroLoja": pv.get("numeroLoja") or "",
            "itens": itens, "parcelas": parcelas,
            "desconto": pv.get("desconto") or {"valor": 0, "unidade": "REAL"},
            "observacoes": pv.get("observacoes") or "",
            "observacoesInternas": pv.get("observacoesInternas") or "",
            "numeroPedidoCompra": pv.get("numeroPedidoCompra") or "",
            "outrasDespesas": pv.get("outrasDespesas") or 0,
            "vendedor": {"id": (pv.get("vendedor") or {}).get("id") or 0}, "categoria": {"id": categoria}}
    tr = pv.get("transporte") or {}
    if tr.get("frete") or tr.get("fretePorConta"):
        body["transporte"] = {"fretePorConta": tr.get("fretePorConta", 0), "frete": tr.get("frete", 0),
                              "quantidadeVolumes": tr.get("quantidadeVolumes", 0), "pesoBruto": tr.get("pesoBruto", 0),
                              "prazoEntrega": tr.get("prazoEntrega", 0)}
    return body


def car_body(car, categoria):
    return {"contato": {"id": car["contato"]["id"]}, "dataEmissao": car.get("dataEmissao"),
            "vencimento": car.get("vencimento"), "valor": car.get("valor"),
            "formaPagamento": {"id": (car.get("formaPagamento") or {}).get("id")},
            "categoria": {"id": categoria}, "portador": {"id": (car.get("portador") or {}).get("id") or 0},
            "vendedor": {"id": (car.get("vendedor") or {}).get("id") or 0},
            "numeroDocumento": car.get("numeroDocumento") or "", "historico": car.get("historico") or ""}


def main():
    ap = argparse.ArgumentParser(description="Aplica categorias em PVs/CARs a partir de um plano JSON.")
    ap.add_argument("--plan", required=True, help="plano JSON (pvs/pv_only/excluir_cars)")
    ap.add_argument("--data-dir", default=DATA_DIR, help="diretório dos snapshots")
    ap.add_argument("--execute", action="store_true", help="aplica de fato (default: dry-run)")
    args = ap.parse_args()

    plan = load_json(args.plan)
    pvs_map = {int(k): int(v) for k, v in (plan.get("pvs") or {}).items()}
    pv_only = {int(k): int(v) for k, v in (plan.get("pv_only") or {}).items()}
    excluir = set(plan.get("excluir_cars") or [])

    cars = load_json(os.path.join(args.data_dir, "contas_receber.json"))
    pvs = load_json(os.path.join(args.data_dir, "pedidos_venda.json"))
    pv_by_num, car_ids_by_pv = associate_cars(cars, pvs, excluir=excluir)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = os.path.join(BACKUPS_DIR, f"backups_categorias_{ts}")
    if args.execute:
        os.makedirs(outdir, exist_ok=True)
    client = BlingClient()

    def save(kind, ident, data):
        save_json(os.path.join(outdir, f"{kind}_{ident}.json"), data, indent=1)

    n_pv = n_car = n_skip = 0
    for number, target in pvs_map.items():
        pv_id = pv_by_num[number]["id"]
        status, pv = client.request("GET", f"/pedidos/vendas/{pv_id}")
        if status != 200:
            print("GET PV err", number, status)
            continue
        pv = pv["data"]
        current = (pv.get("categoria") or {}).get("id") or 0
        if args.execute and current != target:
            save("pv", number, pv)
            st, body = client.request("PUT", f"/pedidos/vendas/{pv_id}", body=pv_body(pv, target))
            print(f"PV {number}: cat {current}->{target} PUT {st}")
            n_pv += 1
            time.sleep(0.4)
            if st not in (200, 204):
                print("   ERRO:", body)
                continue
        else:
            print(f"PV {number}: cat {current} (alvo {target}) — {'skip' if current == target else 'dry'}")

        for car_id in car_ids_by_pv.get(number, []):
            status, car = client.request("GET", f"/contas/receber/{car_id}")
            if status != 200:
                print("  GET CAR err", car_id, status)
                continue
            car = car["data"]
            current = (car.get("categoria") or {}).get("id") or 0
            if current == target:
                n_skip += 1
                continue
            if args.execute:
                save("car", car_id, car)
                st, body = client.request("PUT", f"/contas/receber/{car_id}", body=car_body(car, target))
                print(f"  CAR {car_id}: cat {current}->{target} PUT {st}")
                n_car += 1
                time.sleep(0.4)
                if st not in (200, 204):
                    print("   ERRO:", body)
            else:
                print(f"  CAR {car_id}: cat {current}->{target} (dry)")
            time.sleep(0.15)

    for number, target in pv_only.items():
        pv_id = pv_by_num[number]["id"]
        status, pv = client.request("GET", f"/pedidos/vendas/{pv_id}")
        if status != 200:
            print("GET PV err", number, status)
            continue
        pv = pv["data"]
        current = (pv.get("categoria") or {}).get("id") or 0
        if args.execute and current != target:
            save("pv", number, pv)
            st, body = client.request("PUT", f"/pedidos/vendas/{pv_id}", body=pv_body(pv, target))
            print(f"PV {number} (so PV): cat {current}->{target} PUT {st}")
            n_pv += 1
            time.sleep(0.4)
            if st not in (200, 204):
                print("   ERRO:", body)
        else:
            print(f"PV {number} (so PV): cat {current} (alvo {target}) — {'skip' if current == target else 'dry'}")

    print(f"\n{'aplicado' if args.execute else 'dry-run'}: PV {n_pv}, CAR {n_car}, CARs puladas {n_skip}")
    print("backups:", outdir if args.execute else "(nao gravados em dry-run)")


if __name__ == "__main__":
    main()
