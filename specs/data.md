# Arquivos de dados (`data/`) e formato

`data/` guarda **snapshots JSON** baixados do Bling, usados como referência offline pelos
relatórios. **Revalidar ao vivo antes de decidir.** Contagens mudam com o tempo.

## Snapshots

| Arquivo | Gerado por | Conteúdo |
|---|---|---|
| `pedidos_venda.json` | `fetch_pedidos_venda.py` / `fetch_all.py` | Pedidos de venda (detalhe: itens, parcelas, desconto, NF, situação). |
| `notas_fiscais.json` | `fetch_notas_fiscais.py` / `fetch_all.py` | Mapa PV → NF (`numero`, `id`, `nf`, `situacao`, `total`, `contato`). |
| `contas_receber.json` | `fetch_contas_receber.py` / `fetch_all.py` | CARs com detalhe (origem, histórico, categoria, forma). |
| `contas_pagar.json` | `fetch_contas_pagar.py` | CAPs com detalhe (incremental/retomável). |
| `formas_pagamento.json` | `fetch_formas_pagamento.py` / `fetch_all.py` | Formas de pagamento (lista + detalhe com `destino`, `situacao`). |
| `categorias_com_situacao.json` | `fetch_categorias.py` / `fetch_all.py` | Categorias de receitas/despesas com `situacao`. |
| `artista_<slug>.json` | `fetch_artista.py` + `enrich_snapshot.py` | Snapshot de um artista (obras, PVs, CAPs) + `lookups` de nomes. |
| `cars_ignoradas.json` | manual | CARs mantidas no Bling, fora da contabilização por PV (com motivo). |

## Associação CAR → PV (usada nos relatórios)

Em `scripts/_common.py` (`associate_cars`):

- `origem.tipoOrigem == "venda"` → `origem.numero` (número do PV).
- `origem.tipoOrigem == "notafiscal"` → NF ligada ao PV (`pedidos_venda.json` → `notaFiscal.id`).
- **manual** → procura o número do PV **atual** (`20NNNNN`/`20NNNNNN`) no histórico; sem
  match → "sem PV".

## Gotchas de formato

- Nos `.md` de relatório, valores monetários são escritos `R\$` (escape) para o `$` não ser
  interpretado como math. Aplicar `.replace("R$","R\\$")` ao regerar.
- `GET` de listagem de CAP/CAR **não** traz `categoria`/`historico` → exige detalhe por item.
- `GET item.valor` de PV é o valor **líquido**; `item.desconto` é **percentual** (POST e GET).
