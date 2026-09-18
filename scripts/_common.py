"""Utilitários compartilhados pelos scripts (paths, JSON, formatação, associação CAR↔PV)."""
import json
import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
BACKUPS_DIR = os.path.join(ROOT, "backups")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj, indent=None):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent)


def money(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def car_put_body(car, historico=None):
    """Corpo de `PUT /contas/receber/{id}` a partir do GET (omite `situacao`, read-only)."""
    return {
        "contato": {"id": car["contato"]["id"]},
        "dataEmissao": car.get("dataEmissao"),
        "vencimento": car.get("vencimento"),
        "valor": car.get("valor"),
        "formaPagamento": {"id": (car.get("formaPagamento") or {}).get("id")},
        "categoria": {"id": (car.get("categoria") or {}).get("id")},
        "portador": {"id": (car.get("portador") or {}).get("id")},
        "vendedor": {"id": (car.get("vendedor") or {}).get("id")},
        "numeroDocumento": car.get("numeroDocumento") or "",
        "historico": car.get("historico") if historico is None else historico,
    }


def find_pv_number(hist, pv_numbers):
    """Acha o número de PV (20NNNNN/20NNNNNN) citado no histórico de uma CAR manual."""
    if not hist:
        return None
    candidates = [int(m.group(1)) for m in re.finditer(r"(?<!\d)(20\d{5,6})(?!\d)", hist)
                  if int(m.group(1)) in pv_numbers]
    if candidates:
        return max(candidates, key=lambda n: len(str(n)))
    return None


def associate_cars(cars, pvs, excluir=()):
    """Agrupa CARs por número de PV.

    origem 'venda' -> origem.numero; 'notafiscal' -> NF ligada ao PV; manual -> histórico.
    Retorna (pv_by_num, car_ids_by_pv).
    """
    excluir = set(excluir or [])
    pv_by_num = {p["numero"]: p for p in pvs}
    pv_numbers = set(pv_by_num)
    nf_to_pv = {}
    for p in pvs:
        nf = (p.get("notaFiscal") or {}).get("id")
        if nf:
            nf_to_pv[nf] = p["numero"]

    car_ids_by_pv = defaultdict(list)
    for c in cars:
        if c["id"] in excluir:
            continue
        origem = c.get("origem") or {}
        tipo = origem.get("tipoOrigem") or ""
        number = None
        if tipo == "venda":
            try:
                number = int(origem.get("numero"))
            except (TypeError, ValueError):
                number = None
            if number not in pv_by_num:
                number = None
        elif tipo == "notafiscal":
            number = nf_to_pv.get(origem.get("id"))
        else:
            number = find_pv_number(c.get("historico") or "", pv_numbers)
        if number:
            car_ids_by_pv[number].append(c["id"])
    return pv_by_num, car_ids_by_pv
