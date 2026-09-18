# Pendências da migração Bling

> Arquivo de acompanhamento de pendências identificadas durante a revisão da migração.
> Última atualização: 2026-09-16 (removidas pendências concluídas — restam P2, P7 fantasma, P8 e P9).

## P2. Pedido 2026036 — valor de item errado + desconto zerado (BLOQUEADO)

- id_new: `26174580501` | Cliente: Eduardo Fernandes Dias
- ANTIGA: 1 item R$ 7.000, desconto 1.000 → total **6.000**
- NOVA: 1 item R$ 6.000, desconto 0 → total **6.000** (total coincide por acaso)
- Correção necessária: item para R$ 7.000 + desconto 1.000
- **BLOQUEADO para edição via API:** situação "Atendido" (id 9) + nota fiscal vinculada (id `26656601852`)
- Warning do PUT: "Esta venda está bloqueada para edição e foi salva parcialmente"
- Ação: tratamento manual (painel/contador) — estornar NF/baixa antes de editar, ou aceitar como está
- **Observação:** o valor do item está **divergente** — na conta antiga a obra custava R$ 7.000 com desconto de R$ 1.000 (total 6.000); na conta nova o item entrou por **R$ 6.000 com desconto 0**, então o total bate por coincidência, mas o valor registrado não reflete a venda original. Esse valor **não pode ser editado via API** porque o pedido está na situação **"Atendido" (id 9)** e possui **nota fiscal vinculada** (`26656601852`), o que trava a edição dos itens — a API retorna "Esta venda está bloqueada para edição e foi salva parcialmente". Para corrigir seria preciso estornar a NF/baixa antes de editar.
- Status: pendente (requer intervenção manual)

## P7. Pedido de compra 2 "fantasma" — AS, Sem título, 2016 (PENDENTE)

- Pedido de compra nº 2 (id `26174616716`), data 25/06/2026, total **R$ 0**
- Item: "AS, Sem titulo, 2016" (produto `16668720807`)
- **Fornecedor inválido:** contato `18224454621` cujo nome é *"Ref. ao pedido de compra nº 4, Thiago Barros Gráfica (Rio de Janeiro)"* — contato criado a partir de descrição
- **Sem correspondente na conta antiga** (a antiga tinha pedidos 2, 3, 4, 5 = Lazaro, Syl, Thiago, Evandro)
- Suspeita: lixo de migração
- Decisão do usuário (29/08): **adicionar às pendências** — tratar depois
- Status: pendente (avaliar exclusão)

## P8. Anexos em cadastros de clientes/fornecedores — sem suporte na API v3

- O Bling permite anexar arquivos (contratos PDF, imagens, documentos) no cadastro de clientes e fornecedores — feature do painel lançada na **versão 339 (11/02/2026)**
- **A API v3 NÃO expõe esse recurso:** o OpenAPI completo (26/06/2026, 160 paths) não possui endpoint de anexos de contatos; testes de `/contatos/{id}/anexos`, `/anexos`, etc. retornam 404; o GET de contato não traz campo de anexo
- Consequência: anexos da conta antiga **não são migráveis via API** — exigem ação manual (baixar da conta antiga e reenviar na nova pelo painel)
- Ação pendente: confirmar no painel da conta antiga se existem anexos cadastrados e, se houver, migrar manualmente
- Status: pendente (requer intervenção manual / sem API)

## P9. Categorias financeiras de comissão — inativas e uso inconsistente (PENDENTE)

- **Inativas** (não devem ser usadas): `14735928271 Comissionamento Vendas`,
  `14735928294 Comissões` (ambas sob Despesas Operacionais).
- **Ativa correta**: `14730836888 Comissões de Vendedores` (sob Despesas Comerciais).
- **Uso inconsistente:** a comissão aparece lançada em várias categorias → identificar por
  **histórico** (contém "comissão") + categoria (ver relatórios).
- Ação: revisar/consolidar as categorias de comissão e limpar/desativar as inativas.
- Status: pendente (avaliar consolidação)
