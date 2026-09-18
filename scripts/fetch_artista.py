#!/usr/bin/env python3
"""Coleta os dados de um artista (obras, pedidos de venda e contas a pagar).

Uso:
  python3 scripts/fetch_artista.py --nome "Lázaro Roberto" \
      --contato 18220750384 --categoria 14734724294 \
      --codigo-regex '^LRO?[\\-0-9]' --output data/artista_lazaro_roberto.json

Como o artista é identificado (todos opcionais, exceto --nome):
  --nome          nome do artista; vira termos de busca (sem acento, case-insensitive)
                  aplicados a nome de produto, descrição de item e histórico de CAP.
  --contato       id do contato do artista (match exato em CAP).
  --categoria     id de categoria de repasse (repetível; match exato em CAP).
  --codigo-regex  regex para código de produto/item (ex.: '^LR[\\-0-9]').
"""
import argparse
import json
import os
import re
import sys
import time
import unicodedata
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bling import BlingClient  # noqa: E402

DAY = timedelta(days=1)


def normalize(text):
    """Minúsculas e sem acentos, para comparação tolerante."""
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower().strip()


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "_", normalize(text)).strip("_")


def date_blocks(start, end, days=360):
    """Divide [start, end] em janelas (limite de consulta do Bling)."""
    cur = date.fromisoformat(start)
    last = date.fromisoformat(end)
    while cur <= last:
        yield cur.isoformat(), min(cur + timedelta(days=days), last).isoformat()
        cur = cur + timedelta(days=days + 1)


def build_matchers(nome, codigo_regex):
    terms = [t for t in normalize(nome).split() if len(t) >= 3]

    def match_text(text):
        norm = normalize(text)
        return any(term in norm for term in terms)

    code_re = re.compile(codigo_regex) if codigo_regex else None

    def match_code(code):
        return bool(code_re and code_re.search(code or ""))

    return match_text, match_code


def fetch_artista(client, *, nome, contato_id, categorias, codigo_regex, desde, sleep=0.2):
    match_text, match_code = build_matchers(nome, codigo_regex)
    hoje = date.today().isoformat()

    # 1) contato
    contato = {"id": contato_id} if contato_id else {}
    if contato_id:
        status, data = client.get(f"/contatos/{contato_id}")
        if status == 200 and isinstance(data, dict):
            contato = data["data"]

    # 2) produtos (obras)
    produtos = []
    for p in client.paginate("/produtos"):
        if match_code(p.get("codigo")) or match_text(p.get("nome")):
            status, data = client.get(f"/produtos/{p['id']}")
            produtos.append(data["data"] if status == 200 and isinstance(data, dict) else p)
            time.sleep(sleep)
    prod_ids = {p.get("id") for p in produtos}

    # 3) pedidos de venda
    pvs = []
    lista = client.paginate("/pedidos/vendas", {"situacao[]": 0})
    for pv in lista:
        status, data = client.get(f"/pedidos/vendas/{pv['id']}")
        if status != 200 or not isinstance(data, dict):
            continue
        det = data["data"]
        if any(
            match_code(it.get("codigo"))
            or match_text(it.get("descricao"))
            or (it.get("produto") or {}).get("id") in prod_ids
            for it in det.get("itens") or []
        ):
            pvs.append(det)
        time.sleep(sleep)

    # 4) contas a pagar na janela
    categorias = set(categorias or [])
    caps, seen = [], set()
    for ini, fim in date_blocks(desde, hoje):
        for c in client.paginate("/contas/pagar",
                                 {"dataEmissaoInicial": ini, "dataEmissaoFinal": fim}):
            if c["id"] in seen:
                continue
            seen.add(c["id"])
            status, data = client.get(f"/contas/pagar/{c['id']}")
            if status != 200 or not isinstance(data, dict):
                continue
            det = data["data"]
            if (
                (contato_id and (det.get("contato") or {}).get("id") == contato_id)
                or (det.get("categoria") or {}).get("id") in categorias
                or match_text(det.get("historico"))
            ):
                caps.append(det)
            time.sleep(sleep)

    criterio = " OU ".join(filter(None, [
        f"contato=={contato_id}" if contato_id else "",
        f"categoria in {sorted(categorias)}" if categorias else "",
        f"texto~{nome!r}",
    ]))
    return {
        "meta": {
            "nome": nome,
            "contato_id": contato_id,
            "categorias": sorted(categorias),
            "codigo_regex": codigo_regex,
            "janela_cap": [desde, hoje],
            "criterio_cap": criterio,
            "totais": {"produtos": len(produtos), "pedidos_venda": len(pvs), "contas_pagar": len(caps)},
        },
        "contato": contato,
        "produtos": produtos,
        "pedidos_venda": pvs,
        "contas_pagar": caps,
    }


def main():
    ap = argparse.ArgumentParser(description="Coleta dados de um artista no Bling.")
    ap.add_argument("--nome", required=True, help="nome do artista (busca textual)")
    ap.add_argument("--contato", type=int, help="id do contato do artista")
    ap.add_argument("--categoria", type=int, action="append", default=[],
                    help="id de categoria de repasse (repetível)")
    ap.add_argument("--codigo-regex", help="regex para código de produto/item")
    ap.add_argument("--desde", default="2025-01-01", help="início da janela de CAPs (YYYY-MM-DD)")
    ap.add_argument("--output", help="arquivo de saída (default: data/artista_<slug>.json)")
    ap.add_argument("--sleep", type=float, default=0.2, help="pausa entre chamadas (s)")
    args = ap.parse_args()

    saida = args.output or os.path.join(ROOT, "data", f"artista_{slugify(args.nome)}.json")

    client = BlingClient()
    print(f"coletando artista '{args.nome}'...", flush=True)
    snapshot = fetch_artista(
        client, nome=args.nome, contato_id=args.contato, categorias=args.categoria,
        codigo_regex=args.codigo_regex, desde=args.desde, sleep=args.sleep,
    )
    os.makedirs(os.path.dirname(saida), exist_ok=True)
    with open(saida, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=1)
    print("gravou", saida, snapshot["meta"]["totais"], flush=True)


if __name__ == "__main__":
    main()
