"""Integração com a API v3 do Bling — client reusável (só stdlib).

Credenciais vêm do `.env` (veja `.env.example`). O access_token é renovado
automaticamente via refresh_token e gravado de volta no `.env`.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_HOST = "api.bling.com.br"

# status transitórios do Bling/Cloudflare que valem retry
_RETRY_STATUS = (429, 500, 502, 503, 504)


class BlingError(Exception):
    """Erro retornado pela API ou falha de rede após esgotar retries."""

    def __init__(self, status, body):
        super().__init__(f"Bling API erro {status}: {body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)}")
        self.status = status
        self.body = body


def load_env(path):
    """Lê um .env simples (KEY=VALUE, ignora comentários e linhas vazias)."""
    env = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def upsert_env(path, updates):
    """Atualiza/cria chaves em um .env preservando comentários e demais linhas."""
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    out = []
    pending = dict(updates)
    for line in lines:
        key = line.split("=", 1)[0].strip() if ("=" in line and not line.startswith("#")) else None
        if key in pending:
            out.append(f"{key}={pending.pop(key)}")
        else:
            out.append(line)
    for key, value in pending.items():
        out.append(f"{key}={value}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _encode_params(params):
    """Query string preservando colchetes literais (ex.: situacao[]=1)."""
    parts = []
    for key, value in params.items():
        values = value if isinstance(value, (list, tuple)) else [value]
        for item in values:
            parts.append(f"{key}={urllib.parse.quote(str(item), safe='')}")
    return "&".join(parts)


class BlingClient:
    """Cliente mínimo da API v3: auth via .env, retry, refresh e paginação."""

    def __init__(self, env_file=None, timeout=40, retries=6):
        self.root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.env_file = env_file or os.path.join(self.root, ".env")
        env = load_env(self.env_file)

        self.host = env.get("BLING_HOST") or DEFAULT_HOST
        self.client_id = env.get("BLING_CLIENT_ID", "")
        self.client_secret = env.get("BLING_CLIENT_SECRET", "")
        self.refresh_token = env.get("BLING_REFRESH_TOKEN", "")
        self.access_token = env.get("BLING_ACCESS_TOKEN", "")
        self.expires_at = int(env.get("BLING_EXPIRES_AT") or 0)

        self.timeout = timeout
        self.retries = retries
        self.base_url = f"https://{self.host}/Api/v3"

    # ---------- autenticação ----------
    def refresh(self):
        """Renova o access_token e grava os novos valores no .env."""
        if not (self.client_id and self.client_secret and self.refresh_token):
            raise BlingError(401, "credenciais ausentes no .env (BLING_CLIENT_ID/SECRET/REFRESH_TOKEN)")

        body = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }).encode()
        token = urllib.parse.quote(f"{self.client_id}:{self.client_secret}", safe="")
        req = urllib.request.Request(
            f"{self.base_url}/oauth/token",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Basic {_b64(self.client_id, self.client_secret)}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            payload = json.loads(r.read().decode("utf-8"))

        self.access_token = payload["access_token"]
        self.refresh_token = payload["refresh_token"]
        self.expires_at = int(time.time()) + int(payload["expires_in"])

        upsert_env(self.env_file, {
            "BLING_ACCESS_TOKEN": self.access_token,
            "BLING_REFRESH_TOKEN": self.refresh_token,
            "BLING_EXPIRES_AT": self.expires_at,
        })
        return self

    def _ensure_token(self):
        if not self.access_token or time.time() >= self.expires_at - 60:
            self.refresh()

    # ---------- HTTP ----------
    def request(self, method, path, body=None, retries=None):
        """Executa a request e devolve (status, dados). Levanta BlingError ao esgotar."""
        retries = self.retries if retries is None else retries
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        last = (-1, "sem resposta")

        for attempt in range(retries):
            self._ensure_token()
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json",
            }
            if data is not None:
                headers["Content-Type"] = "application/json"

            req = urllib.request.Request(url, data=data, method=method, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    raw = r.read().decode("utf-8", "replace")
                    return r.status, (json.loads(raw) if raw.strip() else {})
            except urllib.error.HTTPError as e:
                raw = e.read().decode("utf-8", "replace")
                if e.code == 401:
                    self.refresh()
                    continue
                if e.code in _RETRY_STATUS:
                    last = (e.code, raw)
                    time.sleep(2.5 * (attempt + 1))
                    continue
                try:
                    return e.code, json.loads(raw)
                except ValueError:
                    return e.code, raw
            except Exception as exc:  # rede/timeout
                last = (-1, str(exc))
                time.sleep(2 * (attempt + 1))

        raise BlingError(last[0], last[1])

    def get(self, path, params=None):
        if params:
            sep = "&" if "?" in path else "?"
            path = f"{path}{sep}{_encode_params(params)}"
        return self.request("GET", path)

    def paginate(self, path, params=None, limit=100, sleep=0.4):
        """Percorre todas as páginas de um endpoint de listagem."""
        items = []
        page = 1
        while True:
            query = dict(params or {})
            query["pagina"] = page
            query["limite"] = limit
            status, data = self.get(path, query)
            if status != 200:
                raise BlingError(status, data)
            page_items = data.get("data") or []
            items.extend(page_items)
            if len(page_items) < limit:
                break
            page += 1
            time.sleep(sleep)
        return items


def _b64(client_id, client_secret):
    import base64

    return base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
