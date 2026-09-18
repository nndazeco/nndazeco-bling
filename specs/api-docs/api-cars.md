# API — Contas a receber (CAR) e `lancar-contas`

> Achados validados (não redescobrir). Ver também [`api-pv.md`](api-pv.md) (recriação de PV)
> e [`api-baixas.md`](api-baixas.md) (baixa/estorno).

## Origens

- `origem.tipoOrigem` na CAR: **`venda`** (gerada do Pedido de Venda), **`notafiscal`**
  (gerada de NF), vazio = **manual**.
- **PV via API NÃO gera CAR sozinho** → chamar `POST /pedidos/vendas/{id}/lancar-contas`.
- **PV via formulário (UI) GERA CAR** automaticamente (config "Lançamento automático de
  contas em Pedidos de Venda" está ativa).

## `lancar-contas`

- `lancar-contas` num PV já lançado → **400 erro 62** ("contas já foram lançadas"); não
  duplica. **Porém, após excluir TODAS as CARs `venda` do PV, o relançamento funciona**
  (204).
- **`lancar-contas` gera CAR apenas p/ parcelas cuja forma de pagamento tem `destino`=1**
  (campo da forma, spec `FormasPagamentosDadosDTO.destino`: `1` Conta a receber/pagar,
  `2` Ficha financeira, `3` Caixa e bancos). Formas com `destino`=3 **NÃO geram CAR**.
  ATENÇÃO: `GET /formas-pagamentos` **não traz `destino`** (só `situacao`/`tipoPagamento`);
  use `GET /formas-pagamentos/{id}` (1 chamada por item) nas parcelas de PVs com CARs
  faltando. Formas **inativas abortam o `lancar-contas` da venda inteira** ("forma de
  pagamento não existe ou está inativa").
- **Apagar o PV (`DELETE /pedidos/vendas/{id}`) apaga em cascata as CARs de origem `venda`**.

## Histórico da CAR

- Histórico automático da CAR gerada do PV: `Ref. ao pedido de venda nº {numero}`
  (+ ` | {observação da parcela}` se a parcela tiver obs).
- Observações gerais do PV **não** propagam; só a **observação da parcela** vai para o
  histórico.

## NF → CAR

- CAR origem `notafiscal` nasce ao emitir NF com config "Lançar contas ao emitir/cancelar
  nota" (ou `POST /nfe/{id}/lancar-contas`). Endpoints de NF são `/nfe`, `/nfce`, `/nfse`
  (não `/notas-fiscais`).
- **Na conta atual a config "Lançar contas ao emitir ou cancelar nota" está DESATIVADA**
  (NF-e → Configurações gerais) → NF não gera CAR por si; só via
  `POST /nfe/{id}/lancar-contas` manual (que lança as parcelas da NF).
- **PV com NF vinculada**: `lancar-contas` do PV é bloqueado (ver [`api-pv.md`](api-pv.md)).
  NF vinculada **não garante** CAR `notafiscal`.
