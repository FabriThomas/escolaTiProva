# SDD Implementation Plan - Pizzeria REST API

## 1. Project Overview & Architecture

- **Stack**: Python 3.11+, FastAPI, Pydantic v2, Pytest, HTTPX (`TestClient`).
- **Pattern**: Layered Architecture (Routers -> Services -> Repositories).
- **State Management**: In-memory Python dictionaries isolated per domain entity (orders, tabs, menu), indexed by autoincrementing integer IDs (1, 2, 3...).
- **Time Management**: Dedicated time provider (`get_now()`) enforcing timezone `-03:00` for test isolation.
- **Configuration**: `app/config.py` loading environment parameters from fallback defaults or `params.json`:
  - `PRECO_BROTO_CENTAVOS`: 3250
  - `PRECO_GRANDE_CENTAVOS`: 5500
  - `TAXA_ENTREGA_CENTAVOS`: 500
  - `DESCONTO_PROMO_PERCENTUAL`: 15
  - `GORJETA_PADRAO_PERCENTUAL`: 15
  - `PORTA_SERVICO`: 8004

---

## 2. Directory Structure

```plaintext
.
├── params.json                 # System configuration parameters
├── pyproject.toml / requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application factory and custom error handlers
│   ├── config.py               # Settings loader (reads params.json)
│   ├── common/
│   │   ├── __init__.py
│   │   ├── exceptions.py       # Domain exceptions (Http404, Http409, Http422)
│   │   ├── time_provider.py    # get_now() with -03:00 timezone
│   │   └── math_utils.py       # Ceil, half-up rounding, integer bill splitting
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── pedido.py           # Order request/response schemas with Pydantic validations
│   │   ├── comanda.py          # Tab open/closure and history schemas
│   │   ├── cardapio.py         # Flavor toggle and menu listing schemas
│   │   └── relatorio.py        # Daily summary report schemas
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── cardapio_repo.py    # In-memory storage for flavors (case-insensitive keys)
│   │   ├── comanda_repo.py     # In-memory storage for table tabs and autoincrement IDs
│   │   └── pedido_repo.py      # In-memory storage for orders and autoincrement IDs
│   ├── services/
│   │   ├── __init__.py
│   │   ├── cardapio_service.py # Menu registration and availability checks
│   │   ├── comanda_service.py  # Tab lifecycle, occupancy checks, and tip/split calculations
│   │   └── pedido_service.py   # Order precedence pipeline, status progression, loyalty logic
│   └── routers/
│       ├── __init__.py
│       ├── cardapio.py         # PUT /cardapio/{sabor}, GET /cardapio
│       ├── mesas.py            # POST /mesas/{numero}/comandas, GET /mesas/{numero}/comandas
│       ├── comandas.py         # GET /comandas/abertas, POST /comandas/{id}/fechamento
│       ├── pedidos.py          # POST/GET /pedidos, /pedidos/ativos, /status, /cancelamento
│       └── relatorios.py       # GET /relatorios/diario
└── tests/
    ├── conftest.py             # Fixtures for TestClient, mock clocks, and state reset
    ├── test_math_utils.py      # Unit tests for integer formulas and rounding
    ├── test_uc1_uc7_pedidos.py # Order creation, promo calculations, validation order
    ├── test_uc2_uc3_status.py  # Status lifecycle and active orders listing
    ├── test_uc4_relatorios.py  # Daily revenue and average ticket metrics
    ├── test_uc5_uc8_cancel.py  # Cancellations and client active order constraints
    ├── test_uc6_historico.py   # Customer order history queries
    ├── test_uc9_uc13_mesas.py  # Tab opening, table occupation, and history
    ├── test_uc11_uc15_fechamento.py # Tab bill splitting and service charge
    ├── test_uc14_cardapio.py   # Menu availability and dynamic registration
    └── test_uc16_fidelidade.py # 5-order stamp card deduction and rollbacks
```

---

## 3. Implementation Phases & Milestones

### Phase 1: Environment, Configuration & Common Utilities

- **P1.1 — Configuration Module (`app/config.py`)**:
  - Implement dynamic loader for `params.json` with fallback defaults:
    - `PRECO_BROTO_CENTAVOS = 3250`
    - `PRECO_GRANDE_CENTAVOS = 5500`
    - `TAXA_ENTREGA_CENTAVOS = 500`
    - `DESCONTO_PROMO_PERCENTUAL = 15`
    - `GORJETA_PADRAO_PERCENTUAL = 15`
    - `PORTA_SERVICO = 8004`
- **P1.2 — Math Utilities (`app/common/math_utils.py`)**:
  - `calculate_promo_discount(subtotal, pct)`: `math.ceil(subtotal * pct / 100)`.
  - `calculate_tip(subtotal, pct)`: `math.ceil(subtotal * pct / 100)`.
  - `calculate_average_ticket(revenue, count)`: Round half-up: `math.floor(revenue / count + 0.5)` when `count > 0`, else `0`.
  - `split_bill(total, n)`: Divide `total` into `n` chunks, distributing remainder `total % n` as `+1` cent to the initial shares.
- **P1.3 — Time Provider (`app/common/time_provider.py`)**:
  - Provide `get_now()` with fixed `-03:00` offset (`ZoneInfo("America/Sao_Paulo")` or `timezone(timedelta(hours=-3))`).
- **P1.4 — Error Handling Standardization (`app/common/exceptions.py` & `app/main.py`)**:
  - Configure custom exception handlers for Pydantic `RequestValidationError` to return uniform `{"erro": "<slug>"}` 422 responses instead of default FastAPI validation arrays.

---

### Phase 2: Menu (Cardápio) & Table Tab (Comanda) Subsystems

- **P2.1 — Dynamic Menu Storage & Service (UC14)**:
  - In-memory repository mapping case-folded flavor strings (`sabor.lower().strip()`) to `{"sabor": str, "disponivel": bool}`.
  - Any unseen flavor passed to `register_flavor_if_missing()` defaults to `disponivel: True`.
  - Implement `PUT /cardapio/{sabor}` and `GET /cardapio` (sorted alphabetically).
- **P2.2 — Table Tab Subsystem (UC9, UC12, UC13)**:
  - Validate table numbers strictly within 1 to 50 (returns `422 {"erro": "mesa_invalida"}`).
  - Prevent opening a tab on occupied tables (returns `409 {"erro": "mesa_ocupada"}`).
  - Implement `POST /mesas/{numero}/comandas` (`status: "aberta"`, autoincrement ID).
  - Implement `GET /comandas/abertas` (sorted FIFO: oldest `aberta_em` first).
  - Implement `GET /mesas/{numero}/comandas` (sorted newest first).

---

### Phase 3: Order Core Engine & Precedence Pipeline (UC1, UC7, UC8, UC10, UC16)

- **P3.1 — Schema & Boundary Validation Pipeline**:
  - Enforce strict priority sequence on `POST /pedidos`:
    1. **Format 422**: `cliente` (2 to 60 chars), `itens` (1 to 20 items, size in `["broto", "grande"]`, quantity in 1 to 10), `tipo` in `["entrega", "balcao", "mesa"]`, parseable ISO-8601 `recebido_em`.
    2. **Tab Association 422**: If `tipo == "mesa"`, `comanda_id` must reference an active, open tab. If `tipo != "mesa"`, `comanda_id` must be `None`/omitted.
    3. **Menu Availability 409**: Check all flavors in payload. If any flavor has `disponivel == False`, reject with `{"erro": "sabor_indisponivel"}` (register unseen flavors as available).
    4. **Active Order Concurrency 409**: For `entrega` and `balcao`, verify customer has no existing order in status `recebido`, `preparo`, or `pronto` (reject with `{"erro": "pedido_em_aberto"}`). Dine-in (`tipo == "mesa"`) skips this check.
- **P3.2 — Pricing Engine**:
  - Calculate `subtotal_pizzas_centavos` using unit sizes.
  - Calculate `taxa_entrega_centavos` (500 if `entrega`, else 0).
  - Calculate promo discount: `math.ceil(subtotal * DESCONTO_PROMO_PERCENTUAL / 100)`.
- **P3.3 — Loyalty Program Integration (UC16)**:
  - Check customer delivery count: count previous orders for `cliente` with `status == "entregue"`.
  - If customer has 5 or more delivered orders since last reward redemption, apply: `desconto_fidelidade_centavos = PRECO_BROTO_CENTAVOS`.
  - Calculate total: `total_centavos = max(0, subtotal - desconto_promo + taxa - desconto_fidelidade)`.
  - Persist and return `201 Created`.

---

### Phase 4: Order Lifecycle & History (UC2, UC3, UC5, UC6)

- **P4.1 — Status Progression (UC2)**:
  - `POST /pedidos/{id}/status`: `recebido` -> `preparo` -> `pronto` -> `entregue`.
  - Unknown order returns `404 {"erro": "pedido_nao_encontrado"}`.
  - Advancing from `entregue` returns `409 {"erro": "pedido_ja_finalizado"}`.
- **P4.2 — Order Cancellation (UC5)**:
  - `POST /pedidos/{id}/cancelamento`: Allowed strictly while in status `recebido`.
  - Cancelling in `preparo`, `pronto`, or `entregue` returns `409 {"erro": "pedido_nao_cancelavel"}`.
  - Cancellation unlocks customer concurrency limits (UC8) and restores loyalty discount eligibility if redeemed on this order (UC16).
- **P4.3 — Active & Historical Queries (UC3, UC6)**:
  - `GET /pedidos/ativos`: Filter orders in `["recebido", "preparo", "pronto"]`, sorted newest first.
  - `GET /pedidos?cliente={nome}`: Filter all orders matching customer name, sorted newest first.

---

### Phase 5: Tab Closure & Bill Splitting (UC11, UC15)

- **P5.1 — Tab Closure Validation**:
  - Unknown tab ID returns `404 {"erro": "comanda_nao_encontrada"}`.
  - Tab with status `fechada` returns `409 {"erro": "comanda_ja_fechada"}`.
  - Check linked orders: if any order is in `recebido`, `preparo`, or `pronto`, return `409 {"erro": "comanda_com_pedidos_abertos"}`.
  - Validate `gorjeta_percentual` (0 to 30) and `dividir_em` (2 to 10), returning 422 on boundary violations.
- **P5.2 — Financial Consolidation**:
  - Aggregate delivered orders: `subtotal_centavos = sum(order.total_centavos)`.
  - Calculate tip: `gorjeta_centavos = math.ceil(subtotal_centavos * pct / 100)`.
  - Calculate total: `total_centavos = subtotal_centavos + gorjeta_centavos`.
  - If `dividir_em` is present, compute integer partitions in `parcelas_centavos`.
  - Mark tab as `fechada`, record `fechada_em`, and return `200 OK`.

---

### Phase 6: Daily Reporting & Analytics (UC4)

- **P6.1 — Daily Metrics Endpoint (`GET /relatorios/diario`)**:
  - Validate `data` query param matches `YYYY-MM-DD` (returns `422 {"erro": "data_invalida"}`).
  - Filter orders where `recebido_em.date() == target_date` and `status != "cancelado"`.
  - Compute `faturamento_centavos = sum(order.total_centavos)` (tips excluded).
  - Compute `ticket_medio_centavos` using round-half-up division.
  - Empty dates return zeros for all numeric counts.

---

### Phase 7: Verification & Test Suite

- **P7.1 — Unit Test Coverage**:
  - Math formulas: verify promo ceiling, tip ceiling, integer division remainder distribution, and ticket rounding.
- **P7.2 — End-to-End Integration Suite (`pytest` + `TestClient`)**:
  - Full customer flows: Counter order -> advance to terminal state -> new order.
  - Dine-in flows: Open tab -> attach multiple orders -> advance all to delivered -> close tab with custom tip and 3-way split.
  - Loyalty workflow: 5 delivered orders -> 6th order receives `PRECO_BROTO_CENTAVOS` discount -> cancel order -> re-order confirms discount restoration.
  - Complete validation error status matrix (checking 404, 409, and 422 error payloads).
