# Pizzeria Domain Functional Specification (`spec.md`)

**Base Port:** 8004  
**Base URL:** `http://localhost:8004`  
**Storage Architecture:** Ephemeral / In-Memory State (no persistent database assumptions)  
**Monetary Representation:** Integer cents (`centavos`). Floating-point arithmetic is strictly prohibited across all operations and serialization.  
**Exam Track:** `exams/2026/track-04-especificacao-sdd-pizzaria`

---

## 1. Domain Constants & Active Configuration

| Constant | Value | Description |
| :--- | :--- | :--- |
| `PRECO_BROTO_CENTAVOS` | `3250` | Unit price for small pizza (`broto`) in cents (R$ 32,50). |
| `PRECO_GRANDE_CENTAVOS` | `5500` | Unit price for large pizza (`grande`) in cents (R$ 55,00). |
| `TAXA_ENTREGA_CENTAVOS` | `500` | Delivery fee applied exclusively when `tipo = "entrega"` (R$ 5,00). |
| `DESCONTO_PROMO_PERCENTUAL` | `15` | Promotional discount percentage over pizza subtotal (`15%`). |
| `GORJETA_PADRAO_PERCENTUAL` | `15` | Default service charge tip percentage (`15%`). |
| `PORTA_SERVICO` | `8004` | Listening HTTP service port. |

---

## 2. Global Formulas & Calculations

1. **Pizza Subtotal (`subtotal_pizzas_centavos`):**
   $$\text{subtotal\_pizzas\_centavos} = \sum (\text{valor\_unitario\_centavos} \times \text{quantidade})$$
   - `broto` = `3250`
   - `grande` = `5500`

2. **Promotional Discount (`desconto_centavos`):**
   $$\text{desconto\_centavos} = \lceil \text{subtotal\_pizzas\_centavos} \times 15 / 100 \rceil$$
   *(Applies strictly to pizzas; never to delivery fees or tips).*

3. **Delivery Fee (`taxa_entrega_centavos`):**
   - When `tipo = "entrega"`: `500`
   - When `tipo = "balcao"` or `tipo = "mesa"`: `0`

4. **Loyalty Discount (`desconto_fidelidade_centavos`):**
   - Granted on every 6th order after 5 cumulative delivered (`entregue`) orders under the customer's name.
   - Value: `3250` (`PRECO_BROTO_CENTAVOS`). Otherwise: `0`.

5. **Order Total (`total_centavos`):**
   $$\text{total\_centavos} = \max(0, \text{subtotal\_pizzas\_centavos} - \text{desconto\_centavos} + \text{taxa\_entrega\_centavos} - \text{desconto\_fidelidade\_centavos})$$
   - Always an integer in cents; never negative.

6. **Tab Subtotal (`subtotal_centavos`):**
   $$\text{subtotal\_centavos} = \sum \text{total\_centavos of all delivered orders linked to the tab}$$

7. **Tab Tip (`gorjeta_centavos`):**
   $$\text{gorjeta\_centavos} = \lceil \text{subtotal\_centavos} \times \text{gorjeta\_percentual} / 100 \rceil$$
   - Uses `gorjeta_percentual` from request body if supplied; defaults to `15` (`GORJETA_PADRAO_PERCENTUAL`) if omitted.

8. **Tab Final Total (`total_centavos`):**
   $$\text{total\_centavos} = \text{subtotal\_centavos} + \text{gorjeta\_centavos}$$

9. **Bill Splitting Division (`parcelas_centavos`):**
   When `dividir_em = N` ($2 \le N \le 10$) is provided:
   - Total to divide: $\text{Total} = \text{subtotal\_centavos} + \text{gorjeta\_centavos}$
   - Base share: $\text{Base} = \lfloor \text{Total} / N \rfloor$
   - Remainder: $\text{Remainder} = \text{Total} \pmod N$
   - The first $\text{Remainder}$ shares receive $\text{Base} + 1$, and the remaining $N - \text{Remainder}$ shares receive $\text{Base}$.
   - Array length is strictly $N$, and $\sum \text{parcelas\_centavos} = \text{Total}$.

10. **Daily Report Metrics:**
    - Gross revenue: $\text{faturamento\_centavos} = \sum \text{total\_centavos}$ across all non-cancelled orders received on the date (tips excluded).
    - Average ticket:
      - If $\text{total\_pedidos} > 0$: $\text{ticket\_medio\_centavos} = \lfloor (\text{faturamento\_centavos} / \text{total\_pedidos}) + 0.5 \rfloor$ (half-up rounding).
      - If $\text{total\_pedidos} == 0$: $\text{ticket\_medio\_centavos} = 0$.

---

## 3. Order Lifecycle & Validation Pipeline

### State Machine
```
[recebido] ---> [preparo] ---> [pronto] ---> [entregue] (terminal)
    |
    +---> [cancelado] (terminal)
```

### Precedence Matrix for `POST /pedidos`
When evaluating a request to create an order, validations must be executed in this strict order:
1. **HTTP 422 (Schema & Boundary):**
   - `cliente`: Missing or length outside `2..60` characters $\rightarrow$ `{"erro": "cliente_invalido"}`
   - `itens`: Empty array, length $> 20$, invalid size (not `"broto"` or `"grande"`), or quantity outside `1..10` $\rightarrow$ `{"erro": "itens_invalidos"}`
   - `tipo`: Value not in `["entrega", "balcao", "mesa"]` $\rightarrow$ `{"erro": "tipo_invalido"}`
   - `recebido_em`: Present but not a valid ISO-8601 string with timezone offset $\rightarrow$ `{"erro": "recebido_invalido"}`
2. **HTTP 422 (Tab Association):**
   - `tipo == "mesa"` and (`comanda_id` is missing, does not exist, or points to a closed tab) $\rightarrow$ `{"erro": "comanda_invalida"}`
   - `tipo != "mesa"` and `comanda_id` is passed (not null) $\rightarrow$ `{"erro": "comanda_invalida"}`
3. **HTTP 409 (Menu Availability):**
   - Any flavor in `itens` currently marked `disponivel == false` $\rightarrow$ `{"erro": "sabor_indisponivel"}`
4. **HTTP 409 (Customer Active Order Concurrency):**
   - For `tipo = "entrega"` and `tipo = "balcao"`, if the client already has an order in status `"recebido"`, `"preparo"`, or `"pronto"` $\rightarrow$ `{"erro": "pedido_em_aberto"}`

---

## 4. Acceptance Criteria by Use Case

### UC1 & UC7: Create Order & Promotional Calculation
#### Scenario: Successfully create delivery order with promo discount
- **Given** customer `"Ana Souza"` has no open orders
- **And** the flavor `"mussarela"` is available
- **When** a `POST /pedidos` request is received with:
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
    "tipo": "entrega"
  }
  ```
- **Then** the response status code is `201 Created`
- **And** the response body matches:
  - `subtotal_pizzas_centavos`: `11000` ($2 \times 5500$)
  - `taxa_entrega_centavos`: `500`
  - `desconto_centavos`: `1650` ($\lceil 11000 \times 0.15 \rceil$)
  - `desconto_fidelidade_centavos`: `0`
  - `total_centavos`: `9850` ($11000 - 1650 + 500$)
  - `status`: `"recebido"`
  - `comanda_id`: `null`
  - `recebido_em`: valid ISO-8601 timestamp with `-03:00` offset

#### Scenario: Optional `recebido_em` testing hook
- **When** `POST /pedidos` includes `"recebido_em": "2026-10-28T20:00:00-03:00"`
- **Then** the created order adopts this exact timestamp instead of the current system clock
- **When** `POST /pedidos` includes an unparseable `"recebido_em": "invalid-date"`
- **Then** response status is `422 Unprocessable Entity` with `{"erro": "recebido_invalido"}`

---

### UC2: Advance Order Status
#### Scenario: Standard lifecycle progression
- **Given** an order exists with status `"recebido"`
- **When** `POST /pedidos/{id}/status` is requested
- **Then** the response status is `200 OK` and `status` transitions to `"preparo"`
- **When** `POST /pedidos/{id}/status` is requested again
- **Then** `status` transitions to `"pronto"`
- **When** `POST /pedidos/{id}/status` is requested again
- **Then** `status` transitions to `"entregue"`

#### Scenario: Advancing terminal status
- **Given** an order has status `"entregue"`
- **When** `POST /pedidos/{id}/status` is requested
- **Then** response status is `409 Conflict` with `{"erro": "pedido_ja_finalizado"}`

---

### UC3: List Active Orders
#### Scenario: Retrieve all uncompleted orders
- **Given** existing orders:
  - Order 1: `"entregue"`
  - Order 2: `"recebido"`
  - Order 3: `"preparo"`
  - Order 4: `"cancelado"`
  - Order 5: `"pronto"`
- **When** `GET /pedidos/ativos` is requested
- **Then** response status is `200 OK`
- **And** the returned array contains Order 5, Order 3, and Order 2 sorted newest first
- **And** Order 1 and Order 4 are excluded

---

### UC4: Daily Report
#### Scenario: Accurate daily metric calculation
- **Given** date `"2026-10-28"` has two non-cancelled orders:
  - Order A: `total_centavos: 10000`
  - Order B: `total_centavos: 5500`
- **And** one cancelled order with `total_centavos: 9000`
- **When** `GET /relatorios/diario?data=2026-10-28` is requested
- **Then** response status is `200 OK`
- **And** payload contains:
  ```json
  {
    "data": "2026-10-28",
    "total_pedidos": 2,
    "faturamento_centavos": 15500,
    "ticket_medio_centavos": 7750
  }
  ```

#### Scenario: Date with zero orders
- **When** `GET /relatorios/diario?data=2026-01-01` is requested for a date with no orders
- **Then** response status is `200 OK`
- **And** payload contains:
  ```json
  {
    "data": "2026-01-01",
    "total_pedidos": 0,
    "faturamento_centavos": 0,
    "ticket_medio_centavos": 0
  }
  ```

---

### UC5: Cancel Order
#### Scenario: Cancellation allowed in initial state
- **Given** an order in status `"recebido"`
- **When** `POST /pedidos/{id}/cancelamento` is requested
- **Then** response status is `200 OK` with `{"id": id, "status": "cancelado"}`
- **And** the order is excluded from UC4 daily reporting
- **And** customer active order constraint (UC8) is released

#### Scenario: Cancellation blocked in advanced states
- **Given** an order in status `"preparo"`, `"pronto"`, or `"entregue"`
- **When** `POST /pedidos/{id}/cancelamento` is requested
- **Then** response status is `409 Conflict` with `{"erro": "pedido_nao_cancelavel"}`

---

### UC6: Client Order History
#### Scenario: Historical retrieval by customer
- **When** `GET /pedidos?cliente=Ana%20Souza` is requested
- **Then** returns `200 OK` with an array of all orders (regardless of status) placed by Ana Souza, newest first
- **When** `GET /pedidos?cliente=Desconhecido` is requested for a customer with no orders
- **Then** returns `200 OK` with `[]`

---

### UC8: Single Active Order Constraint
#### Scenario: Blocking concurrent active orders for counter/delivery
- **Given** client `"Bruno"` has an order in status `"recebido"`
- **When** `POST /pedidos` is sent for `"Bruno"` with `tipo: "entrega"` or `tipo: "balcao"`
- **Then** response status is `409 Conflict` with `{"erro": "pedido_em_aberto"}`
- **When** Bruno's previous order advances to `"entregue"` or `"cancelado"`
- **Then** the new order is accepted with `201 Created`

#### Scenario: Dine-in orders exempt from customer concurrency check
- **Given** client `"Bruno"` has an order in status `"recebido"` linked to a table tab
- **When** `POST /pedidos` is sent for `"Bruno"` with `tipo: "mesa"` and valid `comanda_id`
- **Then** the order is accepted with `201 Created`

---

### UC9 & UC13: Table Tab Management
#### Scenario: Open a table tab
- **When** `POST /mesas/7/comandas` is requested
- **Then** response status is `201 Created`
- **And** returns `{"id": 1, "mesa": 7, "aberta_em": "<timestamp>", "status": "aberta"}`

#### Scenario: Table already occupied
- **Given** table `7` has an open tab
- **When** `POST /mesas/7/comandas` is requested
- **Then** response status is `409 Conflict` with `{"erro": "mesa_ocupada"}`

#### Scenario: Table number boundary validations
- **When** `POST /mesas/0/comandas` or `POST /mesas/51/comandas` is requested
- **Then** response status is `422 Unprocessable Entity` with `{"erro": "mesa_invalida"}`

#### Scenario: Query table tab history
- **When** `GET /mesas/7/comandas` is requested
- **Then** returns `200 OK` with array of all tabs associated with table 7, sorted newest first

---

### UC10: Table Order Attachment
#### Scenario: Attach order to an open tab
- **Given** comanda `1` is open on table `7`
- **When** `POST /pedidos` is sent with `tipo: "mesa"` and `"comanda_id": 1`
- **Then** response status is `201 Created`
- **And** `taxa_entrega_centavos` is `0`
- **And** `comanda_id` is `1`
- **And** promo discount applies normally

---

### UC11 & UC15: Tab Closure & Bill Splitting
#### Scenario: Closure rejected with unserved orders
- **Given** comanda `1` has an order in status `"preparo"`
- **When** `POST /comandas/1/fechamento` is requested
- **Then** response status is `409 Conflict` with `{"erro": "comanda_com_pedidos_abertos"}`

#### Scenario: Successful closure with custom tip and 3-way split
- **Given** comanda `1` has delivered orders totaling `30500` cents
- **When** `POST /comandas/1/fechamento` is requested with:
  ```json
  {
    "gorjeta_percentual": 10,
    "dividir_em": 3
  }
  ```
- **Then** response status is `200 OK`
- **And** response body matches:
  - `pedidos_entregues`: count of delivered orders
  - `subtotal_centavos`: `30500`
  - `gorjeta_centavos`: `3050` ($\lceil 30500 \times 0.10 \rceil$)
  - `total_centavos`: `33550`
  - `parcelas_centavos`: `[11184, 11183, 11183]`
- **When** `POST /comandas/1/fechamento` is requested again
- **Then** response status is `409 Conflict` with `{"erro": "comanda_ja_fechada"}`

#### Scenario: Split parameter boundary validation
- **When** `POST /comandas/1/fechamento` is sent with `"dividir_em": 1` or `"dividir_em": 11`
- **Then** response status is `422 Unprocessable Entity` with `{"erro": "divisao_invalida"}`

---

### UC12: List Open Tabs
#### Scenario: Query open tabs in FIFO order
- **Given** comanda `1` opened at `19:00` and comanda `2` opened at `19:30`
- **When** `GET /comandas/abertas` is requested
- **Then** response status is `200 OK`
- **And** array contains `[comanda 1, comanda 2]` (oldest first: `aberta_em` ascending)

---

### UC14: Menu & Dynamic Availability
#### Scenario: Flavors dynamically registered and toggleable
- **Given** the flavor `"rucula"` has never been ordered
- **When** `PUT /cardapio/rucula` is requested with `{"disponivel": false}`
- **Then** response status is `200 OK` with `{"sabor": "rucula", "disponivel": false}`
- **When** a `POST /pedidos` is sent containing flavor `"Rucula"` (case-insensitive)
- **Then** response status is `409 Conflict` with `{"erro": "sabor_indisponivel"}`
- **When** `GET /cardapio` is requested
- **Then** returns `200 OK` with all registered flavors sorted alphabetically with their current availability

---

### UC16: Loyalty Stamp Card Protocol
#### Scenario: Automatic loyalty discount on the 6th delivered order
- **Given** client `"Carla"` has exactly `5` orders across any type with status `"entregue"`
- **When** Carla creates a new order for 1 `broto` (`3250` cents) with `tipo = "balcao"`
- **Then** response status is `201 Created`
- **And** `desconto_fidelidade_centavos`: `3250`
- **And** `total_centavos`: `0` ($\max(0, 3250 - 488 + 0 - 3250) = 0$)

#### Scenario: Cancellation restores loyalty eligibility
- **Given** the rewarded order above is still in `"recebido"`
- **When** `POST /pedidos/{id}/cancelamento` is called
- **Then** Carla's loyalty credit is restored, and her next created order receives `desconto_fidelidade_centavos: 3250`

---

## 5. Consolidated Error Status Code Contract

| Condition | HTTP Status | Response Body |
| :--- | :---: | :--- |
| `cliente` missing or outside length `2..60` | **422** | `{"erro": "cliente_invalido"}` |
| `itens` empty, length $> 20$, invalid size, or quantity outside `1..10` | **422** | `{"erro": "itens_invalidos"}` |
| `tipo` not in `["entrega", "balcao", "mesa"]` | **422** | `{"erro": "tipo_invalido"}` |
| `tipo == "mesa"` with invalid/closed tab, or `comanda_id` passed when `tipo != "mesa"` | **422** | `{"erro": "comanda_invalida"}` |
| `recebido_em` invalid ISO-8601 formatting | **422** | `{"erro": "recebido_invalido"}` |
| Query parameter `data` outside `AAAA-MM-DD` | **422** | `{"erro": "data_invalida"}` |
| Table number outside `1..50` | **422** | `{"erro": "mesa_invalida"}` |
| `gorjeta_percentual` outside `0..30` | **422** | `{"erro": "gorjeta_invalida"}` |
| `dividir_em` outside `2..10` | **422** | `{"erro": "divisao_invalida"}` |
| Order ID not found | **404** | `{"erro": "pedido_nao_encontrado"}` |
| Tab ID not found | **404** | `{"erro": "comanda_nao_encontrada"}` |
| Advancing status of an already delivered (`entregue`) order | **409** | `{"erro": "pedido_ja_finalizado"}` |
| Cancelling an order in `preparo`, `pronto`, or `entregue` | **409** | `{"erro": "pedido_nao_cancelavel"}` |
| Creating counter/delivery order for client with existing active order | **409** | `{"erro": "pedido_em_aberto"}` |
| Creating an order containing an unavailable flavor (`disponivel = false`) | **409** | `{"erro": "sabor_indisponivel"}` |
| Opening a tab on an already occupied table | **409** | `{"erro": "mesa_ocupada"}` |
| Attempting to close an already closed tab | **409** | `{"erro": "comanda_ja_fechada"}` |
| Attempting to close a tab with orders still open (`recebido`, `preparo`, `pronto`) | **409** | `{"erro": "comanda_com_pedidos_abertos"}` |
