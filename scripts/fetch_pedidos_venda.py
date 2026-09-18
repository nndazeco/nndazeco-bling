#!/usr/bin/env python3
"""Busca pedidos de venda (lista + detalhe) e grava data/pedidos_venda.json.

Uso: python3 scripts/fetch_pedidos_venda.py
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bling import BlingClient  # noqa: E402

OUT = os.path.join(ROOT, "data", "pedidos_venda.json")


def fetch(client, situacao=0, sleep=0.25):
    """Lista os PVs e busca o detalhe de cada um."""
    pvs = client.paginate("/pedidos/vendas", {"situacao[]": situacao})
    detalhes = []
    for i, pv in enumerate(pvs, 1):
        status, data = client.get(f"/pedidos/vendas/{pv['id']}")
        if status == 200 and isinstance(data, dict):
            detalhes.append(data["data"])
        else:
            print(f"  ! PV {pv.get('id')} -> {status}", flush=True)
        if i % 25 == 0:
            print(f"  detalhes {i}/{len(pvs)}", flush=True)
        time.sleep(sleep)
    return detalhes


def snapshot(det):
    """Reduz o detalhe a um snapshot enxuto (compatível com os relatórios)."""
    c = det.get("contato") or {}
    s = det.get("situacao") or {}
    loja = det.get("loja") or {}
    return {
        "id": det["id"], "numero": det.get("numero"), "numeroLoja": det.get("numeroLoja") or "",
        "data": det.get("data"), "dataSaida": det.get("dataSaida"), "dataPrevista": det.get("dataPrevista"),
        "totalProdutos": det.get("totalProdutos"), "total": det.get("total"),
        "contato": {"id": c.get("id"), "nome": c.get("nome"), "tipoPessoa": c.get("tipoPessoa"),
                    "numeroDocumento": c.get("numeroDocumento") or ""},
        "situacao": {"id": s.get("id"), "valor": s.get("valor")},
        "loja": {"id": loja.get("id"), "unidadeNegocio": {"id": (loja.get("unidadeNegocio") or {}).get("id")}},
        "desconto": det.get("desconto"), "itens": det.get("itens"), "parcelas": det.get("parcelas"),
        "vendedor": det.get("vendedor"), "notaFiscal": det.get("notaFiscal"),
        "categoria": det.get("categoria"),
    }


def main():
    client = BlingClient()
    print("1) PVs (lista + detalhe)...", flush=True)
    detalhes = fetch(client)
    pvs = [snapshot(d) for d in detalhes]

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(pvs, f, ensure_ascii=False, indent=1)
    print(f"gravou {OUT} ({len(pvs)})", flush=True)


if __name__ == "__main__":
    main()
