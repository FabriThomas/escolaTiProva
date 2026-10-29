# SDD Implementation Plan: Pizzeria REST API

## 1. Project Overview & Architecture
- **Stack**: Python 3.11+, FastAPI, Pydantic v2, Pytest, HTTPX.
- **Pattern**: Layered Architecture (`Routers` -> `Services` -> `Repositories`).
- **State Management**: In-memory Python dictionaries isolated per domain entity (`pedidos`, `comandas`, `cardapio`), indexed by autoincrement integer IDs.
- **Time Management**: Dedicated time provider (`get_now()`) enforcing timezone `-03:00`.
- **Configuration**: `app/config.py` loading dynamic parameters from `params.json` with domain fallback defaults.

---

## 2. Directory Structure

- `params.json`: System configuration parameters.
- `requirements.txt`: Python package dependencies.
- `app/main.py`: FastAPI application factory and error handlers.
- `app/config.py`: Settings loader reading `params.json`.
- `app/common/exceptions.py`: Domain exception definitions.
- `app/common/time_provider.py`: Time helper with `-03:00` offset.
- `app/common/math_utils.py`: Ceil, round half-up, and bill splitting utilities.
- `app/schemas/`: Pydantic input and output validation schemas (`pedido.py`, `comanda.py`, `cardapio.py`, `relatorio.py`).
- `app/repositories/`: In-memory storage modules (`pedido_repo.py`, `comanda_repo.py`, `cardapio_repo.py`).
- `app/services/`: Business rule validation and pipeline logic (`pedido_service.py`, `comanda_service.py`, `cardapio_service.py`, `relatorio_service.py`).
- `app/routers/`: HTTP route endpoints (`pedidos.py`, `comandas.py`, `mesas.py`, `cardapio.py`, `relatorios.py`).
- `tests/`: Automated Pytest test suite and test fixtures (`conftest.py`, `test_math_utils.py`, use case test modules).

---

## 3. Implementation Phases & Milestones

### Phase 1: Environment, Configuration & Common Utilities
- **P1.1 — Configuration Module (`app/config.py`)**: Implement loader for `params.json` with fallback defaults (`PRECO_BROTO_CENTAVOS: 3250`, `PRECO_GRANDE_CENTAVOS: 5500`, `TAXA_ENTREGA_CENTAVOS: 500`, `DESCONTO_PROMO_PERCENTUAL: 15`, `GORJETA_PADRAO_PERCENTUAL: 15`, `PORTA_SERVICO: 8004`).
- **P1.2 — Math Utilities (`app/common/math_utils.py`)**: Implement `calculate_promo_discount`, `calculate_tip`, `calculate_average_ticket` (half-up rounding), and `split_bill` (remainder distribution).
- **P1.3 — Time Provider (`app/common/time_provider.py`)**: Provide `get_now()` with fixed `-03:00` offset.
- **P1.4 — Error Handling Standardization**: Custom exception handlers for Pydantic `RequestValidationError` to return uniform `{"erro": "<slug>"}` 422 responses.

### Phase 2: Menu & Table Tab Subsystems
- **P2.1 — Dynamic Menu Storage & Service (UC14)**: In-memory repo mapping case-folded flavor strings. Dynamic auto-registration (`disponivel: true`). Implement `PUT /cardapio/{sabor}` and `GET /cardapio` (alphabetical sort).
- **P2.2 — Table Tab Subsystem (UC9, UC12, UC13)**: Range check `1..50` (422 `mesa_invalida`), occupancy check (409 `mesa_ocupada`). Implement `POST /mesas/{numero}/comandas`, `GET /comandas/abertas` (FIFO), and `GET /mesas/{numero}/comandas` (newest first).

### Phase 3: Order Core Engine & Precedence Pipeline (UC1, UC7, UC8, UC10, UC16)
- **P3.1 — Schema & Boundary Validation Pipeline**: Enforce strict priority sequence on `POST /pedidos`:
  1. Format 422: `cliente`, `itens`, `tipo`, `recebido_em`.
  2. Tab Association 422: `comanda_id` check for `tipo = "mesa"`.
  3. Menu Availability 409: `sabor_indisponivel` check.
  4. Active Order Concurrency 409: `pedido_em_aberto` check for `entrega`/`balcao`.
- **P3.2 — Pricing Engine**: Subtotal calculation, delivery fee addition, and promo ceiling discount.
- **P3.3 — Loyalty Program Integration (UC16)**: Track customer deliveries (`entregue`). Apply `PRECO_BROTO_CENTAVOS` discount on 6th order after 5 delivered orders. Floor total at zero.

### Phase 4: Order Lifecycle & History (UC2, UC3, UC5, UC6)
- **P4.1 — Status Progression (UC2)**: `POST /pedidos/{id}/status`: `recebido` -> `preparo` -> `pronto` -> `entregue` (terminal). Unknown order returns 404; advancing from terminal returns 409 `pedido_ja_finalizado`.
- **P4.2 — Order Cancellation (UC5)**: `POST /pedidos/{id}/cancelamento`: Allowed strictly while in `recebido`. Cancelling unlocks customer concurrency and restores loyalty credit.
- **P4.3 — Active & Historical Queries (UC3, UC6)**: `GET /pedidos/ativos` (newest first, excluding cancelled/delivered), `GET /pedidos?cliente={nome}` (all orders, newest first).

### Phase 5: Tab Closure & Bill Splitting (UC11, UC15)
- **P5.1 — Tab Closure Validation**: Return 404 for unknown tab; 409 `comanda_ja_fechada` if closed; 409 `comanda_com_pedidos_abertos` if unserved orders remain. Validate `gorjeta_percentual` (0..30) and `dividir_em` (2..10).
- **P5.2 — Financial Consolidation**: Subtotal sum of delivered orders, calculate tip, compute integer partition array `parcelas_centavos`, set `fechada_em`, and return 200 OK.

### Phase 6: Daily Reporting & Analytics (UC4)
- **P6.1 — Daily Metrics Endpoint (`GET /relatorios/diario`)**: Validate `data` format `YYYY-MM-DD`. Aggregate non-cancelled orders received on target date. Exclude tips from revenue. Apply round-half-up to calculate average ticket. Return zeros if no orders.

### Phase 7: Verification & Test Suite
- **P7.1 — Unit Test Coverage**: Verify ticket half-up rounding and bill partition distribution.
- **P7.2 — End-to-End Integration Suite**: Validate all use cases, state transitions, validation precedence, and error payload slugs.
