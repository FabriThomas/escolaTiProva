# Tests

## 1. tests/test_math_utils.py (Domain Calculations)

- **test_average_ticket_rounding**
  - **Input A (fractional part >= 0.5 rounds up):**
    - `faturamento_centavos = 100`, `total_pedidos = 3` (100 / 3 = 33.333...) -> **Expected:** 33
    - `faturamento_centavos = 123400`, `total_pedidos = 12` (123400 / 12 = 10283.333...) -> **Expected:** 10284 if exact rounding applied to specification sample (10283.33... in UC4 maps to 10284 via half-up).
    - `faturamento_centavos = 250`, `total_pedidos = 2` (250 / 2 = 125.0) -> **Expected:** 125
    - `faturamento_centavos = 350`, `total_pedidos = 2` (350 / 2 = 175.0) -> **Expected:** 175
    - `faturamento_centavos = 5`, `total_pedidos = 2` (5 / 2 = 2.5) -> **Expected:** 3
  - **Input B (zero orders):**
    - `faturamento_centavos = 0`, `total_pedidos = 0`
    - **Expected Output:** 0

- **test_bill_splitting_remainder_distribution**
  - **Input A:**
    - `total_centavos = 33550`, `dividir_em = 3`
    - **Expected Output:** `parcelas_centavos = [11184, 11183, 11183]`
    - **Assertions:** `sum(parcelas_centavos) == 33550` and `max(parcelas_centavos) - min(parcelas_centavos) <= 1`
  - **Input B:**
    - `total_centavos = 10000`, `dividir_em = 4`
    - **Expected Output:** `parcelas_centavos = [2500, 2500, 2500, 2500]`
  - **Input C:**
    - `total_centavos = 10001`, `dividir_em = 3`
    - **Expected Output:** `parcelas_centavos = [3334, 3334, 3333]`

---

## 2. tests/test_uc1_uc7_uc8_uc10_pedidos.py (Order Creation & Precedence Pipeline)

- **test_create_delivery_order_formula**
  - **Input:**
    - `POST /pedidos`
    - Payload:
      ```json
      {
        "cliente": "Ana Souza",
        "itens": [
          {"sabor": "mussarela", "tamanho": "grande", "quantidade": 2}
        ],
        "tipo": "entrega"
      }
      ```
    - Constants: `PRECO_GRANDE_CENTAVOS = 5500`, `TAXA_ENTREGA_CENTAVOS = 500`, `DESCONTO_PROMO_PERCENTUAL = 15`
  - **Expected Output:**
    - Status: `201 Created`
    - Body matches:
      ```json
      {
        "id": 1,
        "cliente": "Ana Souza",
        "itens": [
          {
            "sabor": "mussarela",
            "tamanho": "grande",
            "quantidade": 2,
            "valor_unitario_centavos": 5500
          }
        ],
        "tipo": "entrega",
        "comanda_id": null,
        "status": "recebido",
        "subtotal_pizzas_centavos": 11000,
        "taxa_entrega_centavos": 500,
        "desconto_centavos": 1650,
        "desconto_fidelidade_centavos": 0,
        "total_centavos": 9850
      }
      ```
      *(where 11000 - 1650 + 500 = 9850)*

- **test_create_order_with_recebido_em_override**
  - **Input:**
    - `POST /pedidos` with `"recebido_em": "2026-10-28T20:00:00-03:00"`
  - **Expected Output:**
    - Status: `201 Created`
    - Body includes: `"recebido_em": "2026-10-28T20:00:00-03:00"`

- **test_validation_precedence_order**
  - **Scenario 1 (Schema format vs. Flavor availability):**
    - Pre-condition: flavor `"palmito"` marked `disponivel: false`.
    - Input: `POST /pedidos` with `"cliente": "A"` (length < 2) and item `"sabor": "palmito"`.
    - Expected Output: Status `422`, Body `{"erro": "cliente_invalido"}`.
  - **Scenario 2 (Comanda validity vs. Flavor availability):**
    - Pre-condition: flavor `"palmito"` marked `disponivel: false`.
    - Input: `POST /pedidos` with `tipo: "mesa"`, `"comanda_id": 9999` (non-existent), and item `"sabor": "palmito"`.
    - Expected Output: Status `422`, Body `{"erro": "comanda_invalida"}`.
  - **Scenario 3 (Flavor availability vs. Active order lock):**
    - Pre-condition: Client `"Bruno"` has an order in status `"recebido"`; flavor `"palmito"` is marked `disponivel: false`.
    - Input: `POST /pedidos` for `"Bruno"` with `tipo: "balcao"` and item `"sabor": "palmito"`.
    - Expected Output: Status `409`, Body `{"erro": "sabor_indisponivel"}`.

- **test_active_order_concurrency_by_type**
  - **Scenario 1 (Delivery/Counter blocked):**
    - Pre-condition: `"Bruno"` has active order #1 (status: `"recebido"`).
    - Input: `POST /pedidos` for `"Bruno"` with `tipo: "entrega"`.
    - Expected Output: Status `409`, Body `{"erro": "pedido_em_aberto"}`.
  - **Scenario 2 (Dine-in allowed concurrent orders):**
    - Pre-condition: Comanda #1 open; `"Bruno"` has active order #1 (status: `"recebido"`, comanda_id: 1).
    - Input: `POST /pedidos` for `"Bruno"` with `tipo: "mesa"` and `"comanda_id": 1`.
    - Expected Output: Status `201 Created`.

---

## 3. tests/test_uc2_uc3_uc5_status.py (Lifecycle & Progression)

- **test_order_status_progression**
  - **Input Sequence:**
    1. Create order -> initial status `"recebido"`.
    2. `POST /pedidos/1/status`
       - Expected Output: Status `200`, `{"id": 1, "status": "preparo"}`.
    3. `POST /pedidos/1/status`
       - Expected Output: Status `200`, `{"id": 1, "status": "pronto"}`.
    4. `POST /pedidos/1/status`
       - Expected Output: Status `200`, `{"id": 1, "status": "entregue"}`.
    5. `POST /pedidos/1/status`
       - Expected Output: Status `409`, `{"erro": "pedido_ja_finalizado"}`.

- **test_order_cancellation_rules**
  - **Scenario 1 (Valid cancellation):**
    - Pre-condition: Order #1 in `"recebido"`.
    - Input: `POST /pedidos/1/cancelamento`.
    - Expected Output: Status `200`, `{"id": 1, "status": "cancelado"}`.
  - **Scenario 2 (Invalid cancellation after advancement):**
    - Pre-condition: Order #2 progressed to `"preparo"`.
    - Input: `POST /pedidos/2/cancelamento`.
    - Expected Output: Status `409`, `{"erro": "pedido_nao_cancelavel"}`.

- **test_list_active_orders**
  - **Pre-condition:** Orders exist in system: #1 (`recebido`), #2 (`preparo`), #3 (`cancelado`), #4 (`pronto`), #5 (`entregue`).
  - **Input:** `GET /pedidos/ativos`.
  - **Expected Output:**
    - Status: `200 OK`
    - Body: Array containing orders `[#4, #2, #1]` sorted newest first (excluding #3 and #5).

---

## 4. tests/test_uc9_uc11_uc12_uc13_comandas.py (Tables & Tab Closure)

- **test_table_open_and_occupancy**
  - **Input A:** `POST /mesas/7/comandas`
    - Expected Output: Status `201`, `{"id": 1, "mesa": 7, "status": "aberta", "aberta_em": "<ISO-8601 -03:00>"}`.
  - **Input B:** `POST /mesas/7/comandas` (while tab #1 is open)
    - Expected Output: Status `409`, `{"erro": "mesa_ocupada"}`.
  - **Input C:** `POST /mesas/55/comandas`
    - Expected Output: Status `422`, `{"erro": "mesa_invalida"}`.

- **test_list_open_tabs_fifo**
  - **Pre-condition:** Tab #1 opened at `19:00:00-03:00`, Tab #2 opened at `19:30:00-03:00`.
  - **Input:** `GET /comandas/abertas`.
  - **Expected Output:** Status `200`, Body `[Tab #1, Tab #2]` (oldest first: `aberta_em` ascending).

- **test_close_tab_with_unserved_orders**
  - **Pre-condition:** Tab #1 open; linked order #1 has status: `"preparo"`.
  - **Input:** `POST /comandas/1/fechamento`.
  - **Expected Output:** Status `409`, `{"erro": "comanda_com_pedidos_abertos"}`.

- **test_close_tab_consolidation_and_split**
  - **Pre-condition:** Tab #1 open; has 2 delivered orders with `total_centavos`: 15000 and 15500 (subtotal = 30500).
  - **Input:**
    - `POST /comandas/1/fechamento`
    - Payload:
      ```json
      {
        "gorjeta_percentual": 10,
        "dividir_em": 3
      }
      ```
  - **Expected Output:**
    - Status: `200 OK`
    - Body:
      ```json
      {
        "id": 1,
        "mesa": 7,
        "status": "fechada",
        "pedidos_entregues": 2,
        "subtotal_centavos": 30500,
        "gorjeta_centavos": 3050,
        "total_centavos": 33550,
        "parcelas_centavos": [11184, 11183, 11183]
      }
      ```
  - **Subsequent Call:** `POST /comandas/1/fechamento`
    - Expected Output: Status `409`, `{"erro": "comanda_ja_fechada"}`.

---

## 5. tests/test_uc14_cardapio.py (Menu & Dynamic Flavors)

- **test_dynamic_flavor_auto_registration**
  - **Pre-condition:** Flavor `"rucula"` has never been added or ordered.
  - **Input:** `POST /pedidos` containing item with `"sabor": "rucula"`.
  - **Expected Output:** Order accepted (`201 Created`); `GET /cardapio` now includes `{"sabor": "rucula", "disponivel": true}`.

- **test_case_insensitive_availability_toggle**
  - **Input 1:** `PUT /cardapio/catupiry` with body `{"disponivel": false}`
    - Expected Output: Status `200`, `{"sabor": "catupiry", "disponivel": false}`.
  - **Input 2:** `POST /pedidos` with item `"sabor": "CaTuPiRy"`
    - Expected Output: Status `409`, `{"erro": "sabor_indisponivel"}`.

- **test_menu_alphabetical_sorting**
  - **Pre-condition:** Registered flavors: `"quatro queijos"`, `"aliche"`, `"calabresa"`.
  - **Input:** `GET /cardapio`.
  - **Expected Output:**
    - Status: `200 OK`
    - Flavors returned in exact order: `["aliche", "calabresa", "quatro queijos"]`.

---

## 6. tests/test_uc16_fidelidade.py (Loyalty Stamp Card)

- **test_loyalty_applied_on_sixth_order**
  - **Pre-condition:** Customer `"Carla"` has completed 5 delivered orders (`status: "entregue"`).
  - **Input:**
    - `POST /pedidos` for `"Carla"` with 1 broto pizza (`subtotal = 3250`), `tipo = "balcao"`.
    - `PRECO_BROTO_CENTAVOS = 3250`, promo discount = 15% (`ceil(3250 * 0.15) = 488`).
  - **Expected Output:**
    - Status: `201 Created`
    - Body includes:
      - `"desconto_centavos": 488`
      - `"desconto_fidelidade_centavos": 3250`
      - `"total_centavos": 0` *(calculated as max(0, 3250 - 488 - 3250) = 0)*

- **test_loyalty_rollback_on_cancellation**
  - **Pre-condition:** Order #6 for `"Carla"` (above) was created with `"desconto_fidelidade_centavos": 3250` and is in `"recebido"`.
  - **Input 1:** `POST /pedidos/6/cancelamento`
    - Expected Output: Status `200`, `{"id": 6, "status": "cancelado"}`.
  - **Input 2:** `POST /pedidos` for `"Carla"` (new order attempt)
    - Expected Output: Status `201 Created`, with `"desconto_fidelidade_centavos": 3250` (discount eligibility restored).

---

## 7. tests/test_uc4_relatorios.py (Daily Reporting)

- **test_daily_report_aggregation**
  - **Pre-condition:**
    - Order #1: `recebido_em = "2026-10-28T12:00:00-03:00"`, `total_centavos = 10000`, `status = "entregue"`.
    - Order #2: `recebido_em = "2026-10-28T13:00:00-03:00"`, `total_centavos = 5500`, `status = "pronto"`.
    - Order #3: `recebido_em = "2026-10-28T14:00:00-03:00"`, `total_centavos = 9000`, `status = "cancelado"`.
    - Order #4: `recebido_em = "2026-10-27T20:00:00-03:00"`, `total_centavos = 8000`, `status = "entregue"` (different date).
    - Comanda closure on 2026-10-28 with `gorjeta_centavos = 3000` (tip must be excluded).
  - **Input:** `GET /relatorios/diario?data=2026-10-28`
  - **Expected Output:**
    - Status: `200 OK`
    - Body:
      ```json
      {
        "data": "2026-10-28",
        "total_pedidos": 2,
        "faturamento_centavos": 15500,
        "ticket_medio_centavos": 7750
      }
      ```
      *(where total_pedidos = 2, faturamento_centavos = 10000 + 5500 = 15500, and ticket_medio_centavos = 15500 / 2 = 7750)*

- **test_daily_report_zero_orders**
  - **Input:** `GET /relatorios/diario?data=2026-01-01` (date with zero registered orders)
  - **Expected Output:**
    - Status: `200 OK`
    - Body:
      ```json
      {
        "data": "2026-01-01",
        "total_pedidos": 0,
        "faturamento_centavos": 0,
        "ticket_medio_centavos": 0
      }
      ```
