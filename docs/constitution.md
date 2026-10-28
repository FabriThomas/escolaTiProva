### leis gerais
payment is calculated in cents;
fees are calculated as follows: delivery fee is TAXA_ENTREGA_CENTAVOS when tipo is "entrega", and 0 for both "balcao" and "mesa". For mesa, service costs are handled on tab closure via uc11, including tip. The tip is calculated rounding up with ceil.
promos are calculated as subtotal x "DESCONTO_PROMO_PERCENTUAL" / 100, rounding up (ceil), always on the pizza only, NOT on the tip/tax.
"total_centavos" is the subtotal - discount + tax, always as an int, never float.
for the body: client "cliente" is a string 2..60, itens "itens" is an array 1..20, each having toppings "sabor" as a string 2..30, size "tamanho" is "broto"|"grande" only, "quantidade" is int 1..10, type "tipo" is "entrega"|"balcao"|"mesa".
"tipo" = "mesa" has "comanda_id" (int) demanded on body, pointing to a tab that is open, if nonexistant or closed return 422. if the "comanda_id" =/ mesa, also 422. For 201 requests, comanda_id is the link, null otherwise.
body accepts "recebido_em" as an optional, using ISO-8601 with a fuse, otherwise define it as current time from the server. If filled wrong, 422.
the order "pedido" must go through those steps: "recebido"->"preparo"->"pronto"->"entregue", with "entregue" being terminal, returning 409 if already in entregue.
for active orders in a GET /pedidos/ativos, the ones that sohuld be returned are "recebido","preparo" or "pronto", sorted by newest.
for a daily report, the order must be: in the correct date on "recebido_em", and cannot be cancelled. "faturamento_centavos" = sum of total_centavos, which excludes tips, as they are for the waiter. "ticket_medio_centavos" = "faturamento_centavos"/"total_pedidos", rounding up from 0.5, and if no orders, then it returns as zero, not an error.
cancelled orders are only those in "recebido", which is the initial state in which preparations haven't happened, as said before they won't be in the daily report and they deaccoplate client from an order (uc8). Cancelling an order in "recebido" returns 200, while cancelling an order in "preparo", "pronto" or "entregue" returns 409 pedido_nao_cancelavel.
"desconto_centaos" = ceil(subtotal x DESCONTO_PROMO_PERCENTUAL / 100), always only on top of the pizzas, excluding fees. The fee comes in the total, as an example considering pct 10, subtotal 10000 = 1000, 9999 = 1000, 333 =34.
A client can onl have one order, returning 409 if the client has an order in "recebido", "preparo" or "pronto", but only for "entrega" and "balcao", as "mesa" considers the tab the owner of the order and thus can have multiple orders.
To open a tab, it must return 409 in case a table is occupied, which it will be until closure via finished status, this type of order waivers the fee, promos are applied as normal. One tab can have multipole orders, each with its own status. If table is outside 1..50, retrn 422.
To close a tab, it cannot have any orders in "recebido", "preparo" or "pronto" (all must be "entregue" or "cancelado"), returning 409 in case of order in "recebido", "preparo" or "pronto", closure on a closed tab is also a 409. The tab considers only "entregue", ignoring cancellations, with "subtotal_centavos" = sum of the "total_centavos" of each order. In case the country has a customary tip amount, you can set the default tip amount with "GORJETA_PADRAO_PERCENTUAL" as an int 0..30, if the tip is already selected by the client then "gorjeta_percentual" as an int 0..30 ignores GORJETA_PADRAO_PERCENTUAL. If the tip is outside of the 0..30 range, then return a 422. Tip is calcualted as "gorjeta_centavos" = ceil(subtotal x pct / 100), with the same rounding as the discount from promos. total_centavos = subtotal + tip. The tip does NOT go in faturamento_centavos, and body can include "parcelas_centavos" in case of a split bill.
When listing open tabs, return a 200 with an array of the open tabs, via FIFO.
When getting the history of a table via GET /mesas/{number}/comandas, returna a 200 with the array of all tabs, open or closed, sorted by newest. If there's no tab, then return an empty array. If number is outside of 1..50, return 422.
menu "cardapio" is open, any flavor between 2..30 characters is accepted on orders and starts as avaible "disponivel". The kitchen marks whats missing with PUT /cardapio/{sabor} sending disponivel false, which returns 200 with the flavor in lower case matching, and GET /cardapio returns 200 with all known flavors that either appeared on an order or were explicitly set, sorted alphabetically with their availability. If an order has an item with an indisponivel flavor, it returns 409 sabor_indisponivel and nothing is saved. Precedence is format validation 422 -> comanda 422 (if mesa) -> flavor indisponivel 409 -> active order 409.
For bill splitting on tab closure uc11, body can optionally take "dividir_em" as int 2..10. If present, it returns "parcelas_centavos" with an array of exactly that amount of ints, whose sum equals total_centavos (subtotal + tip), difference between highest and lowest chunk is at most 1 cent, and the remainder of integer division goes to the first chunks. If out of 2..10 returns 422 divisao_invalida, and if absent the field doesnt show up.
For loyalty stamp card, every 5 delivered orders from a client (any type, cancelled orders dont count), the next order gets "desconto_fidelidade_centavos" equal to PRECO_BROTO_CENTAVOS. On 201 of the rewarded order it shows the discount amount, otherwise 0. Applied as total_centavos = subtotal - promo discount + fee - loyalty discount, floored at 0 so it never goes negative. It is single use and happens on creation, so cancelling the rewarded order while in recebido gives the reward back to the client making them eligible again. Table orders count stamps normally by client name, but the loyalty discount applies to the order itself, not the tab.

For error status:
| Situação | Status | Body |
| --- | --- | --- |
| Cliente ausente ou fora de 2..60 caracteres | 422 | `{"erro": "cliente_invalido"}` |
| Itens vazio, > 20, tamanho inválido ou quantidade fora de 1..10 | 422 | `{"erro": "itens_invalidos"}` |
| Tipo fora de `entrega\|balcao\|mesa` | 422 | `{"erro": "tipo_invalido"}` |
| `tipo = mesa` sem `comanda_id` válido e aberto (ou `comanda_id` com outro tipo) | 422 | `{"erro": "comanda_invalida"}` |
| `recebido_em` fora de ISO-8601 | 422 | `{"erro": "recebido_invalido"}` |
| `data` fora de `AAAA-MM-DD` | 422 | `{"erro": "data_invalida"}` |
| Número de mesa fora de 1..50 | 422 | `{"erro": "mesa_invalida"}` |
| `gorjeta_percentual` fora de 0..30 | 422 | `{"erro": "gorjeta_invalida"}` |
| `dividir_em` fora de 2..10 | 422 | `{"erro": "divisao_invalida"}` |
| Pedido inexistente | 404 | `{"erro": "pedido_nao_encontrado"}` |
| Comanda inexistente | 404 | `{"erro": "comanda_nao_encontrada"}` |
| Avançar pedido já entregue | 409 | `{"erro": "pedido_ja_finalizado"}` |
| Cancelar pedido em preparo/pronto/entregue | 409 | `{"erro": "pedido_nao_cancelavel"}` |
| Criar pedido com cliente já tendo pedido ativo | 409 | `{"erro": "pedido_em_aberto"}` |
| Criar pedido com sabor indisponível | 409 | `{"erro": "sabor_indisponivel"}` |
| Abrir comanda em mesa ocupada | 409 | `{"erro": "mesa_ocupada"}` |
| Fechar comanda já fechada | 409 | `{"erro": "comanda_ja_fechada"}` |
| Fechar comanda com pedidos ainda abertos | 409 | `{"erro": "comanda_com_pedidos_abertos"}` |
