# Pizzeria API Specification & Agent Constitution

**Base URL:** `http://localhost:8004`  
**Monetary Representation:** All monetary values are strictly represented as integers in cents (`centavos`). Floating-point representations are strictly prohibited across the API.

---

## 1. Domain Constants & Global Calculation Formulas

### System Parameters & Environment Constants
* `PRECO_BROTO_CENTAVOS`: Unit price for small-sized pizzas (`broto`).
* `PRECO_GRANDE_CENTAVOS`: Unit price for large-sized pizzas (`grande`).
* `TAXA_ENTREGA_CENTAVOS`: Fixed delivery fee applied exclusively when `tipo = "entrega"`.
* `DESCONTO_PROMO_PERCENTUAL`: Promotion percentage (integer). If `0`, discount is always `0`.
* `GORJETA_PADRAO_PERCENTUAL`: Default service tip percentage (integer, `0..30`). `0` represents regions without customary tipping.

### Order Value Formulas
* **Subtotal Pizzas:** `subtotal_pizzas_centavos` = sum of (`valor_unitario` of item size * `quantidade`) across all items (`broto` = `PRECO_BROTO_CENTAVOS`, `grande` = `PRECO_GRANDE_CENTAVOS`).
* **Promotional Discount:** `desconto_centavos = ceil(subtotal_pizzas_centavos * DESCONTO_PROMO_PERCENTUAL / 100)`. Rounded up (ceiling) in cents. Applied strictly to pizzas, never to delivery fees or tips.
* **Delivery Fee:** `taxa_entrega_centavos = TAXA_ENTREGA_CENTAVOS` when `tipo = "entrega"`; otherwise `0`.
* **Loyalty Discount:** If eligible (every 5 delivered orders): `desconto_fidelidade_centavos = PRECO_BROTO_CENTAVOS`; otherwise `0`.
* **Order Total:** `total_centavos = max(0, subtotal_pizzas_centavos - desconto_centavos + taxa_entrega_centavos - desconto_fidelidade_centavos)`. Always an integer; never negative.

### Tab Closure & Metrics Formulas
* **Tab Subtotal:** `subtotal_centavos` = sum of `total_centavos` of all delivered orders linked to the tab.
* **Tip Calculation:** `gorjeta_centavos = ceil(subtotal_centavos * tip_percentage / 100)`. Uses `gorjeta_percentual` if supplied; defaults to `GORJETA_PADRAO_PERCENTUAL`.
* **Tab Final Total:** `total_centavos = subtotal_centavos + gorjeta_centavos`.
* **Bill Splitting Division:** When `dividir_em` (`N`, between 2 and 10) is supplied:
  * Sum of elements equals `total_centavos`.
  * Base chunk `B = floor(total_centavos / N)`, remainder `R = total_centavos % N`.
  * The first `R` chunks receive `B + 1`, remaining `N - R` chunks receive `B`. Difference between highest and lowest chunk is at most 1 cent.
* **Daily Metrics:**
  * Gross revenue: `faturamento_centavos` = sum of `total_centavos` across all non-cancelled orders received on the target date (tips excluded).
  * Average ticket: `round_half_up(faturamento_centavos / total_pedidos)` when `total_pedidos > 0`, else `0`.

---

## 2. Order Lifecycle & Business Logic

### State Machine
`[recebido]` -> `[preparo]` -> `[pronto]` -> `[entregue]` (terminal)  
`[recebido]` -> `[cancelado]` (terminal)

* **Status Progression:** `recebido` -> `preparo` -> `pronto` -> `entregue`.
* **Terminal Status:** `entregue` is immutable. Attempting to advance returns `409 pedido_ja_finalizado`.
* **Cancellations:** Only orders in `recebido` can be cancelled (`200 OK`). Attempting to cancel in other states returns `409 pedido_nao_cancelavel`.
* **Concurrency Rules:** For `entrega` and `balcao`, at most one active order (`recebido`, `preparo`, `pronto`). Violation returns `409 pedido_em_aberto`. `tipo = "mesa"` is exempt.
* **Loyalty Stamp Card:** Every 5 delivered orders (`entregue`) under a client name grants `desconto_fidelidade_centavos = PRECO_BROTO_CENTAVOS` on the next order. Cancelling in `recebido` restores eligibility.
* **Menu Availability:** Dynamic registration (default `disponivel: true`). Case-insensitive matching. Requesting an unavailable flavor returns `409 sabor_indisponivel`.

---

## 3. Request Validation Precedence Matrix

When evaluating `POST /pedidos`, validations must be executed in this priority order:

1. **Schema & Format Validation (`422`)**: Client string length, item array bounds, valid size/quantity/type, valid `recebido_em`.
2. **Table Tab Validation (`422`)**: If `tipo = "mesa"`, verify `comanda_id` presence, existence, and open status. If `tipo != "mesa"`, verify `comanda_id` is absent.
3. **Menu Availability Check (`409`)**: Verify all requested flavors are `disponivel: true`.
4. **Client Concurrency Check (`409`)**: For `entrega`/`balcao`, verify client has no active orders.

---

## 4. Use Case Specifications

### UC1: Create Order (`POST /pedidos`)
* Request constraints: `cliente` (string 2..60), `itens` (array 1..20; `sabor` string 2..30, `tamanho` "broto"|"grande", `quantidade` 1..10), `tipo` ("entrega"|"balcao"|"mesa").
* Optional `recebido_em`: ISO-8601 string with timezone offset (defaults to current time with -03:00).

Sample Request Payload:
```json
{
  "cliente": "Ana Souza",
  "itens": [
    {"sabor": "mussarela", "tamanho": "grande", "quantidade": 2}
  ],
  "tipo": "entrega"
}
```

Sample Success Response (`201 Created`):
```json
{
  "id": 1,
  "cliente": "Ana Souza",
  "itens": [
    {
      "sabor": "mussarela",
      "tamanho": "grande",
      "quantidade": 2,
      "valor_unitario_centavos": 5000
    }
  ],
  "tipo": "entrega",
  "comanda_id": null,
  "status": "recebido",
  "subtotal_pizzas_centavos": 10000,
  "taxa_entrega_centavos": 500,
  "desconto_centavos": 1000,
  "desconto_fidelidade_centavos": 0,
  "total_centavos": 9500
}
```

### UC2: Advance Order Status (`POST /pedidos/{id}/status`)
* Success (`200 OK`): `{"id": 1, "status": "preparo"}`
* Transitions: `recebido` -> `preparo` -> `pronto` -> `entregue`.

### UC3: List Active Orders (`GET /pedidos/ativos`)
* Returns an array of orders in status `recebido`, `preparo`, or `pronto`, sorted newest first.

### UC4: Daily Report (`GET /relatorios/diario?data=AAAA-MM-DD`)
* Success (`200 OK`):
```json
{
  "data": "2026-10-28",
  "total_pedidos": 12,
  "faturamento_centavos": 123400,
  "ticket_medio_centavos": 10284
}
```

### UC5: Cancel Order (`POST /pedidos/{id}/cancelamento`)
* Allowed only when order is in `recebido`.
* Success (`200 OK`): `{"id": 1, "status": "cancelado"}`

### UC6: Client Order History (`GET /pedidos?cliente={nome}`)
* Returns all orders for the client, sorted newest first (`[]` if empty).

### UC7: Promotional Discount
* Formula: `ceil(subtotal * DESCONTO_PROMO_PERCENTUAL / 100)`.

### UC8: Single Active Order Constraint
* Blocks concurrent active `entrega` or `balcao` orders with `409 pedido_em_aberto`.

### UC9: Open Table Tab (`POST /mesas/{numero}/comandas`)
* Table number in range 1..50.
* Success (`201 Created`):
```json
{
  "id": 1,
  "mesa": 7,
  "aberta_em": "2026-10-28T20:00:00-03:00",
  "status": "aberta"
}
```

### UC10: Table Order Creation
* Extends UC1 for `tipo = "mesa"`. Requires an open `comanda_id`. Sets `taxa_entrega_centavos = 0`.

### UC11: Close Table Tab (`POST /comandas/{id}/fechamento`)
* Optional body: `{"gorjeta_percentual": 10, "dividir_em": 3}`.
* Rejects with `409 comanda_com_pedidos_abertos` if any orders are not yet delivered.
* Success (`200 OK`):
```json
{
  "id": 1,
  "mesa": 7,
  "aberta_em": "2026-10-28T19:00:00-03:00",
  "fechada_em": "2026-10-28T21:00:00-03:00",
  "pedidos_entregues": 3,
  "subtotal_centavos": 30500,
  "gorjeta_centavos": 3050,
  "total_centavos": 33550,
  "parcelas_centavos": [11184, 11183, 11183]
}
```

### UC12: List Open Tabs (`GET /comandas/abertas`)
* Returns open tabs sorted FIFO (oldest `aberta_em` first).

### UC13: Table Tab History (`GET /mesas/{numero}/comandas`)
* Returns all tabs for the given table, sorted newest first.

### UC14: Menu & Availability Management
* `PUT /cardapio/{sabor}` with body `{"disponivel": false}` -> returns `200 OK`.
* `GET /cardapio` -> returns all known flavors sorted alphabetically.

### UC15: Bill Splitting
* Splits tab total across `dividir_em` (2..10) participants.

### UC16: Loyalty Program
* Automatic discount equal to `PRECO_BROTO_CENTAVOS` on the 6th order after 5 delivered orders.

---

## 5. Consolidated Error Contract Matrix

| Condition | Status Code | Response Body |
|---|---|---|
| `cliente` missing or outside 2..60 chars | `422` | `{"erro": "cliente_invalido"}` |
| `itens` empty, > 20, invalid size, or qty outside 1..10 | `422` | `{"erro": "itens_invalidos"}` |
| `tipo` not in `entrega`, `balcao`, `mesa` | `422` | `{"erro": "tipo_invalido"}` |
| `tipo = mesa` with invalid tab, or tab present on non-mesa | `422` | `{"erro": "comanda_invalida"}` |
| `recebido_em` invalid ISO-8601 | `422` | `{"erro": "recebido_invalido"}` |
| Query param `data` outside `AAAA-MM-DD` | `422` | `{"erro": "data_invalida"}` |
| Table number outside 1..50 | `422` | `{"erro": "mesa_invalida"}` |
| `gorjeta_percentual` outside 0..30 | `422` | `{"erro": "gorjeta_invalida"}` |
| `dividir_em` outside 2..10 | `422` | `{"erro": "divisao_invalida"}` |
| Order ID not found | `404` | `{"erro": "pedido_nao_encontrado"}` |
| Tab ID not found | `404` | `{"erro": "comanda_nao_encontrada"}` |
| Advancing status of an already delivered order | `409` | `{"erro": "pedido_ja_finalizado"}` |
| Cancelling an order in `preparo`, `pronto`, or `entregue` | `409` | `{"erro": "pedido_nao_cancelavel"}` |
| Creating order with active order already open | `409` | `{"erro": "pedido_em_aberto"}` |
| Creating order with unavailable flavor | `409` | `{"erro": "sabor_indisponivel"}` |
| Opening tab on occupied table | `409` | `{"erro": "mesa_ocupada"}` |
| Closing already closed tab | `409` | `{"erro": "comanda_ja_fechada"}` |
| Closing tab with active unserved orders | `409` | `{"erro": "comanda_com_pedidos_abertos"}` |
