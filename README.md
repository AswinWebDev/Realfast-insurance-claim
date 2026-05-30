# RealFast Claims Processing System

An insurance claims processing system built as a take-home assignment. Members submit claims with line items, the system adjudicates each item against coverage rules, and tracks the claim through its full lifecycle.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Database | SQLite (local file `claims.db`) |
| ORM | SQLAlchemy 2.0 |
| Frontend | React + Vite *(in progress)* |

---

## Prerequisites

- Python 3.12 (not 3.13/3.14 — pydantic-core wheels unavailable)
- Node.js 18+ *(for frontend, when ready)*

Check your Python version:
```bash
python3.12 --version
```

If not installed on macOS:
```bash
brew install python@3.12
```

---

## Setup & Run

### Backend

```bash
cd app
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start the server:
```bash
cd ..   # project root
source app/.venv/bin/activate
PYTHONPATH=$(pwd) uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The server starts at `http://localhost:8000`. Interactive API docs at `http://localhost:8000/docs`.

The SQLite database (`claims.db`) is created automatically on first run. Seed data (3 plans, 5 members) is inserted on startup.

### Frontend

*(Not yet built — coming next)*

---

## Run Tests

```bash
source app/.venv/bin/activate
PYTHONPATH=$(pwd) python3.12 -m pytest app/tests/ -v
```

28 tests covering adjudication math, accumulators, state machines, and disputes.

---

## Seeded Data

### Plans

| Plan | Deductible | OOP Max | Physical Therapy |
|---|---|---|---|
| Diamond | $500 | $3,000 | Covered |
| Gold | $1,000 | $5,000 | Covered |
| Bronze | $2,500 | $8,000 | **Excluded** |

### Members

| ID | Name | Plan |
|---|---|---|
| `member-001` | Alice Johnson | Diamond |
| `member-002` | Bob Martinez | Gold |
| `member-003` | Carol Chen | Bronze |
| `member-004` | David Park | Diamond |
| `member-005` | Emma Wilson | Gold |

---

## Key API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/members/` | List all members |
| `GET` | `/api/policies/` | List all plans with coverage rules |
| `POST` | `/api/claims/` | Submit a claim (triggers adjudication immediately) |
| `GET` | `/api/claims/` | List claims (filter with `?member_id=`) |
| `GET` | `/api/claims/{id}` | Get claim with line items and adjudication notes |
| `PATCH` | `/api/claims/{id}/status` | Move claim to PAID or DISPUTED |
| `PATCH` | `/api/claims/{id}/line-items/{lid}/review` | Resolve NEEDS_REVIEW line item |
| `POST` | `/api/claims/{id}/line-items/{lid}/disputes` | File a dispute |
| `PATCH` | `/api/claims/{id}/line-items/{lid}/disputes/{did}` | Resolve dispute (UPHELD/OVERTURNED) |

---

## Example: Submit a Claim

```bash
curl -X POST http://localhost:8000/api/claims/ \
  -H "Content-Type: application/json" \
  -d '{
    "member_id": "member-001",
    "provider_name": "Downtown Hospital",
    "line_items": [
      {"service_type": "PRIMARY_CARE", "service_date": "2026-05-01", "billed_amount": 350},
      {"service_type": "LAB", "service_date": "2026-05-01", "billed_amount": 500}
    ]
  }'
```

Each line item is adjudicated immediately. The response includes `approved_amount`, `member_responsibility`, and step-by-step `adjudication_notes`.

---

## Project Structure

```
realfast-claims/
├── app/
│   ├── api/routes/        # FastAPI route handlers
│   ├── core/              # Database setup, seed data
│   ├── models/            # SQLAlchemy models + enums
│   ├── schemas/           # Pydantic request/response schemas
│   ├── services/          # Adjudication engine
│   ├── tests/             # pytest test suite
│   └── requirements.txt
├── docs/
│   ├── domain-model.md    # Entities, state machines, adjudication logic
│   ├── decisions.md       # Design decisions and trade-offs
│   └── self-review.md     # Honest self-assessment
├── ai-artifacts/          # Claude Code session logs (JSONL)
├── CLAUDE.md              # Project context for AI sessions
└── README.md
```

---

## Docs

- `docs/domain-model.md` — full entity definitions, state machines, adjudication order of operations, plan rules
- `docs/decisions.md` — every design decision with trade-off reasoning
- `docs/self-review.md` — honest assessment of what's good, rough, and missing
