# Domain Model

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| **Backend** | Python + FastAPI | Fast to write, excellent for REST APIs, auto-generates OpenAPI docs |
| **Database** | SQLite (local file) | Zero setup, file-based, correct relational schema, good enough for local demo |
| **ORM** | SQLAlchemy + Alembic | Proper schema migrations, clean model definitions |
| **Frontend** | React + Vite | Lightweight, fast dev server, no build complexity |
| **HTTP Client** | Axios | Standard for React → REST API calls |
| **Validation** | Pydantic v2 | Request/response schemas, FastAPI-native |

The database lives at `app/claims.db` — a single SQLite file. No Docker, no Postgres, no setup beyond `pip install` and `npm install`.

---

## Covered Service Types

These are the only service types the system recognizes. Dental and cosmetic procedures are explicitly excluded across all plans.

| Service Type | Code |
|---|---|
| Primary Care Visit | `PRIMARY_CARE` |
| Specialist Visit | `SPECIALIST` |
| Emergency Room | `EMERGENCY_ROOM` |
| Urgent Care | `URGENT_CARE` |
| Inpatient Hospitalization | `INPATIENT` |
| Outpatient Surgery | `OUTPATIENT_SURGERY` |
| Lab / Pathology | `LAB` |
| Imaging (X-Ray, MRI, CT) | `IMAGING` |
| Prescription Drugs | `PRESCRIPTION` |
| Physical Therapy | `PHYSICAL_THERAPY` |
| Mental Health (Outpatient) | `MENTAL_HEALTH` |

**Explicitly excluded (all plans):**
- Dental procedures
- Cosmetic procedures
- Vision correction (LASIK etc.)
- Elective cosmetic surgery

---

## Entities & Relationships

```
Policy ──────────< CoverageRule
  │
  └──────────────< Member
                     │
                     ├──< MemberAccumulator
                     │
                     └──< Claim ──< LineItem ──< Dispute
```

---

## Entity Definitions

### Policy

Represents an insurance plan tier. Shared by many members.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | string | e.g., "Diamond Plan" |
| `tier` | enum | `DIAMOND`, `GOLD`, `BRONZE` |
| `annual_deductible` | decimal | Amount member pays before insurance kicks in |
| `out_of_pocket_max` | decimal | Annual cap on member's total spend |
| `effective_date` | date | When this policy version took effect |

### CoverageRule

One row per covered service type per policy. Defines exactly what the insurance will pay and under what conditions.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `policy_id` | UUID | FK → Policy |
| `service_type` | enum | One of the covered service codes above |
| `annual_limit` | decimal | Max insurance pays per year for this service type |
| `covered_pct` | decimal | e.g., 0.80 = insurance pays 80% after deductible |
| `copay_amount` | decimal | Fixed member payment per visit (applied before deductible) |
| `deductible_applies` | bool | Does the annual deductible apply before the % kicks in? |
| `requires_prior_auth` | bool | Must be pre-authorized before service |
| `is_excluded` | bool | Explicitly not covered (used for per-plan exclusions like PT on Bronze) |

### Member

An insured individual enrolled in a policy.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | string | Full name |
| `date_of_birth` | date | |
| `policy_id` | UUID | FK → Policy — which plan they are on |
| `enrollment_date` | date | When they enrolled |
| `member_number` | string | Human-readable ID (e.g., `MBR-00042`) |

### MemberAccumulator

Tracks how much a member has spent/used against each annual limit. **Per member, per benefit year.** This is what makes adjudication stateful.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `member_id` | UUID | FK → Member |
| `benefit_year` | int | Calendar year (e.g., 2026) |
| `accumulator_type` | enum | `DEDUCTIBLE`, `OOP_MAX`, `SERVICE_BENEFIT` |
| `service_type` | enum | Null for DEDUCTIBLE and OOP_MAX; set for SERVICE_BENEFIT |
| `amount_used` | decimal | Running total charged against this limit |

Unique constraint: `(member_id, benefit_year, accumulator_type, service_type)`.

### Claim

A member's request for reimbursement. Contains one or more line items.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `claim_number` | string | Human-readable (e.g., `CLM-20260001`) |
| `member_id` | UUID | FK → Member |
| `provider_name` | string | Name of the clinic/hospital |
| `provider_npi` | string | National Provider Identifier (optional) |
| `submission_date` | datetime | When member submitted this claim |
| `status` | enum | See state machine below |
| `notes` | text | Internal reviewer notes |

### LineItem

A single service within a claim. Adjudicated individually.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `claim_id` | UUID | FK → Claim |
| `service_type` | enum | Maps to a CoverageRule |
| `procedure_code` | string | CPT code (e.g., `99213`) |
| `diagnosis_code` | string | ICD-10 code (e.g., `J06.9`) |
| `service_date` | date | Date service was rendered — determines benefit year for accumulators |
| `billed_amount` | decimal | What the provider charged |
| `approved_amount` | decimal | What insurance will pay (set after adjudication) |
| `member_responsibility` | decimal | What the member owes (copay + deductible + co-insurance share) |
| `status` | enum | See state machine below |
| `denial_reason` | string | Specific explanation if denied (null if approved) |
| `adjudication_notes` | text | Step-by-step breakdown of how the amount was calculated |

### Dispute

A member's challenge to a line item decision.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `line_item_id` | UUID | FK → LineItem |
| `submitted_at` | datetime | |
| `reason` | text | Member's stated reason for dispute |
| `status` | enum | `OPEN`, `UPHELD`, `OVERTURNED` |
| `resolution_notes` | text | Explanation of outcome |
| `resolved_at` | datetime | Null if still open |

---

## State Machines

### Claim States

```
                    ┌─────────────┐
                    │  SUBMITTED  │
                    └──────┬──────┘
                           │ (auto-triggered on submission)
                    ┌──────▼──────┐
                    │ UNDER_REVIEW│
                    └──────┬──────┘
            ┌──────────────┼──────────────┐
            │              │              │
     ┌──────▼─────┐ ┌──────▼──────┐ ┌───▼────┐
     │  APPROVED  │ │ PARTIALLY_  │ │ DENIED │
     │            │ │  APPROVED   │ │        │
     └──────┬─────┘ └──────┬──────┘ └───┬────┘
            │              │             │
            └──────┬───────┘             │
                   │                     │
            ┌──────▼──────┐              │
            │    PAID     │              │
            └──────┬──────┘              │
                   │                     │
            ┌──────▼──────────────────── ▼──────┐
            │           DISPUTED                │
            └──────┬────────────────────────────┘
                   │
         ┌─────────┴─────────┐
   ┌─────▼──────┐     ┌──────▼──────┐
   │  UPHELD    │     │ OVERTURNED  │
   └────────────┘     └─────────────┘
```

**Claim status is computed from its line items:**
- All line items APPROVED → Claim: `APPROVED`
- All line items DENIED → Claim: `DENIED`
- Mix of APPROVED + DENIED → Claim: `PARTIALLY_APPROVED`
- Any line item `NEEDS_REVIEW` → Claim stays `UNDER_REVIEW`

Claim transitions to `PAID` manually (simulates payment processing).
Claim or any line item can be moved to `DISPUTED` from `APPROVED`, `PARTIALLY_APPROVED`, `DENIED`, or `PAID`.

### LineItem States

```
         ┌─────────┐
         │ PENDING │
         └────┬────┘
              │ (adjudication runs)
    ┌─────────┼──────────┐
    │         │          │
┌───▼───┐ ┌──▼───┐ ┌────▼───────┐
│APPROVED│ │DENIED│ │NEEDS_REVIEW│
└───┬───┘ └──┬───┘ └─────┬──────┘
    │        │            │ (manual decision)
    │        │      ┌─────┴──────┐
    │        │      │            │
    │   ┌────▼──┐ ┌─▼──────┐  (loops back)
    │   │DISPUT-│ │APPROVED│
    │   │  ED   │ │or DENIED│
    └───►       │ └────────┘
        └───────┘
```

**NEEDS_REVIEW triggers when:**
- Billed amount exceeds a threshold (e.g., > $5,000)
- `requires_prior_auth` is true but no auth documented
- Service date is more than 90 days before submission

---

## Adjudication Order of Operations

For each `LineItem`, run in this exact order:

```
1. SERVICE COVERAGE CHECK
   → Find CoverageRule for (policy, service_type)
   → If no rule found OR rule.is_excluded = true:
      DENY("Service type [X] is not covered under your [Plan] plan")

2. PRIOR AUTH CHECK
   → If rule.requires_prior_auth = true:
      DENY("Prior authorization is required for [service_type] but was not obtained")
      [simplified: we flag this as NEEDS_REVIEW instead of hard DENY for demo]

3. ANNUAL BENEFIT LIMIT CHECK
   → Load SERVICE_BENEFIT accumulator for (member, service_type, benefit_year)
   → remaining = rule.annual_limit - accumulator.amount_used
   → If remaining <= 0:
      DENY("Annual benefit limit of $[X] for [service_type] has been fully exhausted")

4. COPAY DEDUCTION
   → member_owes = rule.copay_amount
   → adjudicable_amount = billed_amount - copay_amount
   → If adjudicable_amount <= 0:
      APPROVE for $0 insurance payment (member pays all via copay)

5. DEDUCTIBLE APPLICATION (if rule.deductible_applies = true)
   → Load DEDUCTIBLE accumulator for (member, benefit_year)
   → deductible_remaining = policy.annual_deductible - deductible_accumulator.amount_used
   → member_owes += min(adjudicable_amount, deductible_remaining)
   → adjudicable_amount = max(0, adjudicable_amount - deductible_remaining)
   → If adjudicable_amount = 0:
      APPROVE for $0 (all applied to deductible)

6. CO-INSURANCE APPLICATION
   → insurance_share = adjudicable_amount * rule.covered_pct
   → member_coinsurance = adjudicable_amount * (1 - rule.covered_pct)
   → member_owes += member_coinsurance

7. ANNUAL BENEFIT LIMIT CAP
   → approved_amount = min(insurance_share, remaining_from_step_3)

8. OUT-OF-POCKET MAX CHECK
   → Load OOP_MAX accumulator for (member, benefit_year)
   → oop_remaining = policy.out_of_pocket_max - oop_accumulator.amount_used
   → If member_owes > oop_remaining:
      → excess = member_owes - oop_remaining
      → approved_amount += excess  (insurance absorbs the overage)
      → member_owes = oop_remaining

9. APPROVE
   → line_item.approved_amount = approved_amount
   → line_item.member_responsibility = member_owes
   → line_item.status = APPROVED
   → Increment accumulators:
      - SERVICE_BENEFIT += approved_amount
      - DEDUCTIBLE += amount applied in step 5
      - OOP_MAX += member_owes
```

Every step that results in a DENY writes a specific human-readable `denial_reason`. The `adjudication_notes` field stores the full step-by-step breakdown so a member can see exactly how their payment was calculated.

---

## Plan Rules (Seed Data)

### Diamond Plan

| Service Type | Annual Limit | Covered % | Copay | Deductible Applies | Prior Auth |
|---|---|---|---|---|---|
| Primary Care | $5,000 | 90% | $10 | No | No |
| Specialist | $8,000 | 85% | $30 | Yes | No |
| Emergency Room | $20,000 | 90% | $100 | Yes | No |
| Urgent Care | $5,000 | 90% | $25 | No | No |
| Inpatient | $50,000 | 85% | $250 | Yes | Yes |
| Outpatient Surgery | $30,000 | 85% | $150 | Yes | Yes |
| Lab | $3,000 | 100% | $0 | No | No |
| Imaging | $5,000 | 90% | $50 | Yes | No |
| Prescription | $4,000 | 80% | $15 | No | No |
| Physical Therapy | $5,000 | 85% | $30 | Yes | No |
| Mental Health | $6,000 | 90% | $20 | Yes | No |

Annual Deductible: **$500** | OOP Max: **$3,000**

### Gold Plan

| Service Type | Annual Limit | Covered % | Copay | Deductible Applies | Prior Auth |
|---|---|---|---|---|---|
| Primary Care | $3,000 | 80% | $20 | Yes | No |
| Specialist | $5,000 | 75% | $50 | Yes | No |
| Emergency Room | $15,000 | 80% | $150 | Yes | No |
| Urgent Care | $3,000 | 80% | $40 | Yes | No |
| Inpatient | $35,000 | 75% | $400 | Yes | Yes |
| Outpatient Surgery | $20,000 | 75% | $200 | Yes | Yes |
| Lab | $2,000 | 90% | $10 | Yes | No |
| Imaging | $3,000 | 80% | $75 | Yes | No |
| Prescription | $2,500 | 70% | $25 | Yes | No |
| Physical Therapy | $3,000 | 75% | $45 | Yes | No |
| Mental Health | $4,000 | 80% | $35 | Yes | No |

Annual Deductible: **$1,000** | OOP Max: **$5,000**

### Bronze Plan

| Service Type | Annual Limit | Covered % | Copay | Deductible Applies | Prior Auth |
|---|---|---|---|---|---|
| Primary Care | $1,500 | 60% | $40 | Yes | No |
| Specialist | $2,500 | 55% | $75 | Yes | No |
| Emergency Room | $10,000 | 65% | $250 | Yes | No |
| Urgent Care | $1,500 | 60% | $60 | Yes | No |
| Inpatient | $20,000 | 60% | $600 | Yes | Yes |
| Outpatient Surgery | $10,000 | 60% | $300 | Yes | Yes |
| Lab | $1,000 | 70% | $20 | Yes | No |
| Imaging | $1,500 | 65% | $100 | Yes | No |
| Prescription | $1,200 | 55% | $40 | Yes | No |
| Physical Therapy | — | — | — | — | — |
| Mental Health | $2,000 | 60% | $50 | Yes | No |

Annual Deductible: **$2,500** | OOP Max: **$8,000**

> Physical Therapy: **NOT COVERED** on Bronze. CoverageRule row exists with `is_excluded = true` so the denial reason is explicit.

---

## Denial Reason Taxonomy

These are the exact strings the system produces. Reviewers should be able to read them without translation.

| Code | Denial Reason String |
|---|---|
| `NOT_COVERED` | "Service type [X] is not covered under your [Plan] plan" |
| `EXCLUDED` | "Physical therapy is not a covered benefit under the Bronze plan" |
| `LIMIT_EXHAUSTED` | "Annual benefit limit of $[X] for [service_type] has been fully exhausted for benefit year [Y]" |
| `LIMIT_PARTIAL` | "Annual benefit limit of $[X] for [service_type] has $[remaining] remaining; claim approved for partial amount" |
| `PRIOR_AUTH` | "Prior authorization is required for [service_type] — flagged for manual review" |
| `DEDUCTIBLE_ONLY` | "Full billed amount applied to outstanding deductible of $[X]; $0 payable by insurance at this time" |
| `COPAY_EXCEEDS` | "Billed amount of $[X] does not exceed the applicable copay of $[Y]; member responsible for full amount" |

---

## What Is Out of Scope (and Why)

| Excluded | Reason |
|---|---|
| Authentication / login | Not in scope per problem statement |
| Policy purchase / enrollment | Pre-seeded policies; enrollment via seed data |
| Provider network (in/out of network) | Simplifies adjudication; noted as assumption |
| Coordination of Benefits (multiple insurers) | Real-world complexity not needed for demo |
| Retroactive policy changes | Adjudication uses policy at time of service date |
| Appeals time limits | Dispute can be filed at any time in demo |
| Dental, vision, cosmetic | Explicitly excluded per requirements |
