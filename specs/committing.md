# Mensagens de commit

Conventional Commits, versão enxuta.

## Formato

```
tipo(escopo opcional): descrição curta no imperativo

corpo opcional
```

- **Descrição**: imperativo ("adiciona", não "adicionado"/"adicionando"), até ~50 caracteres,
  sem ponto final.
- **Tipos**: `feat` (funcionalidade nova), `fix` (correção de bug), `docs` (specs/README/
  AGENTS.md), `refactor` (sem mudar comportamento), `chore` (config, deps, tooling), `test`.
- **Escopo**: opcional, quando ajuda a localizar — `feat(scripts)`, `fix(cli)`,
  `docs(scripts)`. Omitir se óbvio pelo tipo.
- **Corpo**: só quando o *porquê* não é óbvio pelo diff (motivo, trade-off, contexto de uma
  pendência) — não narrar o que o diff já mostra.

## Atomicidade

1 commit = 1 mudança lógica. Nada de "e" na descrição (`fix X e adiciona Y`) — se precisa de
"e", são 2 commits.

## Referências

Se o commit resolve ou avança algo em [`PENDENCIAS.md`](../PENDENCIAS.md) ou muda uma decisão
registrada numa spec, citar no corpo (ex.: `Resolve P9.`).

## Exemplos

```
feat(scripts): adiciona check_categorias_inativas

docs(scripts): cria writing-scripts.md e referencia nas specs

fix(cli): renova token antes do 401 em vez de depois

chore: adiciona shebang + chmod +x em scripts/*.py
```

## O que não fazer

- Não commitar `WIP`, `ajustes`, `fix 2` — descrever o que muda.
- Não misturar mudança funcional com reformatação em massa no mesmo commit.
- Não incluir dados sensíveis (`.env`, tokens, ids de cliente) na mensagem.
