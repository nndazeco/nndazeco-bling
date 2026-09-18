#!/usr/bin/env python3
"""Relatório de um artista: catálogo de obras + contas a pagar + contas a receber.

O artista é identificado por --contato/--categoria e/ou por --codigo-regex/--nome
(mesmos critérios do fetch_artista). O "a receber" são as CARs das vendas dos PVs
que contêm obras do artista.

Uso:
  python3 scripts/report_artista.py --file data/artista_lazaro_roberto.json \
      --contato 18220750384 --categoria-repasse 14734724294 \
      --categoria-comissao 14735928271 --categoria-comissao 14735928294 \
      --categoria-comissao 14730836888 --codigo-regex '^LRO?[\\-0-9]' \
      --nome "Lázaro" --titulo "Lázaro Roberto" --out report_lazaro_roberto.md
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import DATA_DIR, associate_cars, load_json  # noqa: E402

_ap = argparse.ArgumentParser(description="Relatório de um artista (obras + CAP + CAR).")
_ap.add_argument("--file", required=True, help="snapshot bruto do artista (fetch_artista)")
_ap.add_argument("--contato", type=int, help="id do contato do artista")
_ap.add_argument("--categoria-repasse", type=int, help="categoria de repasse ao artista")
_ap.add_argument("--categoria-comissao", type=int, action="append", default=[],
                 help="categoria de comissão (repetível)")
_ap.add_argument("--codigo-regex", help="regex do código de produto/item (obras do artista)")
_ap.add_argument("--nome", help="termos de busca textual (nome do artista)")
_ap.add_argument("--data-dir", default=DATA_DIR, help="diretório dos snapshots globais (CARs/PVs)")
_ap.add_argument("--titulo", help="título do relatório (default: nome do artista)")
_ap.add_argument("--out", help="arquivo de saída .md")
_ap.add_argument("--notas", help="arquivo .md com observações a anexar no fim")
args = _ap.parse_args()

CAP_SIT = {1: "Aberto", 2: "Pago", 3: "Atrasado", 4: "Recebido", 5: "Baixado"}
PV_SIT = {6: "Em aberto", 9: "Atendido", 12: "Cancelado", 15: "Em andamento"}


def normalize(text):
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower().strip()


def match_text_factory(nome):
    terms = [t for t in normalize(nome).split() if len(t) >= 3] if nome else []
    return lambda text: any(t in normalize(text) for t in terms)


def money(v):
    if v is None:
        return ""
    return "R\\$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def esc(t):
    return (t or "").replace("\r", " ").replace("\n", " / ").replace("|", "\\|").replace("R$", "R\\$")


def clean(t):
    return re.sub(r"\s+", " ", (t or "")).strip()


def obra_ano(nome):
    m = re.search(r",\s*((?:19|20)\d{2}|XXXX)\s*$", nome or "")
    return m.group(1) if m else ""


d = load_json(args.file)
if "lookups" not in d:
    sys.exit("snapshot sem 'lookups' — rode enrich_snapshot.py antes.")
look = d["lookups"]
contatos, cats = look["contatos"], look["categorias"]
formas, vendedores = look.get("formas_pagamento", {}), look.get("vendedores", {})

# nomes de categoria do snapshot global (as CARs vêm de fora do snapshot do artista)
cat_global_path = os.path.join(args.data_dir, "categorias_com_situacao.json")
if os.path.exists(cat_global_path):
    def _walk(o):
        if isinstance(o, dict):
            if o.get("id") and o.get("descricao"):
                cats.setdefault(str(o["id"]), {"descricao": o["descricao"]})
            for v in o.values():
                _walk(v)
        elif isinstance(o, list):
            for v in o:
                _walk(v)
    _walk(load_json(cat_global_path))

cat_name = lambda cid: (cats.get(str(cid)) or {}).get("descricao") or ("(sem categoria)" if not cid else f"(id {cid})")
nome = lambda cid: (contatos.get(str(cid)) or {}).get("nome") or f"(id {cid})"
forma = lambda fid: formas.get(str(fid), "") or ""
val_name = lambda vid: vendedores.get(str(vid)) or ""
pv_sit = lambda sid: PV_SIT.get(sid, str(sid))
cap_sit = lambda s: CAP_SIT.get(s, str(s))

# ---------- matchers do artista ----------
code_re = re.compile(args.codigo_regex) if args.codigo_regex else None
match_text = match_text_factory(args.nome)


def is_artista_item(it, prod_ids):
    return (
        bool(code_re and code_re.search(it.get("codigo") or ""))
        or match_text(it.get("descricao"))
        or (it.get("produto") or {}).get("id") in prod_ids
    )


classify = lambda c: (
    "repasse" if (c.get("categoria") or {}).get("id") == args.categoria_repasse
    else "comissao" if (c.get("categoria") or {}).get("id") in set(args.categoria_comissao)
    else "despesa"
)

# ---------- dados do snapshot ----------
produtos = sorted(d.get("produtos") or [], key=lambda p: p.get("codigo") or "")
prod_ids = {p.get("id") for p in produtos}
pvs = sorted(d.get("pedidos_venda") or [], key=lambda p: p.get("data") or "")
caps = d.get("contas_pagar") or []
artist_pv_nums = {int(p.get("numero") or 0) for p in pvs}

# ---------- contas a receber (das vendas do artista) ----------
cars_global = load_json(os.path.join(args.data_dir, "contas_receber.json"))
pvs_global = load_json(os.path.join(args.data_dir, "pedidos_venda.json"))
_, car_ids_by_pv = associate_cars(cars_global, pvs_global)
car_by_id = {c["id"]: c for c in cars_global}
cars = []
for num in artist_pv_nums:
    for cid in car_ids_by_pv.get(num, []):
        car = car_by_id.get(cid)
        if car:
            cars.append((num, car))
cars.sort(key=lambda x: x[1].get("vencimento") or "")

by_class = defaultdict(list)
for c in caps:
    by_class[classify(c)].append(c)
total_cap = sum(c.get("valor") or 0 for c in caps)
pago_cap = sum(c.get("valor") or 0 for c in caps if c.get("situacao") == 2)
total_car = sum(c.get("valor") or 0 for _, c in cars)
rec_car = sum(c.get("valor") or 0 for _, c in cars if c.get("situacao") == 2)
soma_obras = sum(p.get("preco") or 0 for p in produtos)

titulo = args.titulo or args.nome or "Artista"
L = []
A = L.append

# ---------- cabeçalho / resumo ----------
A(f"# Relatório — {titulo}")
A("")
if args.contato:
    A(f"**Contato/fornecedor:** {nome(args.contato)} (`id {args.contato}`)  ")
A(f"**Gerado em:** {d.get('meta', {}).get('gerado_em', '')}  ")
janela = (d.get("meta") or {}).get("janela_cap") or []
if janela:
    A("**Janela CAP:** " + " a ".join(janela) + "  ")
A("")
A("## Resumo")
A("")
A("| Bloco | Qtd | Valor |")
A("|---|---:|---:|")
A(f"| Obras (catálogo) | {len(produtos)} | preço de tabela {money(soma_obras)} |")
A(f"| Contas a receber (vendas) | {len(cars)} | {money(total_car)} (recebido {money(rec_car)} / aberto {money(total_car - rec_car)}) |")
A(f"| Contas a pagar | {len(caps)} | {money(total_cap)} (pago {money(pago_cap)} / aberto {money(total_cap - pago_cap)}) |")
A("")
A(f"> Contas a pagar por natureza: **repasse** {len(by_class['repasse'])} · "
  f"**comissões** {len(by_class['comissao'])} · **despesas** {len(by_class['despesa'])}.")
A("")

# ---------- 1. catálogo de obras ----------
A("---")
A("")
A("## 1. Catálogo de obras")
A("")
A("| Código | Obra | Ano | Técnica | Dimensões (cm) | Preço de tabela | Situação | Estoque |")
A("|---|---|---|---|---|---:|---|---:|")
for p in produtos:
    est = (p.get("estoque") or {}).get("saldoVirtualTotal")
    dim = p.get("dimensoes") or {}
    larg, alt, prof = dim.get("largura") or 0, dim.get("altura") or 0, dim.get("profundidade") or 0
    tam = f"{larg:g} × {alt:g}" + (f" × {prof:g}" if prof else "")
    tech = clean(re.sub(r"<[^>]+>", " ", p.get("descricaoCurta") or ""))
    A(f"| `{p.get('codigo')}` | {esc(clean(p.get('nome')))} | {obra_ano(p.get('nome'))} | {esc(tech) or '—'} | "
      f"{tam if (larg or alt) else '—'} | {money(p.get('preco'))} | {p.get('situacao')} | {est} |")
A("")
A(f"**Total de preço de tabela:** {money(soma_obras)} · **{len(produtos)} obras**.")
A("")

# ---------- 2. contas a receber ----------
A("---")
A("")
A("## 2. Contas a receber (vendas das obras)")
A("")
if cars:
    A("| CAR | PV | Cliente | Vencimento | Valor | Situação | Categoria | Forma | Histórico |")
    A("|---|---|---|---|---:|---|---|---|---|")
    for num, c in cars:
        A(f"| `{c['id']}` | {num} | {esc((c.get('contato') or {}).get('nome')) or '—'} | {c.get('vencimento')} | "
          f"{money(c.get('valor'))} | {cap_sit(c.get('situacao'))} | {esc(cat_name((c.get('categoria') or {}).get('id')))} | "
          f"{forma((c.get('formaPagamento') or {}).get('id'))} | {esc(clean(c.get('historico')))[:110]} |")
    A("")
    A(f"**Subtotal:** {money(total_car)} · recebido {money(rec_car)} · aberto {money(total_car - rec_car)} ({len(cars)} títulos).")
else:
    A("_Nenhuma conta a receber associada às vendas do artista._")
A("")

# ---------- 3. contas a pagar ----------
A("---")
A("")
A("## 3. Contas a pagar")
A("")


def pv_ref(hist):
    if not hist:
        return None
    for m in re.finditer(r"(?<!\d)(20\d{5,6})(?!\d)", hist):
        n = int(m.group(1))
        if n in artist_pv_nums:
            return n
    return None


def cap_table(itens, titulo_secao, subtitulo):
    A(f"### {titulo_secao}")
    A("")
    if subtitulo:
        A(subtitulo)
        A("")
    if not itens:
        A("_Nenhum._")
        A("")
        return
    A("| CAP | Emissão | Venc. | Valor | Situação | Categoria | Beneficiário | PV | Histórico |")
    A("|---|---|---|---:|---|---|---|---|---|")
    tot = pago = 0.0
    for c in sorted(itens, key=lambda x: x.get("dataEmissao") or ""):
        val = c.get("valor") or 0
        tot += val
        if c.get("situacao") == 2:
            pago += val
        ref = pv_ref(c.get("historico"))
        A(f"| `{c['id']}` | {c.get('dataEmissao')} | {c.get('vencimento')} | {money(val)} | {cap_sit(c.get('situacao'))} | "
          f"{esc(cat_name((c.get('categoria') or {}).get('id')))} | {esc(nome((c.get('contato') or {}).get('id')))} | "
          f"{ref if ref else '—'} | {esc(clean(c.get('historico')))[:120]} |")
    A("")
    A(f"**Subtotal:** {money(tot)} · pago {money(pago)} · aberto {money(tot - pago)} ({len(itens)} lançamentos).")
    A("")


cap_table(by_class["repasse"], "3.1 Repasses ao artista", "Pagamentos de repasse (venda em consignação).")
cap_table(by_class["comissao"], "3.2 Comissões de venda", "Comissões de vendedores sobre as vendas do artista.")
cap_table(by_class["despesa"], "3.3 Despesas e reembolsos", "Custos de produção, moldura, transporte e afins.")

# ---------- 4. cross-reference PV x repasse ----------
A("---")
A("")
A("## 4. Pedidos de venda × repasse")
A("")
A("| PV | Data | Cliente | Situação PV | Repasses (CAPs) | Repasse pago | Repasse aberto |")
A("|---|---|---|---|---|---:|---:|")
for pv in pvs:
    num = pv.get("numero")
    reps = [c for c in by_class["repasse"] if pv_ref(c.get("historico")) == num]
    ids = ", ".join(f"`{c['id']}`" for c in reps) or "—"
    pago = sum(c.get("valor") or 0 for c in reps if c.get("situacao") == 2)
    aberto = sum(c.get("valor") or 0 for c in reps if c.get("situacao") != 2)
    A(f"| {num} | {pv.get('data')} | {esc((pv.get('contato') or {}).get('nome'))} | "
      f"{pv_sit((pv.get('situacao') or {}).get('id'))} | {ids} | {money(pago)} | {money(aberto)} |")
A("")

# ---------- notas opcionais ----------
if args.notas and os.path.exists(args.notas):
    A("---")
    A("")
    A("## Observações")
    A("")
    A(open(args.notas, encoding="utf-8").read().rstrip())
    A("")

out = args.out or os.path.join(ROOT, f"report_{normalize(titulo).replace(' ', '_')}.md")
with open(out, "w", encoding="utf-8") as f:
    f.write("\n".join(L) + "\n")
print("gravou", out, f"({len(L)} linhas)")
