# Self-Review

## What This Is

An honest assessment of what was built, what was missed the first time, what got fixed, and what is genuinely incomplete. Written after completing the system.

---

## What Works Well

### Domain Model
The core domain decomposition is correct. `Policy → CoverageRule → Member → MemberAccumulator → Claim → LineItem → Dispute` maps directly to real insurance concepts. Coverage rules are stored as data rows, not hardcoded logic — adding a new plan tier requires inserting rows, not editing the engine. The adjudication engine is generic and reads from rules rather than encoding them.

### Adjudication Engine
The 9-step adjudication order is correct: exclusion check → prior auth → annual benefit limit → copay → deductible → co-insurance → limit cap → OOP max → approve. Each step writes a human-readable line to `adjudication_notes` so the member can see exactly how their amount was calculated. Denial reasons are specific strings, not generic codes.

### Accumulator Design
`MemberAccumulator` as an explicit table (not computed by summing line items) is the right call. The three accumulator types — `DEDUCTIBLE`, `OOP_MAX`, `SERVICE_BENEFIT` — correctly model the three independent counters in real insurance. `service_date` on the line item (not `submission_date` on the claim) determines which benefit year's accumulators are charged.

### State Machines
Claim and LineItem have separate state machines as they should. `NEEDS_REVIEW` exists as a distinct line item state to model the prior auth escalation workflow. Claim status is derived from its line items rather than stored separately, with `PAID` and `DISPUTED` as explicit human-action overrides.

### Tests
29 tests covering adjudication math, accumulator isolation, state machine transitions, and dispute lifecycle. Each test name states the business rule being verified. Tests were written before or alongside implementation — the git history shows this.

---

## What Was Wrong and Got Fixed

### Bug 1 — Accumulator Double-Write on Deductible Early Exit (found in engineering review)
When a claim was fully absorbed by the deductible (e.g. Bronze member claiming Primary Care before deductible is met), the early-exit path called `_get_or_create_accumulator` a second time and used `+=` on the already-fetched SQLAlchemy object. This double-incremented the deductible accumulator — a Bronze member would exhaust their $2,500 deductible after only $1,250 in claims.

**Fixed:** replaced the redundant fetch with the `ded_acc` reference already in scope. A regression test was added to catch this specific path.

### Bug 2 — Service Benefit Accumulator Inflated by OOP Adjustment (found by me during testing)
This was the most significant correctness bug in the system. Claude Code missed it in the initial implementation and in the engineering review.

When the OOP max was hit, `approved_amount` was correctly increased to absorb member overflow. However, Step 9 then used this OOP-inflated `approved_amount` to increment the service benefit accumulator — pushing it past the annual limit. A $20,000 Gold Specialist claim (limit: $5,000) would write $18,950 into the accumulator instead of $5,000. Every subsequent Specialist claim for that member would be denied immediately with "limit exhausted," and the accumulator bar in the UI would show way over 100%.

The root cause: `approved_amount` serves two purposes — what insurance pays the provider (which includes OOP absorption), and what counts against the service benefit limit (which must be capped at `remaining_benefit`). These were conflated into the same variable.

**Fixed:** introduced `svc_benefit_charge` as a separate variable that holds the Step 7 capped value and is never touched by the OOP adjustment. `approved_amount` continues to reflect the true payment amount. A regression test was added.

### Bug 3 — NEEDS_REVIEW → APPROVED Manual Review Paid $0 (found during server testing)
The manual review endpoint re-ran adjudication on the line item, but adjudication hit `requires_prior_auth` again at Step 2 and returned `NEEDS_REVIEW` — producing a $0 approval even though the insurer explicitly approved it.

**Fixed:** added `skip_prior_auth=True` flag to `adjudicate_line_item`. The manual review endpoint passes this flag so Step 2 is bypassed and the engine runs the full calculation.

### Bug 4 — Above-Limit Amount Inflating Insurance Payment (found by me during testing)
When a claim exceeds the annual benefit limit, the engine incorrectly added `(insurance_share - approved_amount)` to `member_owes` in Step 7. This cascaded into two errors: (1) `member_owes` was inflated by the above-limit amount, which then fed into the OOP max calculation — making insurance absorb costs it should never pay; (2) `approved_amount` was then inflated by OOP absorption of that phantom member liability.

Example: Bronze Prescription, $20,000 claim, $1,200 limit, OOP $4,500/$8,000 used. Engine was reporting insurance pays $16,500. Correct answer: $6,722 (with OOP used in the original scenario), or $3,597 (fresh member). Amounts above the annual benefit limit are simply not covered — they do not count toward the member's OOP max and the insurer does not pay them.

**Fixed:** removed the line adding above-limit amount to `member_owes`. A regression test was added covering the exact scenario.

### Bug 5 — Above-Limit Amount Does Not Count Toward OOP — UI Gap (found by me during testing)
After fixing Bug 4, a follow-up question during testing revealed a UI clarity issue: a $20,000 Gold LAB claim (annual limit $2,000) showed Insurance Pays $2,000 and Member Pays $2,909, with $15,091 unaccounted for in the summary. The numbers were mathematically correct but the UI gave no explanation of where the remaining amount went — it appeared as if money had disappeared.

In US insurance, amounts above the annual benefit limit are not the member's responsibility. The hospital (provider) writes off the excess under the in-network contractual agreement — they agreed to accept the negotiated rate when they joined the insurer's network. This is called a **contractual adjustment**. The member is never billed for it. It does not count toward the member's OOP max.

**Fixed:** added a fourth "Above Limit (Provider Write-off)" card to the claim summary totals that appears only when the billed amount exceeds insurance + member combined. This makes the accounting complete and explains the gap to the member.

This distinction is specific to the US insurance system (PPO/HMO in-network model). In other countries (including India), insurance reimbursement works differently — there is no chargemaster fiction or contractual write-off. The UI fix applies only to the US model we implemented.

### Bug 6 — Claim Number Race Condition (found in engineering review)
`_claim_number()` used `SELECT COUNT(*) + 1` to generate sequential numbers. Two simultaneous submissions would produce the same claim number and the second would crash with a UNIQUE constraint violation.

**Fixed:** replaced with `CLM-{year}-{uuid[:8].upper()}` — collision-free without needing a sequence table.

---

## UI Issues Found and Fixed

The UI was built to showcase the workflow, not as a production interface. Several issues were caught and fixed during manual testing.

**I identified all of the following. Claude Code fixed them after I raised them.**

### Dispute Button Confusion
After a dispute was UPHELD, the "Flag as Disputed" button reappeared at the claim level because `DENIED` was in the valid states for `canDispute`, and `hasResolvedDispute` wasn't checked. The claim-level "Dispute Claim" button in the member view was also redundant — disputes attach to line items, not claims. "Flag as Disputed" in the insurer view was meaningless — insurers resolve disputes, they don't create them.

**Fixed:** removed "Dispute Claim" from the member view entirely. Removed "Flag as Disputed" from the insurer view entirely. Added `hasResolvedDispute` check so once a dispute is resolved (UPHELD or OVERTURNED) no further dispute buttons appear.

### NEEDS_REVIEW and UNDER_REVIEW Shown as Separate Filter Pills
The insurer tab showed both "UNDER REVIEW" and "NEEDS REVIEW" as separate filter tabs. Clicking UNDER REVIEW showed a claim. Clicking NEEDS REVIEW showed the same claim again. The same claim appeared in both because `claim.status === 'UNDER_REVIEW'` and `line_items.some(l => l.status === 'NEEDS_REVIEW')` are both true for the same object — they describe the same situation at different levels of the model.

**Fixed:** removed the NEEDS REVIEW filter pill. UNDER REVIEW now catches both. The stat card was renamed to "Needs Manual Action" to surface the count that requires human intervention.

### Claim Card in Insurer List Showed Two Badges
Each claim card rendered both an "Under Review" badge and a "Needs Review" badge. Same redundancy as the filter pills.

**Fixed:** show a single badge per card — "Needs Review" when a line item requires manual action, the claim status otherwise.

### Mark as Paid After Dispute Overturn
After overturning a dispute, `compute_claim_status` returned `APPROVED` — correct — but `canPay` was true for the insurer, showing "Mark as Paid". This is the correct behavior. I initially removed the auto-PAID shortcut (which was wrong) and then restored it. The deliberate "Mark as Paid" click is the right flow — the insurer explicitly confirms payment after any approval including post-dispute.

---

## What Is Genuinely Rough

### Web UI Was Not the Initial Suggestion
Claude Code initially suggested a REST API as the interface ("easiest to demo and test"). I pushed for a web UI as it better showcases the workflow to evaluators. Claude Code agreed and built it. The UI is functional for demo purposes but is clearly a flow showcase, not a production interface.

### UI/UX Is Functional, Not Polished
- The "More" expand on line items is the only way to reach "File Dispute" — not immediately obvious to a first-time user
- The accumulator bars have no tooltips explaining what they mean
- No loading skeleton states — the page flickers on member selection
- Mobile layout is not considered
- No empty state illustration — just text

These are acceptable for a demo submission. They would not be acceptable in a member-facing product.

### Accumulator Decrement on Dispute Overturn Not Implemented
When a dispute is overturned and a denied line item becomes approved, the service benefit accumulator is not incremented for the newly approved amount, and if the item was previously approved then denied, the original accumulator write is not reversed. The reverse accumulator flow is missing. This is documented in `docs/decisions.md` and would be a required fix before production use.

### Claim Number Sequence Is Not Human-Friendly
After the race condition fix, claim numbers are `CLM-2026-A3F9C21B` style UUIDs. Real systems use sequential numbers for auditability and customer service lookups. A proper sequence using a database auto-increment or advisory lock would fix this without the collision risk.

### No Audit Log
Every state transition (claim status change, line item adjudication, dispute resolution) should write to an immutable audit table with timestamp and actor. Currently all transitions are fire-and-forget. This means there is no history of who approved what and when.

### Prior Auth Is Simplified
`requires_prior_auth = True` escalates to `NEEDS_REVIEW` in the demo. In a real system, missing prior auth is a hard DENY unless the member can produce the authorization number. The demo workflow allows the insurer to approve anything — including things that legitimately should have been denied.

---

## What Is Out of Scope for This Version

These are deliberately excluded. They are not gaps — they are the next version.

- **Member authentication and login** — out of scope per problem statement
- **Member registration and enrollment** — policies and members are pre-seeded
- **Provider registry and in/out-of-network logic** — would require a second coverage rule set per plan
- **Coordination of Benefits** — multiple insurers for the same member
- **Policy purchase flows and admin panels** — out of scope per problem statement
- **Claims file upload** — members attach EOB documents or provider bills. Not implemented.
- **Dashboards and analytics** — out of scope per problem statement
- **Email or push notifications** — out of scope per problem statement
- **Dispute amount revision** — disputing an approved item's calculated amount is possible in the system but the insurer cannot set a revised amount on OVERTURN. The overturn just re-approves at the original calculated amount.
- **Retroactive policy versioning** — a policy edit today affects all past adjudication
- **CPT → service_type auto-mapping** — members select service type directly; real systems derive it from the CPT code
- **HDHP (High Deductible Health Plan) behavior** — the system models standard PPO/HMO adjudication: copay is deducted first, then the deductible applies to the remainder. HDHPs work differently by IRS rule — no copays until after the deductible is fully met, then copays kick in. Members pay 100% of costs until the deductible is hit. This is a known simplification. All three plans (Diamond, Gold, Bronze) are modeled as PPO-style, not HDHP.
- **US-specific insurance model (chargemaster and provider write-off)** — the system models the US PPO in-network model where hospitals bill an artificially inflated "chargemaster" price and the in-network contracted rate is much lower. Amounts above the annual benefit limit are written off by the provider under their network contract — the member is never balance-billed for it. This behavior (provider write-off, contractual adjustment) is specific to the US system. In other countries, insurance reimbursement works differently — there is no chargemaster pricing, no contractual write-off, and the billed amount is typically the actual cost. The system does not model out-of-network balance billing, which is where US patients face significant unexpected costs when a provider has no contract with their insurer.

---

## Overall Honest Assessment

The backend is production-quality in its domain modeling and adjudication logic. The test suite encodes real business rules. The two correctness bugs that were found and fixed (accumulator double-write and OOP inflation) were genuine — not corner cases. The fact that I caught the OOP bug during manual testing rather than Claude Code catching it in the engineering review is a fair reflection of the limits of AI-assisted review without domain knowledge.

The frontend is a workflow demo. It does the job of showing the full lifecycle — member submits a claim, insurer reviews it, dispute is filed and resolved — but it is not the UI you would ship to members. The interaction patterns are functional but not intuitive enough for a non-technical user.

The domain model is sound. The adjudication engine is correct. The test suite is honest. That is what this assignment asked for.
