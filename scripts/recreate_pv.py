#!/usr/bin/env python3
"""Recria um Pedido de Venda preservando dados: GET (backup) -> DELETE -> POST (numero fixo) -> lancar-contas.

Uso:
  python3 scripts/recreate_pv.py --backup backups/backups_recreate_<ts>/pv_2026028.json --vendedor 15596924706     # dry-run
  python3 scripts/recreate_pv.py --backup ... --vendedor 15596924706 --execute

Regras:
  - forma de pagamento de TODAS as parcelas remapeada para --forma (default 10378288 Pix Santander, destino=1).
  - situacao nao e enviada (API nao permite; recria como 6 Em aberto).
  - vendedor: id do vendedor a atribuir (default: mantem o do backup).
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bling import BlingClient  # noqa: E402

DIR = ROOT
DEFAULT_FORMA = 10378288

_client = None


def api(method, path, body=None):
    global _client
    if _client is None:
        _client = BlingClient()
    return _client.request(method, path, body=body)


def build_body(pv, forma_id, vendedor_id):
    # ATENCAO: no GET, item.valor e o valor LIQUIDO e item.desconto e o PERCENTUAL aplicado.
    # No POST, item.valor deve ser o valor BRUTO (lista) e item.desconto o PERCENTUAL.
    itens = []
    for i in pv.get("itens") or []:
        net = i.get("valor") or 0
        d = i.get("desconto") or 0
        gross = round(net / (1 - d / 100), 2) if d else net
        itens.append({
            "codigo": i.get("codigo") or "",
            "descricao": i.get("descricao") or "",
            "unidade": i.get("unidade") or "UN",
            "quantidade": i.get("quantidade"),
            "valor": gross,
            "desconto": d,
            "descricaoDetalhada": i.get("descricaoDetalhada") or "",
            "produto": {"id": (i.get("produto") or {}).get("id") or 0},
        })
    parcelas = []
    for x in pv.get("parcelas") or []:
        parcelas.append({
            "dataVencimento": x.get("dataVencimento"),
            "valor": x.get("valor"),
            "observacoes": x.get("observacoes") or "",
            "formaPagamento": {"id": forma_id},
        })
    body = {
        "contato": {"id": (pv.get("contato") or {}).get("id")},
        "data": pv.get("data"),
        "numero": pv.get("numero"),
        "numeroLoja": pv.get("numeroLoja") or "",
        "itens": itens,
        "parcelas": parcelas,
        "desconto": pv.get("desconto") or {"valor": 0, "unidade": "REAL"},
        "observacoes": pv.get("observacoes") or "",
        "observacoesInternas": pv.get("observacoesInternas") or "",
        "numeroPedidoCompra": pv.get("numeroPedidoCompra") or "",
        "outrasDespesas": pv.get("outrasDespesas") or 0,
        "vendedor": {"id": vendedor_id if vendedor_id is not None else (pv.get("vendedor") or {}).get("id") or 0},
    }
    cat = (pv.get("categoria") or {}).get("id")
    if cat:
        body["categoria"] = {"id": cat}
    tr = pv.get("transporte") or {}
    if tr.get("frete") or tr.get("fretePorConta"):
        body["transporte"] = {
            "fretePorConta": tr.get("fretePorConta", 0),
            "frete": tr.get("frete", 0),
            "quantidadeVolumes": tr.get("quantidadeVolumes", 0),
            "pesoBruto": tr.get("pesoBruto", 0),
            "prazoEntrega": tr.get("prazoEntrega", 0),
        }
    return body


def calc_total(body):
    prod = 0.0
    for i in body["itens"]:
        net = (i["valor"] or 0) * (1 - (i["desconto"] or 0) / 100)
        prod += net * (i["quantidade"] or 1)
    desc = (body.get("desconto") or {}).get("valor") or 0
    frete = (body.get("transporte") or {}).get("frete") or 0
    return round(prod - desc + frete, 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backup", required=True)
    ap.add_argument("--vendedor", type=int, default=None)
    ap.add_argument("--forma", type=int, default=DEFAULT_FORMA)
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    with open(args.backup, encoding="utf-8") as f:
        raw = json.load(f)
    pv = raw.get("data", raw)
    body = build_body(pv, args.forma, args.vendedor)
    total_calc = calc_total(body)
    print(f"PV {pv.get('numero')} id {pv.get('id')} | total original {pv.get('total')} | total calculado {total_calc}")
    print(json.dumps(body, ensure_ascii=False, indent=1))
    if abs((pv.get("total") or 0) - total_calc) > 0.02:
        print("!!! DIVERGENCIA de total — abortando")
        return
    if not args.execute:
        print("(dry-run; use --execute para aplicar)")
        return

    old_id = pv["id"]
    s, b = api("DELETE", f"/pedidos/vendas/{old_id}")
    print("DELETE", old_id, "->", s)
    if s not in (200, 204):
        print("abortando:", b); return
    s, b = api("POST", "/pedidos/vendas", body)
    print("POST ->", s, json.dumps(b, ensure_ascii=False)[:300] if isinstance(b, dict) else b)
    if s not in (200, 201):
        print("abortando"); return
    new_id = b["data"]["id"]
    s, b = api("POST", f"/pedidos/vendas/{new_id}/lancar-contas")
    print("lancar-contas", new_id, "->", s)
    time.sleep(1)
    s, b = api("GET", f"/pedidos/vendas/{new_id}")
    pv2 = b.get("data", {})
    print("NOVO id", new_id, "numero", pv2.get("numero"), "situacao", (pv2.get("situacao") or {}).get("id"),
          "total", pv2.get("total"), "vendedor", (pv2.get("vendedor") or {}).get("id"),
          "NF", (pv2.get("notaFiscal") or {}).get("id"))


if __name__ == "__main__":
    main()
