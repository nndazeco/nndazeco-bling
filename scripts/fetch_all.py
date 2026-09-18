#!/usr/bin/env python3
"""Orquestra a coleta de todos os snapshots.

Uso: python3 scripts/fetch_all.py

Executa, em ordem:
  1. fetch_pedidos_venda     -> data/pedidos_venda.json
  2. fetch_notas_fiscais     -> data/notas_fiscais.json
  3. fetch_contas_receber    -> data/contas_receber.json
  4. fetch_formas_pagamento  -> data/formas_pagamento.json
  5. fetch_categorias        -> data/categorias_com_situacao.json
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import fetch_categorias  # noqa: E402
import fetch_contas_receber  # noqa: E402
import fetch_formas_pagamento  # noqa: E402
import fetch_notas_fiscais  # noqa: E402
import fetch_pedidos_venda  # noqa: E402


def main():
    print("=== 1/5 pedidos de venda ===", flush=True)
    fetch_pedidos_venda.main()
    print("=== 2/5 notas fiscais ===", flush=True)
    fetch_notas_fiscais.main()
    print("=== 3/5 contas a receber ===", flush=True)
    fetch_contas_receber.main()
    print("=== 4/5 formas de pagamento ===", flush=True)
    fetch_formas_pagamento.main()
    print("=== 5/5 categorias ===", flush=True)
    fetch_categorias.main()
    print("snapshots atualizados.", flush=True)


if __name__ == "__main__":
    main()
