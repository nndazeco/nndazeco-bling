#!/usr/bin/env python3
"""Salva lançamentos de contas a pagar (incremental, retomável)."""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bling import BlingClient  # noqa: E402

OUT = os.path.join(ROOT, "data", "contas_pagar.json")

_client = None


def api(endpoint):
    global _client
    if _client is None:
        _client = BlingClient()
    status, data = _client.request("GET", endpoint)
    if status != 200:
        raise RuntimeError(f"GET {endpoint} -> {status}")
    return data

# já coletados?
acumulado = []
if os.path.exists(OUT):
    try:
        acumulado = json.load(open(OUT))
        print(f"Retomando: já há {len(acumulado)} lançamentos salvos", flush=True)
    except Exception:
        acumulado = []

coletados_ids = {l["id"] for l in acumulado}

# página os ids de todos
page = 1
ids = []
while True:
    d = api(f"/contas/pagar?pagina={page}&limite=100").get("data", [])
    if not d:
        break
    ids.extend(l["id"] for l in d)
    page += 1

print(f"Total ids na API: {len(ids)}", flush=True)

faltantes = [i for i in ids if i not in coletados_ids]
print(f"Faltam detalhes de: {len(faltantes)}", flush=True)

# busca detalhes faltantes e salva incrementalmente
for n, i in enumerate(faltantes):
    try:
        det = api(f"/contas/pagar/{i}").get("data", {})
        acumulado.append(det)
        coletados_ids.add(i)
    except Exception as e:
        print(f"  erro id {i}: {e}", flush=True)
        time.sleep(1)
    if (n + 1) % 25 == 0:
        with open(OUT, "w") as f:
            json.dump(acumulado, f, ensure_ascii=False, indent=2)
        print(f"  {n+1}/{len(faltantes)} salvos ({len(acumulado)} total)", flush=True)
    time.sleep(0.02)

with open(OUT, "w") as f:
    json.dump(acumulado, f, ensure_ascii=False, indent=2)
print(f"Concluído: {len(acumulado)} lançamentos em data/contas_pagar.json", flush=True)
