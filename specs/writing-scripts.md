# Escrita de scripts novos

Convenções pra criar um script novo em `scripts/`. Esta é a **fonte única** da nomenclatura de
verbos — `tools/gen_script_docs.py` e `overview.md` referenciam este arquivo, não repetem a
tabela.

## Princípio

1 script = 1 tarefa. Só stdlib (sem dependências externas). Genérico e parametrizável — nunca
hardcodar ids/nomes; use argumentos.

**Exceção:** `fetch_all.py` é um orquestrador (roda vários `fetch_*` em sequência) — não é
1 entidade, é o único caso assim no repo.

## Nomenclatura

`verbo_entidade.py`, snake_case. O verbo é obrigatório e indica a natureza do script:

| verbo | natureza |
|---|---|
| `fetch_` | lê a API e grava snapshot em `data/` |
| `report_` | relatório offline (a partir dos snapshots), não muta |
| `apply_` | altera dados na API — **dry-run por padrão** |
| `check_` | audita/imprime — **não altera nada** |
| `recreate_` | recria entidade — **dry-run por padrão** |
| `delete_` | exclusões — **destrutivas, dry-run por padrão** |
| `enrich_` | complementa snapshot existente com lookups extras |

## Estrutura/esqueleto

Shebang `#!/usr/bin/env python3` na 1ª linha + arquivo com bit `+x` (`chmod +x scripts/nome.py`).
Depois: docstring, `ROOT`/`sys.path` (pra importar `bling`/`scripts._common` de qualquer cwd),
imports `_common`/`bling`, `main()`, guard `if __name__ == "__main__"`.

Modelos pra copiar a estrutura (não colar código daqui, ler o arquivo):
- [`scripts/fetch_formas_pagamento.py`](../scripts/fetch_formas_pagamento.py) — fetch simples.
- [`scripts/apply_renomear_pv_historico.py`](../scripts/apply_renomear_pv_historico.py) — apply
  com dry-run/`--execute`.

## Docstring

1ª linha = propósito do script — é extraída via `ast.get_docstring` por
`tools/gen_script_docs.py` e vira a descrição em `specs/scripts.md`. Depois, bloco `Uso:` com
exemplos de linha de comando. Se o script lê um `--plan`, incluir exemplo do JSON esperado.

## Argumentos (argparse sempre)

Nunca `sys.argv` cru. Convenções de nome já em uso:

- `--data-dir` — diretório dos snapshots (default `data/`).
- `--out` / `--output` — arquivo de saída.
- `--sleep` — intervalo entre chamadas à API.
- `--plan` — arquivo JSON com o plano de mutação.
- `--cars` — filtro/seleção de CARs.
- `--execute` — sai do dry-run e aplica de verdade.

Todo argumento leva `help`; o parser leva `description`.

## Dados

Ler snapshots via `--data-dir` + `_common.load_json`. Usar `_common.associate_cars` e
`_common.money` em vez de reimplementar. Nunca hardcodar ids/nomes — sempre parametrizar ou
derivar do snapshot/API.

## API

Sempre via `bling.BlingClient` (já cobre refresh de token, retry e paginação — nunca reescrever
isso num script). Respeitar `--sleep` entre chamadas. Quando a listagem não traz um campo
necessário, buscar o detalhe do item individualmente.

## Scripts que mutam (`apply_`/`recreate_`/`delete_`)

- Dry-run por padrão; só muta com `--execute`.
- Imprimir o plano antes de aplicar (o que vai mudar, mesmo no dry-run).
- Reler o estado ao vivo no `--execute` (não confiar em snapshot) — garante idempotência.
- No PUT de CAR: omitir `situacao` do body e usar `_common.car_put_body`.
- Workaround do **erro 84** (forma de pagamento inativa trava PUT): reativar a forma → fazer o
  PUT → restaurar o estado original da forma.
- Fazer backup antes de mutar (ex.: `backups/backups_<script>_<timestamp>/`).
- Pedir confirmação explícita antes de qualquer ação destrutiva.
- Relatório final: "aplicado em N" (contagem do que foi de fato alterado).

## Saídas

- `report_*`: grava `.md` (nome `report_<algo>.md`), escapando `R$` para `R\$` (markdown
  trata `$` como possível LaTeX).
- `check_*`: só stdout — não grava arquivo, não muta nada.

## Evitar duplicação (DRY)

Trecho repetido entre scripts, ou dentro do mesmo script, vai para `scripts/_common.py` (ou um
helper local se for específico demais pra `_common`). Casos de duplicação já conhecidos no
repo, tratar como regra geral daqui pra frente:

- Montagem do body de PUT de CAR (`car_put_body`) — usar sempre o helper, não remontar o dict.
- Workaround do erro 84 — mesma sequência (reativar → PUT → restaurar) em qualquer script que
  mexa em forma de pagamento vinculada a CAR.

## Checklist pós-criação

1. `python3 -m py_compile scripts/novo_script.py`.
2. Registrar entrada no `META` de `tools/gen_script_docs.py` (entidade, api, mutates, output,
   example).
3. Rodar `python3 tools/gen_script_docs.py` pra regenerar `specs/scripts.md`.
4. Adicionar o nome do script à lista `## Scripts` do `AGENTS.md`.
5. Se o script criar um snapshot novo em `data/`, atualizar `specs/data.md` e, se fizer
   sentido, incluir no `scripts/fetch_all.py`.
6. Atualizar `README.md` se o script mudar o escopo geral do projeto.
