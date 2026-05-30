# RealFast Claims Processing System

An insurance claims processing system built as a take-home assignment. Members submit claims with line items, the system adjudicates each item against coverage rules, and tracks the claim through its full lifecycle.

> **Structure note:** Backend lives in `app/`, frontend in `frontend/` — both at the project root. Run both to use the full system (see Setup below).

---

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Database | SQLite (local file `claims.db`) |
| ORM | SQLAlchemy 2.0 |
| Frontend | React + Vite |

---

## Environment Variables

**No `.env` file is required.** This project uses SQLite (a local file) and has no external service dependencies. Everything runs locally out of the box.

The only environment variable needed at runtime is `PYTHONPATH`, set inline when starting the server (see below).

---

## Prerequisites

- **Python 3.12** — required. Python 3.13/3.14 will not work (pydantic-core wheels unavailable).
- **Node.js 18+** — required for the frontend.

Check versions:
```bash
python3.12 --version   # must be 3.12.x
node --version         # must be 18+
npm --version
```

Install Python 3.12 on macOS if missing:
```bash
brew install python@3.12
```

---

## Setup & Run

### 1. Backend

From the project root:

```bash
cd app
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
```

Start the server:
```bash
source app/.venv/bin/activate
PYTHONPATH=$(pwd) uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- API runs at `http://localhost:8000`
- Interactive API docs at `http://localhost:8000/docs`
- `claims.db` is created automatically on first run
- Seed data (3 plans, 5 members) is inserted on startup — no manual setup needed

### 2. Frontend

In a separate terminal, from the project root:

```bash
cd frontend
npm install
npm run dev
```

- UI runs at `http://localhost:5174`
- Requires the backend to be running on port 8000

### 3. Run Both (quick reference)

```bash
# Terminal 1 — backend
source app/.venv/bin/activate
PYTHONPATH=$(pwd) uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — frontend
cd frontend && npm run dev
```

Then open `http://localhost:5174` in your browser.

---

## Run Tests

From the project root with the venv activated:

```bash
source app/.venv/bin/activate
PYTHONPATH=$(pwd) python3.12 -m pytest app/tests/ -v
```

29 tests across 6 groups: coverage rules, adjudication math, accumulators, claim status derivation, state machine transitions, and disputes.

---

## Seeded Data

No manual data entry needed. On first startup the backend seeds:

### Plans

| Plan | Deductible | OOP Max | Physical Therapy |
|---|---|---|---|
| Diamond | $500 | $3,000 | Covered (85%, $30 copay) |
| Gold | $1,000 | $5,000 | Covered (75%, $45 copay) |
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

## UI Overview

Two tabs:

**Member View** — select a member, see their plan, accumulator usage bars, coverage rules, claims history. Submit a new claim with line items. View adjudication results with step-by-step notes. File disputes on denied line items.

**Insurer View** — all claims queue with filter pills. Click a claim to open the detail panel. Approve or deny NEEDS_REVIEW line items (prior auth). Resolve disputes (UPHELD / OVERTURNED). Mark approved claims as Paid.

---

## Key API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/members/` | List all members |
| `GET` | `/api/members/{id}` | Member detail with accumulators |
| `GET` | `/api/policies/` | List all plans with coverage rules |
| `POST` | `/api/claims/` | Submit a claim (triggers adjudication immediately) |
| `GET` | `/api/claims/` | List claims (filter with `?member_id=`) |
| `GET` | `/api/claims/{id}` | Get claim with line items and adjudication notes |
| `PATCH` | `/api/claims/{id}/status` | Move claim to PAID |
| `PATCH` | `/api/claims/{id}/line-items/{lid}/review` | Resolve NEEDS_REVIEW line item |
| `POST` | `/api/claims/{id}/line-items/{lid}/disputes` | File a dispute |
| `PATCH` | `/api/claims/{id}/line-items/{lid}/disputes/{did}` | Resolve dispute (UPHELD/OVERTURNED) |

Full interactive docs at `http://localhost:8000/docs` when the server is running.

---

## Example: Submit a Claim via curl

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

The response includes `approved_amount`, `member_responsibility`, and step-by-step `adjudication_notes` for each line item.

---

## Project Structure

```
realfast-claims/
├── app/
│   ├── api/routes/        # FastAPI route handlers (claims, members, policies)
│   ├── core/              # Database setup, seed data
│   ├── models/            # SQLAlchemy models + enums
│   ├── schemas/           # Pydantic request/response schemas
│   ├── services/          # Adjudication engine (9-step)
│   ├── tests/             # pytest test suite (29 tests)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/           # Axios API client
│   │   ├── components/
│   │   │   ├── member/    # Member tab components
│   │   │   ├── insurer/   # Insurer tab components
│   │   │   └── shared/    # ClaimDetail, StatusBadge, Modal
│   │   └── App.jsx        # Tab switcher root
│   └── package.json
├── docs/
│   ├── domain-model.md    # Entities, state machines, adjudication logic
│   ├── decisions.md       # Design decisions and trade-offs
│   └── self-review.md     # Honest self-assessment
├── ai-artifacts/          # Claude Code JSONL session logs
├── CLAUDE.md              # Project context for AI sessions
└── README.md
```

---

## Docs

- `docs/domain-model.md` — full entity definitions, state machines, 9-step adjudication order, plan rules table
- `docs/decisions.md` — every design decision with trade-off reasoning
- `docs/self-review.md` — honest assessment including bugs found and fixed, known gaps, and what is out of scope
