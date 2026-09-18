#!/usr/bin/env python3
"""Gera report_cars_por_pv.md e report_cars_sem_pv.md a partir de snapshots ao vivo.

Fontes:
  data/pedidos_venda.json      (detalhado: itens, parcelas, desconto, NF, situacao)
  data/contas_receber.json     (CARs com detalhe)
  data/notas_fiscais.json      (PV -> nf id)

Associação CAR→PV:
  - tipoOrigem 'venda'  -> origem.numero
  - tipoOrigem 'notafiscal' -> seção NF (sem PV)
  - manual: busca no historico pelo numero de PV atual (20NNNNN/20NNNNNN).
    Sem match -> "sem PV".

Grupos:
  1 Acima, 2 Abaixo, 3 Duplicação exata (~2x), 4 Cobre via manual,
  5 Ideal, 6 PVs sem CAR.
"""
import argparse
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import DATA_DIR  # noqa: E402

_ap = argparse.ArgumentParser(description="Gera os relatórios de CARs por PV / sem PV.")
_ap.add_argument("--data-dir", default=DATA_DIR, help="diretório dos snapshots")
_ap.add_argument("--out-dir", default=ROOT, help="diretório de saída dos relatórios")
_ap.add_argument("--titulo", default="NND | AZECO — Galeria de Arte", help="título dos relatórios")
args = _ap.parse_args()

FP_NAMES = {
    10378288: "Pix à vista", 10362651: "Pix Nubank", 10378251: "Pix Itaú",
    10554067: "Pix Parcelado", 9941919: "Dinheiro", 9941921: "Cheque",
    9941922: "Depósito Bancário", 10271615: "Compensação Financeira",
    10378390: "Cartão de Credito_Rede", 10378373: "Pix à vista",
    0: "", 10378251: "Pix Itaú",
}

SIT = {1: "Aberto", 2: "Pago", 3: "Atrasado", 4: "Recebido", 5: "Baixado"}
PV_SIT = {6: "Em aberto", 9: "Atendido", 12: "Cancelado", 15: "Em andamento",
          18: "Venda Agenciada", 21: "Em digitação", 24: "Verificado",
          883047: "Aguardando Envio", 883048: "Aguardando Pagamento",
          883049: "Aguardando Envio Invoice", 883050: "Entregue a transportadora",
          883051: "Recebido pelo cliente"}


def load(f):
    return json.load(open(os.path.join(args.data_dir, f), encoding="utf-8"))


IGNORADAS_PATH = os.path.join(args.data_dir, "cars_ignoradas.json")


def load_ignoradas():
    try:
        with open(IGNORADAS_PATH, encoding="utf-8") as f:
            d = json.load(f)
    except FileNotFoundError:
        return {}
    return {k: v for k, v in d.items() if not k.startswith("_")}


CAT_NAMES = {}


def load_cat_names():
    try:
        d = load("categorias_com_situacao.json")
    except Exception:
        return

    def walk(o):
        if isinstance(o, dict):
            if o.get("id") and o.get("descricao"):
                CAT_NAMES[str(o["id"])] = o["descricao"]
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(d)


def cat_name(obj):
    cid = (obj.get("categoria") or {}).get("id") or 0
    if not cid:
        return "—"
    return CAT_NAMES.get(str(cid), f"{cid} (?)")


def fmt(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def r(hist):
    return (hist or "").replace("R$", "R\\$").replace("\n", " / ").replace("\r", "").replace("|", "\\|")


def fp_name(c):
    fp = c.get("formaPagamento") or {}
    return FP_NAMES.get(fp.get("id"), "")


def sit_name(c):
    return SIT.get(c.get("situacao"), str(c.get("situacao")))


def find_pv_num_for_manual(hist, pv_nums):
    """Tenta achar o numero do PV no historico de uma CAR manual."""
    if not hist:
        return None
    h = hist
    # 1) numeros explícitos 20NNNNN / 20NNNNNN (7 ou 8 digitos). Escolhe o MAIS longo
    #    que exista, com borda nao-digito para evitar prefixo errado.
    cands = []
    for mm in re.finditer(r"(?<!\d)(20\d{5,6})(?!\d)", h):
        n = int(mm.group(1))
        if n in pv_nums:
            cands.append(n)
    if cands:
        return max(cands, key=lambda n: len(str(n)))
    return None


def main():
    pvs = load("pedidos_venda.json")
    cars = load("contas_receber.json")
    ignoradas = load_ignoradas()
    pv_nf = {x["numero"]: x.get("nf") for x in load("notas_fiscais.json")}
    load_cat_names()
    pv_by_num = {}
    for p in pvs:
        pv_by_num.setdefault(p["numero"], p)

    pv_nums = set(pv_by_num.keys())

    # separa ignoradas (mantidas no Bling, fora da contabilização por PV)
    car_ignoradas = []
    cars_rest = []
    for c in cars:
        if str(c["id"]) in ignoradas:
            car_ignoradas.append(c)
        else:
            cars_rest.append(c)
    cars = cars_rest

    # mapeia NF -> PV (para associar CARs notafiscal ao PV dono da NF)
    nf_to_pv = {}
    for p in pvs:
        nf = (p.get("notaFiscal") or {}).get("id")
        if nf:
            nf_to_pv[nf] = p["numero"]

    # agrupa CARs
    by_pv = {}
    no_pv = []
    nf_cars = []
    for c in cars:
        o = c.get("origem") or {}
        tipo = o.get("tipoOrigem") or ""
        hist = c.get("historico") or ""
        if tipo == "venda":
            n = o.get("numero")
            try:
                n = int(n) if n else None
            except Exception:
                n = None
            if n and n in pv_by_num:
                by_pv.setdefault(n, []).append(c)
            else:
                no_pv.append(c)
        elif tipo == "notafiscal":
            nf_id = o.get("id")
            pvnum = nf_to_pv.get(nf_id)
            if pvnum and pvnum in pv_by_num:
                by_pv.setdefault(pvnum, []).append(c)
            else:
                nf_cars.append(c)
        else:
            n = find_pv_num_for_manual(hist, pv_nums)
            if n:
                by_pv.setdefault(n, []).append(c)
            else:
                no_pv.append(c)

    # define estado de cada PV
    info = {}
    for num, p in pv_by_num.items():
        cs = by_pv.get(num, [])
        total = p.get("total") or 0
        soma = sum(x.get("valor") or 0 for x in cs)
        nv = sum(1 for x in cs if (x.get("origem") or {}).get("tipoOrigem") == "venda")
        nnf = sum(1 for x in cs if (x.get("origem") or {}).get("tipoOrigem") == "notafiscal")
        nman = len(cs) - nv - nnf
        sit = (p.get("situacao") or {}).get("id")
        info[num] = dict(pv=p, cars=cs, total=total, soma=round(soma, 2),
                         nvenda=nv, nmanual=nman, nnotafiscal=nnf, situacao=sit)

    def classify(num):
        it = info[num]
        total, soma = it["total"], it["soma"]
        nv, nman = it["nvenda"], it["nmanual"]
        ncars = len(it["cars"])
        if ncars == 0:
            return 6
        if soma == 0:
            return 6
        # duplicação exata ~2x
        if total and abs(soma - 2 * total) < 0.01 and nv > 0 and nman > 0:
            return 3
        if soma > total + 0.01:
            return 1
        if soma < total - 0.01:
            return 2
        # == total
        if nv > 0 and nman == 0 and it["nnotafiscal"] == 0:
            return 5
        if nv == 0 and nman > 0:
            return 4
        return 4

    groups = {1: [], 2: [], 3: [], 4: [], 5: [], 6: []}
    for num in info:
        g = classify(num)
        groups[g].append(num)

    def order_key(num):
        p = info[num]["pv"]
        return p.get("data") or "", p.get("numero") or num

    for g in groups:
        groups[g].sort(key=order_key)

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    total_cars_all = len(cars) + len(car_ignoradas)
    n_venda = sum(1 for c in cars if (c.get("origem") or {}).get("tipoOrigem") == "venda")
    n_nf = sum(1 for c in cars if (c.get("origem") or {}).get("tipoOrigem") == "notafiscal")
    n_man = len(cars) - n_venda - n_nf
    pv_com_car = sum(1 for num in info if len(info[num]["cars"]) > 0)
    n_pvs = len(info)

    # ---------- escreve relatorio ----------
    out = []
    out.append("# Relatório de Contas a Receber por Pedido de Venda")
    out.append("")
    out.append("**" + args.titulo + "**")
    out.append("")
    out.append("> Total de cada título = total do PV. PVs classificados por cobertura das CARs.")
    out.append("")
    out.append(f"- Total CARs: **{total_cars_all}** · `venda`: {n_venda} · `notafiscal`: {n_nf} · manual: {n_man} · ignoradas: {len(car_ignoradas)} · PVs com CAR: {pv_com_car}")
    out.append(f"- Atualizado: {now}")
    out.append("")
    out.append("## Índice")
    out.append("")
    out.append(f"1. ⬆ Acima do total — {len(groups[1])} PV")
    out.append(f"2. ⬇ Abaixo do total — {len(groups[2])} PV")
    out.append(f"3. 🔁 Duplicação exata (≈2×) — {len(groups[3])} PV")
    out.append(f"4. 🔄 Cobre via manual — {len(groups[4])} PV")
    out.append(f"5. ✅ Ideal — {len(groups[5])} PV")
    out.append(f"6. ⚠️ PVs sem CAR (não cobertos) — {len(groups[6])}")
    out.append("")
    out.append("")
    group_titles = {
        1: ("## 1. ⬆ Acima do total", "CARs somam **mais** que o total do PV"),
        2: ("## 2. ⬇ Abaixo do total", "CARs somam **menos** que o total do PV"),
        3: ("## 3. 🔁 Duplicação exata (≈2×)", "Soma das CARs = **2× total**"),
        4: ("## 4. 🔄 Cobre via manual", "Total **coberto**, mas só por CARs manuais"),
        5: ("## 5. ✅ Ideal", "CARs de origem `venda` = total, sem manuais"),
        6: ("## 6. ⚠️ PVs sem CAR (não cobertos)", "Pedidos de venda existentes **sem nenhuma CAR**"),
    }
    # para grupo 6 escrever tabela compacta, para demais blocos detalhados
    def emit_header(g):
        t, d = group_titles[g]
        out.append(t + f" — {len(groups[g])} PV")
        out.append("")
        out.append(f"> {d}.")
        out.append("")

    def fmt_situ(c):
        return sit_name(c)

    def emit_pv_block(num):
        it = info[num]
        p = it["pv"]
        cnome = (p.get("contato") or {}).get("nome") or ""
        num_pv = p.get("numero")
        nf = pv_nf.get(num_pv)
        nf_tag = " — **NF vinculada**" if nf else ""
        sit = it["situacao"]
        cancel_tag = " — **Cancelado**" if sit == 12 else ""
        out.append(f"### PV {num_pv} — {cnome}{nf_tag}{cancel_tag}")
        out.append("")
        out.append(f"**Total do PV:** {fmt(it['total'])} · _(soma CARs: {fmt(it['soma'])})_ · {it['nvenda']} `venda` · {it['nnotafiscal']} `notafiscal` · {it['nmanual']} manual")
        out.append(f"**Categoria do PV:** {cat_name(p)}")
        out.append("")
        autos = [c for c in it["cars"] if (c.get("origem") or {}).get("tipoOrigem") == "venda"]
        nfcs = [c for c in it["cars"] if (c.get("origem") or {}).get("tipoOrigem") == "notafiscal"]
        mans = [c for c in it["cars"] if (c.get("origem") or {}).get("tipoOrigem") not in ("venda", "notafiscal")]
        if autos:
            out.append(f"#### Automáticas (origem `venda`) ({len(autos)})")
            out.append("")
            out.append("| CAR | vencimento | competência | valor | situação | categoria | forma | contato id | histórico |")
            out.append("|---|---|---|---|---|---|---|---|---|")
            for c in autos:
                cc = c.get("contato") or {}
                out.append(f"| `{c['id']}` | {c.get('vencimento')} | {c.get('competencia')} | {fmt(c.get('valor'))} | {fmt_situ(c)} | {cat_name(c)} | {fp_name(c)} | {cc.get('id')} | {r(c.get('historico'))} |")
            out.append("")
        if nfcs:
            out.append(f"#### De Nota Fiscal (origem `notafiscal`) ({len(nfcs)})")
            out.append("")
            out.append("| CAR | NF | vencimento | competência | valor | situação | categoria | histórico |")
            out.append("|---|---|---|---|---|---|---|---|")
            for c in nfcs:
                nfnum = ((c.get("origem") or {}).get("numero") or "")
                out.append(f"| `{c['id']}` | {nfnum} | {c.get('vencimento')} | {c.get('competencia')} | {fmt(c.get('valor'))} | {fmt_situ(c)} | {cat_name(c)} | {r(c.get('historico'))} |")
            out.append("")
        if mans:
            out.append(f"#### Manuais (sem origem) ({len(mans)})")
            out.append("")
            out.append("| CAR | vencimento | competência | valor | situação | categoria | forma | contato id | histórico |")
            out.append("|---|---|---|---|---|---|---|---|---|")
            for c in sorted(mans, key=lambda x: x.get("vencimento") or ""):
                cc = c.get("contato") or {}
                out.append(f"| `{c['id']}` | {c.get('vencimento')} | {c.get('competencia')} | {fmt(c.get('valor'))} | {fmt_situ(c)} | {cat_name(c)} | {fp_name(c)} | {cc.get('id')} | {r(c.get('historico'))} |")
            out.append("")
        # divergencias
        if autos and mans:
            out.append("**Divergências (manual × automática):**")
            # pairing por vencimento aproximado
            seen = set()
            for m in sorted(mans, key=lambda x: x.get("vencimento") or ""):
                cand = None
                for a in autos:
                    if a["id"] in seen:
                        continue
                    if (m.get("vencimento") or "").startswith((a.get("vencimento") or "")[:7]):
                        cand = a
                        break
                if cand:
                    seen.add(cand["id"])
                    out.append(f"- CAR `{m['id']}` (gêmeo `{cand['id']}`) → **situação ({fmt_situ(cand)} vs {fmt_situ(m)})**")
            out.append("")

    for g in (1, 2, 3, 4, 5):
        emit_header(g)
        for num in groups[g]:
            emit_pv_block(num)
            out.append("")

    # grupo 6: tabela
    emit_header(6)
    if groups[6]:
        out.append("| PV | data | total | contato | situação | categoria |")
        out.append("|---|---|---|---|---|---|")
        for num in groups[6]:
            it = info[num]
            p = it["pv"]
            cnome = (p.get("contato") or {}).get("nome") or ""
            sit = PV_SIT.get(it["situacao"], str(it["situacao"]))
            out.append(f"| {p.get('numero')} | {p.get('data')} | {fmt(it['total'])} | {cnome} | {sit} | {cat_name(p)} |")
        out.append("")
    out.append("")

    # CARs sem PV e NF
    out2 = []
    out2.append("# Relatório — CARs sem PV / de Nota Fiscal")
    out2.append("")
    out2.append("**" + args.titulo + "**")
    out2.append("")
    out2.append(f"- CARs sem PV: **{len(no_pv)}** · NF restantes: **{len(nf_cars)}**")
    out2.append(f"- Atualizado: {now}")
    out2.append("")
    out2.append("## Índice")
    out2.append("")
    out2.append(f"1. CARs sem PV correspondente — {len(no_pv)}")
    out2.append(f"2. CARs de Nota Fiscal restantes — {len(nf_cars)}")
    out2.append("")
    out2.append("")
    out2.append("## 1. CARs sem PV correspondente")
    out2.append("")
    out2.append("> Contas a receber cujo histórico não referencia um Pedido de Venda existente (mesmo após tradução da numeração antiga).")
    out2.append("")
    out2.append("| CAR | venc | valor | situação | categoria | forma | histórico |")
    out2.append("|---|---|---|---|---|---|---|")
    for c in sorted(no_pv, key=lambda x: x.get("vencimento") or ""):
        out2.append(f"| `{c['id']}` | {c.get('vencimento')} | {fmt(c.get('valor'))} | {fmt_situ(c)} | {cat_name(c)} | {fp_name(c)} | {r(c.get('historico'))} |")
    out2.append("")
    out2.append("## 2. CARs de Nota Fiscal restantes")
    out2.append("")
    if nf_cars:
        out2.append("| CAR | NF | venc | valor | situação | categoria | histórico |")
        out2.append("|---|---|---|---|---|---|---|")
        for c in nf_cars:
            nfnum = ((c.get("origem") or {}).get("numero") or "")
            out2.append(f"| `{c['id']}` | {nfnum} | {c.get('vencimento')} | {fmt(c.get('valor'))} | {fmt_situ(c)} | {cat_name(c)} | {r(c.get('historico'))} |")
        out2.append("")
    else:
        out2.append("_Nenhuma._")
        out2.append("")

    # CARs ignoradas
    if car_ignoradas:
        out.append("")
        out.append("## CARs ignoradas na contabilização")
        out.append("")
        out.append("> Mantidas no Bling, porém fora da soma/classificação por PV (ver `data/cars_ignoradas.json`).")
        out.append("")
        out.append("| CAR | vencimento | competência | valor | situação | categoria | forma | motivo |")
        out.append("|---|---|---|---|---|---|---|---|")
        for c in sorted(car_ignoradas, key=lambda x: x.get("vencimento") or ""):
            motivo = (ignoradas.get(str(c["id"])) or {}).get("motivo", "")
            out.append(f"| `{c['id']}` | {c.get('vencimento')} | {c.get('competencia')} | {fmt(c.get('valor'))} | {fmt_situ(c)} | {cat_name(c)} | {fp_name(c)} | {motivo} |")
        out.append("")

    with open(os.path.join(args.out_dir, "report_cars_por_pv.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    with open(os.path.join(args.out_dir, "report_cars_sem_pv.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(out2))

    print("grupos:", {k: len(v) for k, v in groups.items()})
    print("sem PV:", len(no_pv), "NF:", len(nf_cars))


if __name__ == "__main__":
    main()
