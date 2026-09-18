# API — Pedido de Compra → Contas a Pagar (CAP)

> Achados validados (não redescobrir).

- **PC via API GERA CAP automaticamente** (1 CAP por parcela). CAP não recebe `origem`
  preenchida (só texto).
- Histórico automático: `Ref. ao pedido de compra nº {numero}, {nome fornecedor}`
  (+ ` | {obs da parcela}`).
- Granularidade financeira = **parcela**, não item.
- **Categoria financeira é atribuída ao PC e a CAP gerada herda**.
- Muitos PCs de evento (exposição) existem sem parcelas → não geram CAP (o gasto fica como
  CAP manual com sufixo `| Exposição: ...`).
