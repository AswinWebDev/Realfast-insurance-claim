"""
Tests encode domain rules — each test name states the business rule being verified.
"""
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def submit(client: TestClient, member_id: str, line_items: list) -> dict:
    resp = client.post("/api/claims/", json={
        "member_id": member_id,
        "provider_name": "Test Clinic",
        "line_items": line_items,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def li(service_type: str, billed: float, date: str = "2026-06-01") -> dict:
    return {"service_type": service_type, "service_date": date, "billed_amount": billed}


# ---------------------------------------------------------------------------
# Coverage / exclusion
# ---------------------------------------------------------------------------

class TestCoverageRules:
    def test_physical_therapy_denied_on_bronze(self, client):
        claim = submit(client, "member-003", [li("PHYSICAL_THERAPY", 300)])
        item = claim["line_items"][0]
        assert item["status"] == "DENIED"
        assert "not a covered benefit" in item["denial_reason"]
        assert item["approved_amount"] == "0.00"

    def test_physical_therapy_approved_on_diamond(self, client):
        # Diamond PT has deductible_applies=True so a $300 claim on a fresh deductible
        # goes entirely to deductible — still APPROVED, insurance just pays $0 this claim.
        claim = submit(client, "member-001", [li("PHYSICAL_THERAPY", 300)])
        item = claim["line_items"][0]
        assert item["status"] == "APPROVED"
        assert item["denial_reason"] is None or "deductible" in item["denial_reason"].lower()

    def test_physical_therapy_approved_on_gold(self, client):
        claim = submit(client, "member-002", [li("PHYSICAL_THERAPY", 300)])
        item = claim["line_items"][0]
        assert item["status"] == "APPROVED"

    def test_lab_has_no_copay_on_diamond(self, client):
        claim = submit(client, "member-001", [li("LAB", 500)])
        item = claim["line_items"][0]
        assert item["status"] == "APPROVED"
        assert Decimal(item["approved_amount"]) == Decimal("500.00")
        assert Decimal(item["member_responsibility"]) == Decimal("0.00")

    def test_unknown_service_type_rejected_by_api(self, client):
        resp = client.post("/api/claims/", json={
            "member_id": "member-001",
            "provider_name": "Clinic",
            "line_items": [{"service_type": "DENTAL", "service_date": "2026-06-01", "billed_amount": 200}],
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Adjudication math
# ---------------------------------------------------------------------------

class TestAdjudicationMath:
    def test_diamond_primary_care_copay_and_coinsurance(self, client):
        # Diamond: PRIMARY_CARE copay=$10, deductible does NOT apply, covered 90%
        # billed=$350 → adjudicable=$340 → insurance=90%*340=$306, member=$10+$34=$44
        claim = submit(client, "member-001", [li("PRIMARY_CARE", 350)])
        item = claim["line_items"][0]
        assert item["status"] == "APPROVED"
        assert Decimal(item["approved_amount"]) == Decimal("306.00")
        assert Decimal(item["member_responsibility"]) == Decimal("44.00")

    def test_bronze_deductible_applied_before_coinsurance(self, client):
        # Bronze: PRIMARY_CARE copay=$40, deductible=$2500 applies
        # billed=$200 → adjudicable=$160 → entire $160 applied to deductible → $0 insurance
        claim = submit(client, "member-003", [li("PRIMARY_CARE", 200)])
        item = claim["line_items"][0]
        assert item["status"] == "APPROVED"
        assert Decimal(item["approved_amount"]) == Decimal("0.00")
        assert Decimal(item["member_responsibility"]) == Decimal("200.00")

    def test_billed_amount_below_copay_insurance_pays_nothing(self, client):
        # Gold: SPECIALIST copay=$50, billed=$30 → adjudicable=-$20 → $0 insurance
        claim = submit(client, "member-002", [li("SPECIALIST", 30)])
        item = claim["line_items"][0]
        assert item["status"] == "APPROVED"
        assert Decimal(item["approved_amount"]) == Decimal("0.00")

    def test_deductible_accumulator_not_double_incremented_on_early_exit(self, client):
        # Bronze PRIMARY_CARE: copay=$40, deductible=$2500 applies.
        # billed=$200 → adjudicable=$160 → all $160 hits deductible → early exit.
        # Submit twice. Deductible used should be $160+$160=$320, not $320+$320=$640.
        submit(client, "member-003", [li("PRIMARY_CARE", 200)])
        submit(client, "member-003", [li("PRIMARY_CARE", 200)])
        from fastapi.testclient import TestClient
        resp = client.get("/api/members/member-003")
        accums = resp.json()["accumulators"]
        ded = next((a for a in accums if a["accumulator_type"] == "DEDUCTIBLE"), None)
        assert ded is not None
        assert Decimal(ded["amount_used"]) == Decimal("320.00"), (
            f"Expected $320.00 deductible used, got ${ded['amount_used']} — double-write bug"
        )

    def test_gold_lab_coinsurance_after_deductible(self, client):
        # Gold: LAB copay=$10, deductible=$1000 applies, covered 90%
        # First submit a large claim to exhaust deductible, then test coinsurance
        # Exhaust deductible with a big PRIMARY_CARE claim
        submit(client, "member-002", [li("PRIMARY_CARE", 2000)])
        # Now deductible should be met — next LAB claim should hit coinsurance
        claim2 = submit(client, "member-002", [li("LAB", 500)])
        item = claim2["line_items"][0]
        assert item["status"] == "APPROVED"
        # copay=$10, adjudicable=$490, deductible already met, insurance=90%*490=$441
        assert Decimal(item["approved_amount"]) == Decimal("441.00")


# ---------------------------------------------------------------------------
# Accumulators
# ---------------------------------------------------------------------------

class TestAccumulators:
    def test_annual_benefit_limit_exhausted_after_repeated_claims(self, client):
        # Diamond: LAB limit=$3000. Submit $1500 twice → third claim denied
        submit(client, "member-001", [li("LAB", 1500)])
        submit(client, "member-001", [li("LAB", 1500)])
        claim3 = submit(client, "member-001", [li("LAB", 500)])
        item = claim3["line_items"][0]
        assert item["status"] == "DENIED"
        assert "exhausted" in item["denial_reason"]

    def test_partial_approval_when_limit_partially_remaining(self, client):
        # Diamond: LAB limit=$3000. Use $2800, then claim $500 → partial $200 approved
        submit(client, "member-001", [li("LAB", 2800)])
        claim2 = submit(client, "member-001", [li("LAB", 500)])
        item = claim2["line_items"][0]
        assert item["status"] == "APPROVED"
        assert Decimal(item["approved_amount"]) == Decimal("200.00")

    def test_accumulators_are_per_member_not_shared(self, client):
        # Alice (Diamond) exhausts her LAB limit — Bob (Gold) is unaffected
        submit(client, "member-001", [li("LAB", 3000)])
        bob_claim = submit(client, "member-002", [li("LAB", 500)])
        item = bob_claim["line_items"][0]
        assert item["status"] == "APPROVED"

    def test_service_date_determines_benefit_year(self, client):
        # Claim for Dec 2025 should not touch 2026 accumulators
        submit(client, "member-001", [li("LAB", 3000, date="2025-12-01")])
        claim_2026 = submit(client, "member-001", [li("LAB", 500, date="2026-06-01")])
        item = claim_2026["line_items"][0]
        assert item["status"] == "APPROVED"


# ---------------------------------------------------------------------------
# Claim status derived from line items
# ---------------------------------------------------------------------------

class TestClaimStatus:
    def test_all_approved_claim_status_is_approved(self, client):
        claim = submit(client, "member-001", [li("LAB", 100), li("PRIMARY_CARE", 100)])
        assert claim["status"] == "APPROVED"

    def test_all_denied_claim_status_is_denied(self, client):
        # Bronze member: both PT (excluded) and exhaust limits
        # Use two PT line items — both denied
        claim = submit(client, "member-003", [
            li("PHYSICAL_THERAPY", 100),
            li("PHYSICAL_THERAPY", 200),
        ])
        assert claim["status"] == "DENIED"

    def test_mixed_line_items_produce_partially_approved(self, client):
        # Bronze: PRIMARY_CARE approved (deductible), PHYSICAL_THERAPY denied (excluded)
        claim = submit(client, "member-003", [
            li("PRIMARY_CARE", 200),
            li("PHYSICAL_THERAPY", 300),
        ])
        assert claim["status"] == "PARTIALLY_APPROVED"

    def test_needs_review_keeps_claim_under_review(self, client):
        # INPATIENT on Gold requires prior_auth → NEEDS_REVIEW
        claim = submit(client, "member-002", [li("INPATIENT", 5000)])
        assert claim["line_items"][0]["status"] == "NEEDS_REVIEW"
        assert claim["status"] == "UNDER_REVIEW"


# ---------------------------------------------------------------------------
# State machine transitions
# ---------------------------------------------------------------------------

class TestOopMax:
    def test_oop_max_caps_member_responsibility(self, client):
        # Diamond OOP max=$3000. Use MENTAL_HEALTH (limit=$6000, 90% covered, copay=$20, deductible applies).
        # Deductible=$500 first. Claim $300: adjudicable=$280, deductible absorbs $280 → member=$300, insurance=$0.
        # After 2 such claims: deductible used=$560 > $500, so deductible met mid-claim-2.
        # Use a simpler approach: submit claims where member owes ~$100 each, push to OOP.
        # MENTAL_HEALTH Diamond: copay=$20, deductible=$500 applies, 90% covered, limit=$6000.
        # After deductible is met: $200 claim → adjudicable=$180, insurance=90%*180=$162, member=$20+$18=$38.
        # First exhaust deductible: submit $600 claim: adjudicable=$580, deductible=$500 applied,
        #   remaining=$80, insurance=90%*80=$72, member=$20+$500+$8=$528.
        # Now OOP used=$528. Remaining OOP=$3000-528=$2472.
        # Each subsequent $200 claim: member=$38. Need 2472/38≈65 more claims to hit OOP.
        # Too many — use larger claims. $500 claim after deductible: adjudicable=$480, ins=90%*480=$432,
        #   member=$20+$48=$68. Need 2472/68≈36 more. Still too many.
        # Better: use SPECIALIST (deductible applies, copay=$30, 85% covered, limit=$8000).
        # $1000 claim after deductible met: adjudicable=$970, ins=85%*970=$824.50, member=$30+$145.50=$175.50.
        # First claim hits deductible: $1000 → adjudicable=$970, ded=$500 remaining, ded_applied=$500,
        #   after_ded=$470, ins=85%*470=$399.50, member=$30+$500+$70.50=$600.50.
        # OOP after claim 1: $600.50. Remaining: $2399.50.
        # Subsequent $1000 SPECIALIST: member=$175.50. Need 2399.50/175.50≈13.67 → 14 more claims.
        # 14*$1000 SPECIALIST + 1 = total insurance = 14*$824.50=$11543, but limit=$8000.
        # Limit exhausted after ~9-10 claims. Still a problem.
        # Cleanest approach: use a service with NO annual limit cap concern.
        # EMERGENCY_ROOM Diamond: limit=$20000, copay=$100, deductible applies, 90% covered.
        # $300 claim: adjudicable=$200, deductible absorbs up to $500.
        # Push deductible first with 1 large ER claim: $600 → adjudicable=$500, ded=$500 applied,
        #   after_ded=$0 → approved=$0, member=$600. OOP=$600.
        # Then small ER claims: $200 → adjudicable=$100, ins=90%*100=$90, member=$100+$10=$110.
        # Need ($3000-$600)/$110 = 21.8 → 22 more $200 ER claims.
        # Insurance total: 22*$90=$1980 << $20000 limit. OOP total: $600+22*$110=$3020 > $3000. ✓
        submit(client, "member-001", [li("EMERGENCY_ROOM", 600)])
        for _ in range(21):
            submit(client, "member-001", [li("EMERGENCY_ROOM", 200)])
        claim_final = submit(client, "member-001", [li("EMERGENCY_ROOM", 200)])
        item = claim_final["line_items"][0]
        assert item["status"] == "APPROVED"
        assert Decimal(item["member_responsibility"]) < Decimal("110.00"), (
            "OOP max should cap member responsibility once $3000 annual limit is reached"
        )


class TestClaimLifecycle:
    def test_approved_claim_can_be_marked_paid(self, client):
        claim = submit(client, "member-001", [li("LAB", 100)])
        assert claim["status"] == "APPROVED"
        resp = client.patch(f"/api/claims/{claim['id']}/status", json={"status": "PAID"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "PAID"

    def test_denied_claim_cannot_be_marked_paid(self, client):
        claim = submit(client, "member-003", [li("PHYSICAL_THERAPY", 300)])
        assert claim["status"] == "DENIED"
        resp = client.patch(f"/api/claims/{claim['id']}/status", json={"status": "PAID"})
        assert resp.status_code == 400

    def test_denied_claim_can_be_disputed(self, client):
        claim = submit(client, "member-003", [li("PHYSICAL_THERAPY", 300)])
        resp = client.patch(f"/api/claims/{claim['id']}/status", json={"status": "DISPUTED"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "DISPUTED"

    def test_invalid_transition_rejected(self, client):
        claim = submit(client, "member-001", [li("LAB", 100)])
        # Cannot jump from APPROVED directly to UNDER_REVIEW
        resp = client.patch(f"/api/claims/{claim['id']}/status", json={"status": "UNDER_REVIEW"})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Disputes
# ---------------------------------------------------------------------------

class TestDisputes:
    def test_manual_review_denied_outcome(self, client):
        claim = submit(client, "member-002", [li("INPATIENT", 5000)])
        li_id = claim["line_items"][0]["id"]
        assert claim["line_items"][0]["status"] == "NEEDS_REVIEW"
        resp = client.patch(
            f"/api/claims/{claim['id']}/line-items/{li_id}/review",
            json={"outcome": "DENIED", "notes": "Prior auth not approved"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "DENIED"
        assert resp.json()["denial_reason"] == "Prior auth not approved"

    def test_member_can_dispute_denied_line_item(self, client):
        claim = submit(client, "member-003", [li("PHYSICAL_THERAPY", 300)])
        item_id = claim["line_items"][0]["id"]
        resp = client.post(
            f"/api/claims/{claim['id']}/line-items/{item_id}/disputes",
            json={"reason": "My doctor said this is medically necessary"},
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "OPEN"

    def test_duplicate_open_dispute_rejected(self, client):
        claim = submit(client, "member-003", [li("PHYSICAL_THERAPY", 300)])
        item_id = claim["line_items"][0]["id"]
        client.post(
            f"/api/claims/{claim['id']}/line-items/{item_id}/disputes",
            json={"reason": "My doctor said this is medically necessary"},
        )
        resp = client.post(
            f"/api/claims/{claim['id']}/line-items/{item_id}/disputes",
            json={"reason": "Filing again"},
        )
        assert resp.status_code == 409

    def test_overturned_dispute_sets_line_item_to_approved(self, client):
        claim = submit(client, "member-003", [li("PHYSICAL_THERAPY", 300)])
        item_id = claim["line_items"][0]["id"]
        dispute_resp = client.post(
            f"/api/claims/{claim['id']}/line-items/{item_id}/disputes",
            json={"reason": "My doctor said this is medically necessary"},
        )
        dispute_id = dispute_resp.json()["id"]
        resolve_resp = client.patch(
            f"/api/claims/{claim['id']}/line-items/{item_id}/disputes/{dispute_id}",
            json={"outcome": "OVERTURNED", "resolution_notes": "Medical necessity confirmed on review"},
        )
        assert resolve_resp.status_code == 200
        assert resolve_resp.json()["status"] == "OVERTURNED"
        # Line item should now be APPROVED, claim back to APPROVED (insurer marks paid separately)
        claim_resp = client.get(f"/api/claims/{claim['id']}")
        updated_item = next(i for i in claim_resp.json()["line_items"] if i["id"] == item_id)
        assert updated_item["status"] == "APPROVED"
        assert claim_resp.json()["status"] == "APPROVED"

    def test_upheld_dispute_leaves_line_item_denied(self, client):
        claim = submit(client, "member-003", [li("PHYSICAL_THERAPY", 300)])
        item_id = claim["line_items"][0]["id"]
        dispute_resp = client.post(
            f"/api/claims/{claim['id']}/line-items/{item_id}/disputes",
            json={"reason": "I want it covered"},
        )
        dispute_id = dispute_resp.json()["id"]
        resolve_resp = client.patch(
            f"/api/claims/{claim['id']}/line-items/{item_id}/disputes/{dispute_id}",
            json={"outcome": "UPHELD", "resolution_notes": "Physical therapy excluded on Bronze plan per policy terms"},
        )
        assert resolve_resp.status_code == 200
        claim_resp = client.get(f"/api/claims/{claim['id']}")
        updated_item = next(i for i in claim_resp.json()["line_items"] if i["id"] == item_id)
        assert updated_item["status"] == "DENIED"
