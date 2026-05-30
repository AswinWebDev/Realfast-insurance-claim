# CLAUDE.md — RealFast Claims Processing System

## START HERE — Read These First

Before doing anything in a new session, read both of these files in full:

1. `problem_statement.md` — the assignment brief. What must be built, what is in/out of scope, what deliverables are required.
2. `candidate_assignment_instructions.md` — how the work is evaluated. Domain modeling matters more than feature count. Tests must appear before or alongside code (git history is checked). JSONL session logs are mandatory. Self-review doc is required.

Do not write code until you have read both.

---

## What We Are Building

An insurance **Claims Processing System** that runs entirely on localhost. A member submits a claim with line items (medical services), the system adjudicates each line item against coverage rules, and the claim moves through a lifecycle to payment or dispute.

The submission is a take-home assignment for a Forward Deployed Engineer role at RealFast AI. It is evaluated on domain modeling quality, rule representation, state management, explanation capability, and test coverage — not on feature breadth.

---

## Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Backend | Python 3.12 + FastAPI | `app/` directory. Run with uvicorn. |
| Database | SQLite (`claims.db`) | Local file, zero setup. Lives at project root when server runs. |
| ORM | SQLAlchemy 2.0 | Mapped columns, typed relationships. |
| Validation | Pydantic v2 | `use_enum_values=True` on all response schemas. |
| Frontend | React + Vite | `frontend/` directory (not yet built). |
| Tests | pytest + httpx TestClient | `app/tests/`. Uses a separate `test_claims.db` per run. |

**Python version**: Must use Python 3.12. Python 3.14 (system default on this machine) does not have pydantic-core wheels. The venv is at `app/.venv`, created with `python3.12 -m venv .venv`.

**Run backend**:
```bash
cd /Users/aswinvinod/Desktop/realfast-claims
source app/.venv/bin/activate
PYTHONPATH=/Users/aswinvinod/Desktop/realfast-claims uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Run tests**:
```bash
source app/.venv/bin/activate
PYTHONPATH=/Users/aswinvinod/Desktop/realfast-claims python3.12 -m pytest app/tests/ -v
```

---

## Domain Model

### Entities (all in `app/models/models.py`)

```
Policy ──────────────< CoverageRule
  │
  └──────────────────< Member
                         │
                         ├──< MemberAccumulator  (per member, per year, per type)
                         │
                         └──< Claim ──< LineItem ──< Dispute
```

| Entity | Key Fields |
|---|---|
| `Policy` | `tier` (DIAMOND/GOLD/BRONZE), `annual_deductible`, `out_of_pocket_max` |
| `CoverageRule` | `policy_id`, `service_type`, `annual_limit`, `covered_pct`, `copay_amount`, `deductible_applies`, `requires_prior_auth`, `is_excluded` |
| `Member` | `policy_id`, `member_number` (MBR-XXXXX) |
| `MemberAccumulator` | `member_id`, `benefit_year`, `accumulator_type` (DEDUCTIBLE/OOP_MAX/SERVICE_BENEFIT), `service_type` (null for deductible/oop), `amount_used` |
| `Claim` | `member_id`, `status`, `claim_number` (CLM-YYYYNNNN) |
| `LineItem` | `claim_id`, `service_type`, `service_date`, `billed_amount`, `approved_amount`, `member_responsibility`, `status`, `denial_reason`, `adjudication_notes` |
| `Dispute` | `line_item_id`, `reason`, `status` (OPEN/UPHELD/OVERTURNED), `resolution_notes` |

### Covered Service Types (11 total — no dental, no cosmetic)

`PRIMARY_CARE`, `SPECIALIST`, `EMERGENCY_ROOM`, `URGENT_CARE`, `INPATIENT`, `OUTPATIENT_SURGERY`, `LAB`, `IMAGING`, `PRESCRIPTION`, `PHYSICAL_THERAPY`, `MENTAL_HEALTH`

### Plan Rules (seeded at startup via `app/core/seed.py`)

| Plan | Deductible | OOP Max | Physical Therapy |
|---|---|---|---|
| Diamond | $500 | $3,000 | Covered (85%, $30 copay) |
| Gold | $1,000 | $5,000 | Covered (75%, $45 copay) |
| Bronze | $2,500 | $8,000 | **Excluded** (`is_excluded=True`) |

### Seeded Members

| ID | Name | Plan |
|---|---|---|
| `member-001` | Alice Johnson | Diamond |
| `member-002` | Bob Martinez | Gold |
| `member-003` | Carol Chen | Bronze |
| `member-004` | David Park | Diamond |
| `member-005` | Emma Wilson | Gold |

---

## State Machines

### Claim States
```
SUBMITTED → UNDER_REVIEW → APPROVED | PARTIALLY_APPROVED | DENIED
                                  ↓               ↓
                                PAID          DISPUTED
                                  ↓
                              DISPUTED → UPHELD | OVERTURNED
```
Claim status is **computed from line items** after adjudication:
- All APPROVED → `APPROVED`
- All DENIED → `DENIED`
- Any NEEDS_REVIEW → `UNDER_REVIEW`
- Mixed → `PARTIALLY_APPROVED`

`PAID` and `DISPUTED` are explicit overrides set by API calls (human actions).

### LineItem States
```
PENDING → APPROVED | DENIED | NEEDS_REVIEW
                                    ↓
                          APPROVED | DENIED  (manual review)
```

`NEEDS_REVIEW` triggers when `requires_prior_auth=True` on the coverage rule.

---

## Adjudication Engine (`app/services/adjudication.py`)

The core of the system. Runs per `LineItem` in this exact order:

1. **Coverage check** — is `service_type` in the policy? Is it `is_excluded`? → DENY with specific reason
2. **Prior auth check** — if `requires_prior_auth`, escalate to `NEEDS_REVIEW`
3. **Annual benefit limit check** — load `SERVICE_BENEFIT` accumulator, check remaining
4. **Copay deduction** — subtract from billed; if billed ≤ copay, approve for $0 insurance
5. **Deductible** — if `deductible_applies`, charge against `DEDUCTIBLE` accumulator first
6. **Co-insurance** — insurance pays `covered_pct` of remainder; member pays `1 - covered_pct`
7. **Benefit limit cap** — cap insurance share at remaining `SERVICE_BENEFIT` accumulator
8. **OOP max** — if member's total out-of-pocket hits `out_of_pocket_max`, insurance absorbs excess
9. **Approve** — write `approved_amount`, `member_responsibility`, increment all three accumulators

Every step writes a human-readable line to `adjudication_notes`. Every denial writes a specific `denial_reason` string.

**Critical invariant**: accumulators are per-member per-year. `service_date` on the line item (not submission date) determines the benefit year. Never put `amount_used` on the `CoverageRule` — it is shared across all members on that plan.

---

## API Routes

All routes prefixed with `/api`. Auto-docs at `http://localhost:8000/docs`.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/members/` | List all members (includes policy name/tier) |
| `GET` | `/api/members/{id}` | Member detail with accumulators |
| `GET` | `/api/policies/` | List all policies with coverage rules |
| `GET` | `/api/policies/{id}` | Single policy |
| `POST` | `/api/claims/` | Submit claim — triggers adjudication immediately |
| `GET` | `/api/claims/` | List claims (optional `?member_id=` filter) |
| `GET` | `/api/claims/{id}` | Single claim with line items and disputes |
| `PATCH` | `/api/claims/{id}/status` | Move claim through lifecycle (PAID, DISPUTED, etc.) |
| `PATCH` | `/api/claims/{id}/line-items/{lid}/review` | Resolve NEEDS_REVIEW → APPROVED or DENIED |
| `POST` | `/api/claims/{id}/line-items/{lid}/disputes` | File a dispute on a line item |
| `PATCH` | `/api/claims/{id}/line-items/{lid}/disputes/{did}` | Resolve dispute (UPHELD or OVERTURNED) |

---

## Tests (`app/tests/test_adjudication.py`)

25 tests, all passing. Five groups, each testing domain behaviour not just HTTP status codes:

| Group | What it tests |
|---|---|
| `TestCoverageRules` | PT excluded on Bronze, covered on Diamond/Gold; LAB 100% on Diamond; unknown service type rejected |
| `TestAdjudicationMath` | Copay + co-insurance arithmetic; deductible before co-insurance; billed-below-copay edge case; deductible exhaustion then co-insurance |
| `TestAccumulators` | Limit exhaustion → DENIED; partial limit → partial approval; per-member isolation; service_date drives benefit year |
| `TestClaimStatus` | APPROVED/DENIED/PARTIALLY_APPROVED/UNDER_REVIEW derived correctly from line items |
| `TestClaimLifecycle` | Valid transitions (APPROVED→PAID); invalid transitions rejected (DENIED→PAID); dispute flow |
| `TestDisputes` | File dispute; duplicate rejected; OVERTURNED → line item APPROVED; UPHELD → line item stays DENIED |

---

## Current Implementation Status

| Area | Status |
|---|---|
| Domain models + schema | Done |
| Seed data (3 plans, 11 rules each, 5 members) | Done |
| Adjudication engine (9-step) | Done |
| REST API (claims, members, policies, disputes) | Done |
| Tests (25 passing) | Done |
| Frontend (React + Vite) | **Not started** |
| `docs/self-review.md` | Not started |
| `README.md` | Not started |
| Git history initialised | Not started |

**Next task: React frontend.** Located at `frontend/`. Needs: member selector, claim submission form, claim detail view with adjudication notes, dispute filing, claim status transition buttons.

---

## Key Design Decisions (see `docs/decisions.md` for full reasoning)

- **Coverage rules as DB rows** — adjudication engine is generic, reads rules, doesn't encode them. Adding a new plan = inserting rows.
- **MemberAccumulator as explicit table** — not computed by summing line items. Incremented atomically inside the same DB transaction as adjudication.
- **Physical Therapy on Bronze stored as `is_excluded=True`** — not a missing row. Produces a specific, queryable denial reason.
- **Disputes attach to LineItems** — members dispute individual decisions, not whole claims.
- **`service_date` drives benefit year** — a December service on a January-submitted claim charges the prior year's accumulators.
- **Prior auth escalates to NEEDS_REVIEW** — not a hard DENY in this demo, to allow the manual review workflow to be demonstrated.

---

## What Is Explicitly Out of Scope

Per the problem statement — do not build these, they will not improve the score:
- Authentication / login
- Policy purchase or enrollment
- Provider registry or in/out-of-network logic
- Email notifications
- Admin panels
- Multi-tenant access control
- Dental, vision, or cosmetic service types

---

## Submission Checklist

| Item | Status |
|---|---|
| `app/` — working application | Done |
| `docs/domain-model.md` | Done |
| `docs/decisions.md` | Done |
| `docs/self-review.md` | Pending |
| `README.md` — setup and run instructions | Pending |
| `ai-artifacts/` — JSONL session logs (mandatory) | Pending — locate logs before submitting |
| `.git/` — full commit history | Pending — init git and commit incrementally |

**JSONL logs location**: Claude Code stores session logs at `~/.claude/projects/`. Run `ls ~/.claude/projects/` to find the log directory for this project. Include all `.jsonl` files in `ai-artifacts/`.
