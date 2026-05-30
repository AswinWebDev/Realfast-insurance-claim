# Decisions & Trade-offs

## Tech Stack Decisions

### Python + FastAPI (Backend)
Chosen for speed of development and built-in OpenAPI docs at `/docs`. FastAPI's Pydantic integration means request validation and response schemas are one layer of code, not two. Alternative was Node/Express — rejected because Python's SQLAlchemy ecosystem is cleaner for domain modeling with an ORM.

### SQLite (Database)
Single file at `app/claims.db`. Zero setup, ships with Python, fully relational, supports foreign keys and transactions. This is the right call for a local-only demo — swapping to Postgres later would require changing the connection string only, not the schema or ORM code.

### SQLAlchemy + Alembic (ORM + Migrations)
SQLAlchemy gives us a proper domain model in Python classes, not raw SQL strings. Alembic gives us migration history — reviewers can see schema evolution via `alembic history`. Alternative was raw SQLite with `sqlite3` module — rejected because it would push SQL into application logic.

### React + Vite (Frontend)
Vite is faster than Create React App and has no config overhead. React is the obvious choice given familiarity. No component library (no Material UI, no Chakra) — plain CSS with a minimal custom stylesheet. This keeps the frontend fast to write and easy to follow.

### No Authentication
Explicitly out of scope per problem statement. Member identity is passed as `member_id` in API requests. In production this would be a JWT claim — the slot exists in every request, just not validated.

---

## Domain Modeling Decisions

### Coverage Rules as Database Rows, Not Code
Coverage rules (annual limits, copay amounts, covered percentages) are stored as `CoverageRule` rows linked to a `Policy`. They are not hardcoded `if` statements. This means:
- Rules can be read and understood without reading code
- The adjudication engine is generic — it reads rules, it doesn't encode them
- Adding a new plan tier requires inserting rows, not editing logic

Trade-off: a DSL (domain-specific language) or rules engine would be more expressive for complex conditions. For this scope, row-based rules are sufficient and more transparent.

### MemberAccumulator as Explicit Table
Rather than computing "amount used" by summing approved line items on every request, we maintain a running `MemberAccumulator` total. This is incremented atomically when a line item is approved.

Trade-off: introduces a write-side consistency requirement — if adjudication fails mid-transaction, the accumulator must not be incremented. Solved by wrapping adjudication in a database transaction.

### Claim Status is Computed, Not Stored
`Claim.status` is derived from its line items on every read:
- All APPROVED → `APPROVED`
- All DENIED → `DENIED`
- Mix → `PARTIALLY_APPROVED`
- Any NEEDS_REVIEW → `UNDER_REVIEW`

Exception: `PAID` and `DISPUTED` are explicit states that override the computed value. These represent human actions (paying out, filing a dispute) that the system records.

Trade-off: slightly more expensive reads. Acceptable for this scale.

### Service Date Determines Benefit Year
`LineItem.service_date` determines which year's accumulators are charged, not `Claim.submission_date`. A claim submitted in January for a December service charges the prior year's accumulators. This matches real insurance behavior.

### Physical Therapy Excluded on Bronze via is_excluded Flag
Rather than simply omitting a Bronze CoverageRule for physical therapy, we insert a row with `is_excluded = true`. This means the denial reason is explicit and queryable: "Physical therapy is not a covered benefit under the Bronze plan." An absent row would produce a generic "service not found" error — worse for the member, worse for auditability.

### Dispute is on LineItem, Not Claim
Members dispute individual decisions, not entire claims. A partially-approved claim might have 3 approved items and 1 denied — the member disputes only the denial. Attaching disputes to line items models this correctly.

### Prior Auth Escalates to NEEDS_REVIEW, Not Hard DENY
In real systems, missing prior auth would be a hard denial. For demo purposes, we escalate to `NEEDS_REVIEW` so we can show the manual review workflow. This is documented as an assumption.

---

## Scope Decisions

### No Provider Network (In/Out of Network)
Real systems apply different reimbursement rates for out-of-network providers. Excluded here — it would require a provider registry and a second set of coverage rules per plan. Noted as a known simplification.

### No Coordination of Benefits
When a member has two insurers, the primary pays first and the secondary picks up remaining costs. Excluded — not needed for the demo and would significantly complicate adjudication.

### No Retroactive Policy Changes
Adjudication uses the policy rules active at the time of `service_date`. If a policy changes mid-year, old claims use old rules. We do not model policy versioning — this is a known gap.

### Dental, Vision, Cosmetic Excluded
All plans explicitly exclude dental procedures, cosmetic surgery, vision correction (LASIK), and elective cosmetic procedures. These are modeled as globally excluded service types — no CoverageRule exists for them. Any claim line item with these service types is denied at the first adjudication step.

### Pre-seeded Policies and Members
Policies (Diamond, Gold, Bronze) and a set of sample members are seeded at startup. The frontend is built around these seeded entities. There is no policy creation or member enrollment UI — that is out of scope per the problem statement.

---

## What I Would Do With More Time

1. **Policy versioning** — right now a policy edit affects all past adjudication. A `policy_version` on each line item would fix this.
2. **Retry/resubmit flow** — currently a denied claim can only be disputed. A resubmit with corrected information would be more realistic.
3. **Audit log** — every state transition on a claim or line item should be written to an immutable audit table with timestamp and actor. Currently transitions are fire-and-forget.
4. **Accumulator recalculation** — if a line item is overturned via dispute, the accumulator should be decremented. This reverse flow is not implemented.
5. **CPT → service_type mapping** — currently the member selects a `service_type` directly. In production, the system would map a submitted CPT code to a service type automatically.
