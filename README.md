# Pizzeria REST API

FastAPI-based in-memory REST API for pizzeria order intake, table tab lifecycle management, bill splitting, customer loyalty rewards, and daily reporting metrics.

---

## What the Evaluator Should Review First

1. **Order Validation Precedence (`app/services/pedido_service.py`)**:
   - Implements the strict priority sequence: Schema & boundary checks (422) $\rightarrow$ Tab assignment validity (422) $\rightarrow$ Menu item availability (409) $\rightarrow$ Active customer concurrency (409).
2. **Tab Closure & Bill Splitting (`app/services/comanda_service.py` & `app/common/math_utils.py`)**:
   - Validates all attached orders are delivered prior to closure.
   - Calculates custom tips and splits totals into integer-cent chunks where differences between shares never exceed 1 cent.
3. **Loyalty Program Protocol (`app/services/pedido_service.py`)**:
   - Automatically tracks completed deliveries, awards a small pizza credit on the 6th order after 5 delivered orders, enforces a zero-cent floor, and cleanly restores eligibility upon order cancellation.
4. **Automated Test Suite (`tests/`)**:
   - End-to-end coverage across all use cases (UC1 through UC16), state transitions, edge cases, and the consolidated error contract.

---

## Architectural Decisions

* **Layered Architecture**: Strict separation of concerns across `routers` (HTTP/transport), `services` (business domain rules), and `repositories` (in-memory data management).
* **In-Memory Storage**: Domain state is managed in memory using Python dictionaries with isolated sequence counters for auto-incrementing integer IDs (`1, 2, 3...`).
* **Strict Integer Arithmetic**: All monetary fields are kept in cents (`centavos`). Floating-point representations and arithmetic are forbidden across all calculation engines and API responses.
* **Predictable Timezone & Test Hook**: Datetime values are generated with a `-03:00` offset (`America/Sao_Paulo`). The optional `recebido_em` parameter on `POST /pedidos` serves as a testability hook for retroactive reporting tests.
* **Uniform Error Responses**: FastAPI's validation exception handler is customized to guarantee standard error payloads (`{"erro": "<slug>"}`) across all 422, 409, and 404 responses.

---

## Prerequisites

* Python 3.11+
* `pip` or virtual environment manager (`venv`)

---

## Setup & Running the Application

### 1. Create and Activate Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
