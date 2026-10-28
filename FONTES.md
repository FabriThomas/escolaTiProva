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

* **Subtotal Pizzas:**
  `subtotal_pizzas_centavos` = sum of (`valor_unitario` of item size * `quantidade`) across all items.
  * `broto` = `PRECO_BROTO_CENTAVOS`
  * `grande` = `PRECO_GRANDE_CENTAVOS`

* **Promotional Discount:**
  `desconto_centavos` = `ceil(subtotal_pizzas_centavos * DESCONTO_PROMO_PERCENTUAL / 100)`
  * Rounded up (ceiling) in cents.
  * Incides strictly on pizzas, never on delivery fees or tips.

* **Delivery Fee:**
  * When `tipo = "entrega"`: `taxa_entrega_centavos = TAXA_ENTREGA_CENTAVOS`
  * When `tipo = "balcao"` or `tipo = "mesa"`: `taxa_entrega_centavos = 0`

* **Loyalty Discount:**
  * If eligible (every 5 delivered orders): `desconto_fidelidade_centavos = PRECO_BROTO_CENTAVOS`
  * Otherwise: `desconto_fidelidade_centavos = 0`

* **Order Total:**
  `total_centavos` = `max(0, subtotal_pizzas_centavos - desconto_centavos + taxa_entrega_centavos - desconto_fidelidade_centavos)`
  * Always an integer; never negative.

### Tab Closure Formulas

* **Tab Subtotal:**
  `subtotal_centavos` = sum of `total_centavos` of all delivered orders linked to the tab.

* **Tip Calculation:**
  `gorjeta_centavos` = `ceil(subtotal_centavos * tip_percentage / 100)`
  * Uses `gorjeta_percentual` from request body if supplied; defaults to `GORJETA_PADRAO_PERCENTUAL` if omitted.
  * Uses the same ceiling rounding as promotional discounts.

* **Tab Final Total:**
  `total_centavos` = `subtotal_centavos + gorjeta_centavos`

* **Bill Splitting Division:**
  When `dividir_em` (`N`, between 2 and 10) is supplied:
  * Generates an array `parcelas_centavos` with exactly `N` integers.
  * Sum of elements equals `total_centavos` (`subtotal_centavos + gorjeta_centavos`).
  * Base chunk `B` = `floor(total_centavos / N)`
  * Remainder `R` = `total_centavos % N`
  * The first `R` chunks receive `B + 1`, and the remaining `N - R` chunks receive `B`.
  * Difference between the highest and lowest chunk is at most 1 cent.

### Daily Metrics Formulas

* **Gross Revenue:**
  `faturamento_centavos` = sum of `total_centavos` across all non-cancelled orders received on the target date.
  * Tips are excluded from `faturamento_centavos` (tips go to waitstaff, not the house).

* **Average Ticket:**
  * When `total_pedidos > 0`: `ticket_medio_centavos = round_half_up(faturamento_centavos / total_pedidos)` (rounding 0.5 upwards).
  * When `total_pedidos == 0`: `ticket_medio_centavos = 0` (returns 0, not an error).

---

## 2. Order Lifecycle & Business Logic

### State Machine
```
[recebido] ---> [preparo] ---> [pronto] ---> [entregue] (terminal)
    |
    +---> [cancelado] (terminal)
```
* **Status Progression:** `recebido` -> `preparo` -> `pronto` -> `entregue`.
* **Terminal Status:** `entregue` is immutable. Attempting to advance from `entregue` returns `409 pedido_ja_finalizado`.
* **Cancellations:** Only orders in `recebido` can be cancelled (`200 OK`). Attempting to cancel an order in `preparo`, `pronto`, or `entregue` returns `409 pedido_nao_cancelavel`.

### Active Order Concurrency Rules
* For `tipo = "entrega"` and `tipo = "balcao"`, a client may have at most **one** active order (`recebido`, `preparo`, or `pronto`). Attempting to create another returns `409 pedido_em_aberto`.
* For `tipo = "mesa"`, this constraint is bypassed: concurrency is scoped to the tab (`comanda`), which can accumulate multiple simultaneous active orders.

### Loyalty Stamp Card Protocol
* Every 5 delivered orders (`entregue`) under a client name (across any order type; cancelled orders excluded) grants `desconto_fidelidade_centavos = PRECO_BROTO_CENTAVOS` on their next order.
* The reward applies at creation. Cancelling a rewarded order while in `recebido` restores the client's eligibility.
* For `tipo = "mesa"`, stamps accrue to the individual client name, but the loyalty discount applies to the specific order, not to the collective tab.

### Menu & Flavor Availability
* The menu is open: any flavor string (`2..30` characters) is dynamically registered and initialized as available (`disponivel: true`).
* Case-insensitive matching is enforced (e.g., `Mussarela` matches `mussarela`).
* If an order contains any item whose flavor is currently marked `disponivel: false`, order creation fails with `409 sabor_indisponivel`, and no mutations are persisted.

---

## 3. Request Validation Precedence Matrix

When evaluating `POST /pedidos`, validations must be executed in the following priority:
1. **Schema & Format Validation (`422 Unprocessable Entity`)**: Client string length, item array bounds, valid size/quantity/type, valid `recebido_em` timestamp.
2. **Table Tab Validation (`422 Unprocessable Entity`)**: If `tipo = "mesa"`, verify `comanda_id` presence, existence, and open status. If `tipo != "mesa"`, verify `comanda_id` is absent.
3. **Menu Availability Check (`409 Conflict`)**: Verify all requested flavors are `disponivel: true`.
4. **Client Concurrency Check (`409 Conflict`)**: For `entrega` and `balcao`, verify client has no orders in `recebido`, `preparo`, or `pronto`.

---

## 4. Use Case Specifications (UC Cross-Reference)

### UC1: Create Order
* **Endpoint:** `POST /pedidos`
* **Cross-References:** UC7, UC8, UC10, UC14, UC16
* **Request Body:**
  ```json
  {
    "cliente": "Ana Souza",
    "itens": [
      {
        "sabor": "mussarela",
        "tamanho": "grande",
        "quantidade": 2
      }
    ],
    "tipo": "entrega",
    "comanda_id": null,
    "recebido_em": "2026-10-28T20:00:00-03:00"
  }
  ```
* **Payload Constraints:**
  * `cliente`: string, `2..60` chars.
  * `itens`: array, `1..20` elements.
  * `itens[].sabor`: string, `2..30` chars.
  * `itens[].tamanho`: `"broto"` | `"grande"`.
  * `itens[].quantidade`: integer, `1..10`.
  * `tipo`: `"entrega"` | `"balcao"` | `"mesa"`.
  * `comanda_id`: integer, required when `tipo = "mesa"`, forbidden otherwise.
  * `recebido_em`: optional ISO-8601 string with timezone offset (defaults to server current time).
* **Success Response (`201 Created`):**
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
    "recebido_em": "2026-10-28T20:00:00-03:00",
    "status": "recebido",
    "subtotal_pizzas_centavos": 10000,
    "taxa_entrega_centavos": 500,
    "desconto_centavos": 1000,
    "desconto_fidelidade_centavos": 0,
    "total_centavos": 9500
  }
  ```

### UC2: Advance Order Status
* **Endpoint:** `POST /pedidos/{id}/status`
* **Success Response (`200 OK`):**
  ```json
  {
    "id": 1,
    "status": "preparo"
  }
  ```
* **Transitions:** `recebido` -> `preparo` -> `pronto` -> `entregue`.

### UC3: List Active Orders
* **Endpoint:** `GET /pedidos/ativos`
* **Behavior:** Returns an array of orders in status `recebido`, `preparo`, or `pronto`, sorted by newest first.
* **Success Response (`200 OK`):** Array of order objects.

### UC4: Daily Report
* **Endpoint:** `GET /relatorios/diario?data=AAAA-MM-DD`
* **Success Response (`200 OK`):**
  ```json
  {
    "data": "2026-10-28",
    "total_pedidos": 12,
    "faturamento_centavos": 123400,
    "ticket_medio_centavos": 10284
  }
  ```
* **Behavior:** Filters by date on `recebido_em`. Only non-cancelled orders count. Days with zero orders return `total_pedidos: 0`, `faturamento_centavos: 0`, `ticket_medio_centavos: 0`.

### UC5: Cancel Order
* **Endpoint:** `POST /pedidos/{id}/cancelamento`
* **Cross-References:** UC4, UC8, UC16
* **Behavior:** Allowed only when order is in `recebido`. Cancelling removes the order from daily reporting, frees the client to order again, and re-credits any redeemed loyalty reward.
* **Success Response (`200 OK`):**
  ```json
  {
    "id": 1,
    "status": "cancelado"
  }
  ```

### UC6: Client Order History
* **Endpoint:** `GET /pedidos?cliente={nome}`
* **Behavior:** Returns all orders across all statuses for the given client, sorted newest first. Returns `[]` if client has no history.
* **Success Response (`200 OK`):** Array of order objects.

### UC7: Promotional Discount
* **Cross-References:** UC1, UC10
* **Behavior:** Encapsulates the formula `ceil(subtotal * DESCONTO_PROMO_PERCENTUAL / 100)` evaluated strictly against pizza costs.

### UC8: Single Active Order Constraint
* **Cross-References:** UC1, UC5
* **Behavior:** Rejects `POST /pedidos` with `409 pedido_em_aberto` if an `entrega` or `balcao` customer has an order in `recebido`, `preparo`, or `pronto`.

### UC9: Open Table Tab
* **Endpoint:** `POST /mesas/{numero}/comandas`
* **Success Response (`201 Created`):**
  ```json
  {
    "id": 1,
    "mesa": 7,
    "aberta_em": "2026-10-28T20:00:00-03:00",
    "status": "aberta"
  }
  ```
* **Constraints:** `numero` must be within `1..50`. Table must not have an already active open tab (`409 mesa_ocupada`).

### UC10: Table Order Creation
* **Cross-References:** UC1, UC2, UC9
* **Behavior:** Extends UC1 for dine-in tables (`tipo = "mesa"`). Requires a valid, open `comanda_id`. Sets `taxa_entrega_centavos = 0`. Promotion discounts apply normally. Bypasses UC8 concurrency.

### UC11: Close Table Tab
* **Endpoint:** `POST /comandas/{id}/fechamento`
* **Cross-References:** UC4, UC15
* **Request Body (Optional):**
  ```json
  {
    "gorjeta_percentual": 10,
    "dividir_em": 3
  }
  ```
* **Success Response (`200 OK`):**
  ```json
  {
    "id": 1,
    "mesa": 7,
    "aberta_em": "2026-10-28T19:30:00-03:00",
    "fechada_em": "2026-10-28T20:30:00-03:00",
    "pedidos_entregues": 3,
    "subtotal_centavos": 30500,
    "gorjeta_centavos": 3050,
    "total_centavos": 33550,
    "parcelas_centavos": [11184, 11183, 11183]
  }
  ```
* **Constraints:** Fails with `409 comanda_com_pedidos_abertos` if any order linked to the tab is still in `recebido`, `preparo`, or `pronto`. Fails with `409 comanda_ja_fechada` if tab is already closed.

### UC12: List Open Tabs
* **Endpoint:** `GET /comandas/abertas`
* **Behavior:** Returns all open tabs sorted FIFO (oldest first: `aberta_em` ascending).
* **Success Response (`200 OK`):** Array of tab objects.

### UC13: Table Tab History
* **Endpoint:** `GET /mesas/{numero}/comandas`
* **Behavior:** Returns all tabs (both open and closed) for a table, sorted newest first. Returns `[]` if no tabs exist. Validates `numero` in `1..50`.
* **Success Response (`200 OK`):** Array of tab objects.

### UC14: Menu & Availability Management
* **Endpoints:**
  * `PUT /cardapio/{sabor}` — Body: `{"disponivel": false}` -> Updates availability (case-insensitive name match).
    * **Success Response (`200 OK`):** `{"sabor": "catupiry", "disponivel": false}`
  * `GET /cardapio` -> Returns all known flavors sorted alphabetically with their current availability status.
    * **Success Response (`200 OK`):** Array of flavor objects.

### UC15: Bill Splitting
* **Cross-References:** UC11
* **Behavior:** Handles optional `dividir_em` (`2..10`) during tab closure. Calculates integer breakdown for `parcelas_centavos`. If omitted, the field is omitted from the response.

### UC16: Loyalty Program
* **Cross-References:** UC1, UC5
* **Behavior:** Tracks completed deliveries per client name. Deducts `PRECO_BROTO_CENTAVOS` on every 6th order after 5 delivered orders. Applies floor at zero.

---

## 5. Comprehensive Error Contract Matrix

| Condition | Status Code | Response Body | Cross-Ref UC |
| :--- | :---: | :--- | :--- |
| `cliente` missing or outside `2..60` characters | **422** | `{"erro": "cliente_invalido"}` | UC1 |
| `itens` empty, `> 20`, invalid size, or `quantidade` outside `1..10` | **422** | `{"erro": "itens_invalidos"}` | UC1 |
| `tipo` not in `entrega`, `balcao`, or `mesa` | **422** | `{"erro": "tipo_invalido"}` | UC1 |
| `tipo = mesa` with invalid/closed `comanda_id`, or `comanda_id` present when `tipo != mesa` | **422** | `{"erro": "comanda_invalida"}` | UC1, UC10 |
| `recebido_em` invalid ISO-8601 format | **422** | `{"erro": "recebido_invalido"}` | UC1 |
| Query param `data` outside `AAAA-MM-DD` | **422** | `{"erro": "data_invalida"}` | UC4 |
| Table number outside range `1..50` | **422** | `{"erro": "mesa_invalida"}` | UC9, UC13 |
| `gorjeta_percentual` outside range `0..30` | **422** | `{"erro": "gorjeta_invalida"}` | UC11 |
| `dividir_em` outside range `2..10` | **422** | `{"erro": "divisao_invalida"}` | UC11, UC15 |
| Order ID not found | **404** | `{"erro": "pedido_nao_encontrado"}` | UC2, UC5 |
| Tab (`comanda`) ID not found | **404** | `{"erro": "comanda_nao_encontrada"}` | UC11 |
| Advancing status of an already delivered (`entregue`) order | **409** | `{"erro": "pedido_ja_finalizado"}` | UC2 |
| Cancelling an order in `preparo`, `pronto`, or `entregue` | **409** | `{"erro": "pedido_nao_cancelavel"}` | UC5 |
| Creating `entrega`/`balcao` order for client with existing active order | **409** | `{"erro": "pedido_em_aberto"}` | UC1, UC8 |
| Creating an order containing an unavailable flavor (`disponivel = false`) | **409** | `{"erro": "sabor_indisponivel"}` | UC1, UC14 |
| Opening a tab on a table that is already occupied | **409** | `{"erro": "mesa_ocupada"}` | UC9 |
| Attempting to close an already closed tab | **409** | `{"erro": "comanda_ja_fechada"}` | UC11 |
| Attempting to close a tab with orders still in `recebido`, `preparo`, or `pronto` | **409** | `{"erro": "comanda_com_pedidos_abertos"}` | UC11 |
