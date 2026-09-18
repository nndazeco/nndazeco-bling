# API — Limites e integração

> Achados validados (não redescobrir).

- **Não há webhook** para contas (receber/pagar) nem pedido de compra → usar **polling**.
- Rate limit agressivo: rajadas → 429/Cloudflare 1015. Fetch em lote com concorrência
  moderada + retry; listagens de CAP/CAR **não** trazem `categoria`/`historico` → exigem 1
  chamada de detalhe por item. Varreduras de CAP completo (~974 itens) levam ~10 min.
