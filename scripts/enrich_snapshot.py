#!/usr/bin/env python3
"""Enriquece um snapshot bruto com mapas de nomes (contatos, categorias,
formas de pagamento, portadores/contas contábeis e vendedores).

Funciona com qualquer snapshot que tenha as listas `contas_pagar` e `pedidos_venda`
(ex.: saída do fetch_artista).

Uso: python3 scripts/enrich_snapshot.py --file data/artista_lazaro_roberto.json
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bling import BlingClient  # noqa: E402


def collect_ids(snapshot):
    contato_ids, cat_ids, port_ids, forma_ids, vend_ids = set(), set(), set(), set(), set()
    for c in snapshot.get("contas_pagar") or []:
        contato_ids.add((c.get("contato") or {}).get("id"))
        cat_ids.add((c.get("categoria") or {}).get("id"))
        port_ids.add((c.get("portador") or {}).get("id"))
        forma_ids.add((c.get("formaPagamento") or {}).get("id"))
    for p in snapshot.get("pedidos_venda") or []:
        contato_ids.add((p.get("contato") or {}).get("id"))
        vend_ids.add((p.get("vendedor") or {}).get("id"))
        for parcela in p.get("parcelas") or []:
            forma_ids.add((parcela.get("formaPagamento") or {}).get("id"))
    for ids in (contato_ids, cat_ids, port_ids, forma_ids, vend_ids):
        ids.discard(0)
        ids.discard(None)
    return contato_ids, cat_ids, port_ids, forma_ids, vend_ids


def build_lookups(client, ids):
    contato_ids, cat_ids, port_ids, forma_ids, vend_ids = ids
    look = {"contatos": {}, "categorias": {}, "formas_pagamento": {}, "portadores": {}, "vendedores": {}}

    for cid in sorted(contato_ids):
        status, data = client.get(f"/contatos/{cid}")
        if status == 200 and isinstance(data, dict):
            c = data["data"]
            look["contatos"][str(cid)] = {"nome": c.get("nome"), "tipo": c.get("tipo"),
                                          "numeroDocumento": c.get("numeroDocumento")}

    for cid in sorted(cat_ids):
        status, data = client.get(f"/categorias/receitas-despesas/{cid}")
        if status == 200 and isinstance(data, dict):
            c = data["data"]
            look["categorias"][str(cid)] = {"descricao": c.get("descricao"),
                                            "situacao": c.get("situacao"), "tipo": c.get("tipo")}

    for f in client.paginate("/formas-pagamentos"):
        look["formas_pagamento"][str(f["id"])] = f.get("descricao")

    for f in client.paginate("/contas-contabeis"):
        look["portadores"][str(f["id"])] = f.get("descricao")

    for v in client.paginate("/vendedores"):
        look["vendedores"][str(v["id"])] = (v.get("contato") or {}).get("nome")

    # mantém só os ids realmente usados (portadores/vendedores vêm de listagem completa)
    look["portadores"] = {k: v for k, v in look["portadores"].items() if int(k) in port_ids}
    look["vendedores"] = {k: v for k, v in look["vendedores"].items() if int(k) in vend_ids}
    return look


def main():
    ap = argparse.ArgumentParser(description="Enriquece um snapshot bruto com lookups de nome.")
    ap.add_argument("--file", required=True, help="snapshot JSON a enriquecer (in-place)")
    args = ap.parse_args()

    with open(args.file, encoding="utf-8") as f:
        snapshot = json.load(f)

    client = BlingClient()
    ids = collect_ids(snapshot)
    print("buscando lookups...", flush=True)
    snapshot["lookups"] = build_lookups(client, ids)

    with open(args.file, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=1)
    print("OK ->", args.file, flush=True)


if __name__ == "__main__":
    main()
