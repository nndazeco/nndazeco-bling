"""CLI da API v3 do Bling.

Uso:
  python3 -m bling GET /produtos
  python3 -m bling POST /pedidos/vendas '{"contato":{"id":1}}'
  python3 -m bling PUT /pedidos/vendas/123 @body.json
  echo '{...}' | python3 -m bling POST /pedidos/vendas -

Credenciais: .env (veja .env.example). O token é renovado automaticamente.
"""
from __future__ import annotations

import json
import sys

from .client import BlingClient, BlingError

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
HELP = __doc__


def _parse(argv):
    """Separa <METODO> <endpoint> [body]."""
    if not argv or argv[0] in ("-h", "--help"):
        return None, None, None, None
    if argv[0].upper() not in METHODS or len(argv) < 2:
        return "erro", None, None, None
    return "ok", argv[0].upper(), argv[1], argv[2:]


def _parse_body(extra):
    if not extra:
        return {"ok": True, "value": None}
    raw = extra[0]
    try:
        if raw == "-":
            raw = sys.stdin.read()
        elif raw.startswith("@"):
            with open(raw[1:], encoding="utf-8") as f:
                raw = f.read()
        return {"ok": True, "value": json.loads(raw)}
    except (OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    kind, method, endpoint, extra = _parse(argv)

    if kind is None:
        print(HELP)
        return 0
    if kind == "erro":
        print(HELP, file=sys.stderr)
        return 2

    parsed = _parse_body(extra)
    if not parsed["ok"]:
        print(f"erro: body invalido ({parsed['error']})", file=sys.stderr)
        return 2
    body = parsed["value"]

    client = BlingClient()
    try:
        status, data = client.request(method, endpoint, body=body)
    except BlingError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1

    if isinstance(data, (dict, list)):
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(data)
    return 0 if status < 400 else 1


if __name__ == "__main__":
    raise SystemExit(main())
