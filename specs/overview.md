# Visão geral

Integração com a **API v3 do Bling** para a galeria **NND | AZECO**.

Requisitos e setup ficam no [`README.md`](../README.md).

## CLI e client

- **CLI**: `python3 -m bling <GET|POST|PUT|PATCH|DELETE> <endpoint> [body]` — renova o token
  e grava de volta no `.env`. Body inline, `@arquivo.json` ou `-` (stdin); sai `1` em erro ≥400.
- **Client**: `from bling import BlingClient` — auth/refresh, retry e paginação
  (`get`, `request`, `paginate`).

## Estrutura

- `bling/` — client e CLI da API v3.
- `scripts/` — fetchers, relatórios e ações; referência em [`scripts.md`](scripts.md).
- `specs/` — esta documentação.
- `tools/` — apoio (ex.: gerador de `scripts.md`).
- `data/` — snapshots locais do Bling (ver [`data.md`](data.md)).

## Nomenclatura de scripts

Convenções de nomenclatura e escrita de scripts novos: ver
[`writing-scripts.md`](writing-scripts.md).
