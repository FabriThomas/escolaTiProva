# Tasks Breakdown - Pizzeria REST API

## 1. Setup & Core Primitives

- [ ] **T1.1: Configuration Module (`app/config.py`)**
  - Implement dynamic loader for `params.json` with fallback defaults:
    - `PRECO_BROTO_CENTAVOS`: 3250
    - `PRECO_GRANDE_CENTAVOS`: 5500
    - `TAXA_ENTREGA_CENTAVOS`: 500
    - `DESCONTO_PROMO_PERCENTUAL`: 15
    - `GORJETA_PADRAO_PERCENTUAL`: 15
    - `PORTA_SERVICO`: 8004
  - Create the application factory in `app/main.py`.
- [ ] **T1.2: Integer Math & Rounding Utilities (`app/common/math_utils.py`)**
  - Implement `calculate_promo_discount(subtotal, pct)` using `math.ceil`.
  - Implement `calculate_tip(subtotal, pct)` using `math.ceil`.
  - Implement `split_bill(total, n)` distributing the remainder (`total % n`) as +1 cent across the initial shares.
  - Implement `calculate_average_ticket(faturamento, total_pedidos)` using round-half-up: `floor(faturamento / total_pedidos + 0.5)`.
- [ ] **T1.3: Timezone Provider & Test Hooks (`app/common/time_provider.py`)**
  - Implement `get_now()` producing ISO-8601 timestamps strictly with `-03:00` offset.
  - Ensure `recebido_em` parameter on `POST /pedidos` accepts ISO-8601 with timezone and falls back to `get_now()` if omitted.
- [ ] **T1.4: Domain Exceptions & Error Handler (`app/common/exceptions.py`)**
  - Setup custom domain exceptions (`DomainConflictError`, `DomainNotFoundError`, `DomainValidationError`).
  - Override FastAPI's `RequestValidationError` to return uniform `{"erro": "<slug>"}` 422 responses.
- [ ] **T1.5: In-Memory Storage Repositories (`app/repositories/`)**
  - Build `pedido_repo.py` with in-memory dict and integer auto-increment ID.
  - Build `comanda_repo.py` with in-memory dict and integer auto-increment ID.
  - Build `cardapio_repo.py` with in-memory dict indexed by case-folded flavor keys.
- [ ] **T1.6: Pytest Reset & Mock Fixtures (`tests/conftest.py`)**
  - Implement test fixture to clear in-memory dictionaries and reset auto-increment counters before each test run.
  - Implement mockable fixture for `get_now()` to support deterministic time tests.

---

## 2. Menu & Table Tabs

- [ ] **T2.1: Dynamic Menu Engine (UC14)**
  - Implement `PUT /cardapio/{sabor}` to update flavor availability.
  - Implement `GET /cardapio` returning all registered flavors alphabetically sorted.
  - Auto-register any new flavor seen in orders as `disponivel: true`.
- [ ] **T2.2: Table Tab Management (UC9, UC12, UC13)**
  - Implement `POST /mesas/{numero}/comandas` validating table range 1 to 50 (`422 mesa_invalida`) and table occupancy (`409 mesa_ocupada`).
  - Implement `GET /comandas/abertas` returning active tabs sorted FIFO (oldest first).
  - Implement `GET /mesas/{numero}/comandas` returning full table history sorted newest first (returns `[]` if empty).

---

## 3. Orders Core & Lifecycle

- [ ] **T3.1: Order Creation Pipeline & Precedence (UC1, UC7, UC8, UC10)**
  - Enforce validation priority:
    1. Schema bounds (`422 cliente_invalido`, `itens_invalidos`, `tipo_invalido`, `recebido_invalido`).
    2. Tab rules (`422 comanda_invalida` if missing/closed for mesa, or present for non-mesa).
    3. Menu availability (`409 sabor_indisponivel`).
    4. Active order concurrency (`409 pedido_em_aberto` for entrega/balcao; skipped for mesa).
  - Calculate `subtotal_pizzas_centavos`, `taxa_entrega_centavos`, and `desconto_centavos`.
- [ ] **T3.2: Loyalty Stamp Card Protocol (UC16)**
  - Count delivered orders (`status == "entregue"`) under the client name.
  - Apply `desconto_fidelidade_centavos = PRECO_BROTO_CENTAVOS` (3250 cents) on every 6th order after 5 delivered orders.
  - Apply floor at zero (`total_centavos = max(0, ...)`) so total is never negative.
- [ ] **T3.3: Order Lifecycle Transitions & Cancellation (UC2, UC5)**
  - Implement `POST /pedidos/{id}/status` progressing: `recebido` -> `preparo` -> `pronto` -> `entregue` (terminal; `409 pedido_ja_finalizado` on subsequent attempts).
  - Implement `POST /pedidos/{id}/cancelamento` strictly allowed in `recebido` (`409 pedido_nao_cancelavel` otherwise).
  - Ensure cancellation releases client concurrency lock and restores unredeemed loyalty status.
- [ ] **T3.4: Order Querying Endpoints (UC3, UC6)**
  - Implement `GET /pedidos/ativos` returning orders in `recebido`, `preparo`, or `pronto`, sorted newest first.
  - Implement `GET /pedidos?cliente={nome}` returning customer history across all statuses, sorted newest first.

---

## 4. Financial Closures & Reporting

- [ ] **T4.1: Tab Closure & Bill Splitting (UC11, UC15)**
  - Implement `POST /comandas/{id}/fechamento`.
  - Reject closure if linked orders are still in `recebido`, `preparo`, or `pronto` (`409 comanda_com_pedidos_abertos`).
  - Reject already closed tabs (`409 comanda_ja_fechada`).
  - Validate optional parameters (`gorjeta_percentual`: 0 to 30, `dividir_em`: 2 to 10).
  - Sum delivered order totals, compute ceiling tip, and split into `parcelas_centavos` if `dividir_em` is present.
- [ ] **T4.2: Daily Revenue Reporting (UC4)**
  - Implement `GET /relatorios/diario?data=AAAA-MM-DD`.
  - Validate date format (`422 data_invalida`).
  - Aggregate non-cancelled orders received on target date (tips excluded).
  - Calculate average ticket with round-half-up (return zeros if day has no orders).

---

## 5. Verification & Test Suite

- [ ] **T5.1: Unit Test Suite (`tests/test_math_utils.py`)**
  - Verify ceil promo discount, ceil tip, round-half-up average ticket, and remainder distribution in bill splitting.
- [ ] **T5.2: End-to-End Use Case Tests (`tests/`)**
  - `test_uc1_uc7_pedidos.py`: Order creation, pricing calculations, and validation precedence order.
  - `test_uc2_uc3_status.py`: Status pipeline transitions and active orders filter.
  - `test_uc4_relatorios.py`: Daily report aggregations and date validation.
  - `test_uc5_uc8_cancel.py`: Order cancellation, lock release, and concurrency blocking.
  - `test_uc6_historico.py`: Customer historical query results.
  - `test_uc9_uc13_mesas.py`: Tab opening, occupancy rules, and table tab history.
  - `test_uc11_uc15_fechamento.py`: Tab closure validations, tip calculations, and bill division.
  - `test_uc14_cardapio.py`: Dynamic flavor registration and availability blocking.
  - `test_uc16_fidelidade.py`: 5-order threshold redemption and cancellation rollback.
- [ ] **T5.3: Error Matrix Parameterized Test**
  - Parameterized table-driven test covering the entire error contract (verifying HTTP 404, 409, and 422 payload slugs).
