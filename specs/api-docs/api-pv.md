# API — Pedido de venda (PV)

> Achados validados (não redescobrir). Origens de CAR em [`api-cars.md`](api-cars.md).

## Recriação de PV

- Fluxo: backup `GET` → `DELETE` (apaga CARs `venda` em cascata) → `POST` (numero fixo) →
  `POST /lancar-contas` → validar CARs.
- **Recriar PV mantendo número**: `POST /pedidos/vendas` aceita `numero` fixo e sempre cria
  com situação **6 (Em aberto)**. Útil quando o PUT está bloqueado ("venda bloqueada para
  edição, salva parcialmente"). Cuidado: **vendedor inativo** no POST → erro "Vendedor
  inativo" (usar um vendedor ativo).
- **`situacao` do PV NÃO é editável via API**: `PUT /pedidos/vendas/{id}` exige **body
  completo** (senão erro 23 "Insira ao menos um item") e, mesmo com ele, ignora `situacao`
  (retorna 200, continua 6); não existem endpoints `/situacoes`, `/alterar-situacao` (404).
  Recriar um PV perde a situação original (9 Atendido / 18 Venda Agenciada) → restaurar
  manualmente no painel se necessário.
- **PV com NF vinculada NÃO pode ser recriado**: `lancar-contas` → **400 erro 62**;
  `DELETE /pedidos/vendas/{id}` → **400 erro 64** ("possui nota(s) fiscal(is) lançada(s)").
  Só destrava cancelando a NF (ação fiscal, painel/contador); alternativa sem cancelar =
  criar CARs manuais (`POST /contas/receber`).
- **Alterar `categoria` de PV com NF vinculada é possível** via `PUT /pedidos/vendas/{id}`
  (body completo): categoria muda e situação/NF/parcelas/itens permanecem. O bloqueio de
  edição não impede a categoria.
- **Ao recriar, remapear parcelas de formas inativas** para uma forma ativa (`destino`=1).
- **Item `desconto` é PERCENTUAL (POST e GET); `GET item.valor` é o valor LÍQUIDO**: para
  recriar, enviar `valor` bruto = `liquido / (1 - desconto/100)` e `desconto` = percentual
  do GET.
- Utilitário: `scripts/recreate_pv.py --backup <pv.json> --vendedor <id> [--execute]`
  (dry-run por padrão; valida total antes de aplicar).

## Vendedores

- **Vendedores não têm `POST` na API v3** (`POST /vendedores` → 404). Criar vendedor só via
  painel (rota `vendedores.php#transform/{contatoId}` + Salvar). `GET /vendedores` omite
  inativos; `GET /vendedores/{id}` traz `contato.situacao` (`A`/`I`/`E`). Inativar/ativar
  também é pelo painel (editar vendedor → Situação).
