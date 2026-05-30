import uuid
from datetime import datetime, UTC
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import Claim, LineItem, Member, Dispute
from app.models.enums import ClaimStatus, LineItemStatus, DisputeStatus
from app.schemas.schemas import (
    ClaimSubmitIn, ClaimOut, ClaimStatusUpdateIn,
    DisputeIn, DisputeResolveIn, LineItemOut, DisputeOut,
    ReviewDecisionIn,
)
from app.services.adjudication import adjudicate_line_item, compute_claim_status

router = APIRouter(prefix="/claims", tags=["claims"])


def _claim_number() -> str:
    return f"CLM-{datetime.now(UTC).year}-{uuid.uuid4().hex[:8].upper()}"


@router.post("/", response_model=ClaimOut, status_code=201)
def submit_claim(payload: ClaimSubmitIn, db: Session = Depends(get_db)):
    member = db.query(Member).filter_by(id=payload.member_id).first()
    if not member:
        raise HTTPException(404, "Member not found")

    claim = Claim(
        claim_number=_claim_number(),
        member_id=member.id,
        provider_name=payload.provider_name,
        provider_npi=payload.provider_npi,
        status=ClaimStatus.SUBMITTED,
    )
    db.add(claim)
    db.flush()

    policy = member.policy
    # eager-load coverage rules
    _ = policy.coverage_rules

    for item_in in payload.line_items:
        li = LineItem(
            claim_id=claim.id,
            service_type=item_in.service_type,
            procedure_code=item_in.procedure_code,
            diagnosis_code=item_in.diagnosis_code,
            service_date=item_in.service_date,
            billed_amount=item_in.billed_amount,
            status=LineItemStatus.PENDING,
        )
        db.add(li)
        db.flush()

        result = adjudicate_line_item(db, li, member, policy, commit_accumulators=True)
        li.status = result.status
        li.approved_amount = result.approved_amount
        li.member_responsibility = result.member_responsibility
        li.denial_reason = result.denial_reason
        li.adjudication_notes = result.adjudication_notes

    db.flush()
    claim.status = compute_claim_status(claim.line_items)
    # Move immediately to UNDER_REVIEW so UI shows the review state
    if claim.status == ClaimStatus.SUBMITTED:
        claim.status = ClaimStatus.UNDER_REVIEW

    db.commit()
    db.refresh(claim)
    return claim


@router.get("/", response_model=list[ClaimOut])
def list_claims(member_id: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Claim)
    if member_id:
        q = q.filter_by(member_id=member_id)
    return q.order_by(Claim.submission_date.desc()).all()


@router.get("/{claim_id}", response_model=ClaimOut)
def get_claim(claim_id: str, db: Session = Depends(get_db)):
    claim = db.query(Claim).filter_by(id=claim_id).first()
    if not claim:
        raise HTTPException(404, "Claim not found")
    return claim


@router.patch("/{claim_id}/status", response_model=ClaimOut)
def update_claim_status(claim_id: str, payload: ClaimStatusUpdateIn, db: Session = Depends(get_db)):
    claim = db.query(Claim).filter_by(id=claim_id).first()
    if not claim:
        raise HTTPException(404, "Claim not found")

    allowed_transitions = {
        ClaimStatus.APPROVED: [ClaimStatus.PAID, ClaimStatus.DISPUTED],
        ClaimStatus.PARTIALLY_APPROVED: [ClaimStatus.PAID, ClaimStatus.DISPUTED],
        ClaimStatus.DENIED: [ClaimStatus.DISPUTED],
        ClaimStatus.PAID: [ClaimStatus.DISPUTED],
        ClaimStatus.UNDER_REVIEW: [ClaimStatus.APPROVED, ClaimStatus.PARTIALLY_APPROVED, ClaimStatus.DENIED],
    }

    valid = allowed_transitions.get(claim.status, [])
    if payload.status not in valid:
        raise HTTPException(
            400,
            f"Cannot transition claim from {claim.status} to {payload.status}. "
            f"Allowed: {[s.value for s in valid]}"
        )

    claim.status = payload.status
    if payload.notes:
        claim.notes = payload.notes
    db.commit()
    db.refresh(claim)
    return claim


# ---------- Line item review ----------

@router.patch("/{claim_id}/line-items/{line_item_id}/review", response_model=LineItemOut)
def resolve_review(
    claim_id: str,
    line_item_id: str,
    payload: ReviewDecisionIn,
    db: Session = Depends(get_db),
):
    """Manually resolve a NEEDS_REVIEW line item to APPROVED or DENIED."""
    li = db.query(LineItem).filter_by(id=line_item_id, claim_id=claim_id).first()
    if not li:
        raise HTTPException(404, "Line item not found")
    if li.status != LineItemStatus.NEEDS_REVIEW:
        raise HTTPException(400, "Line item is not in NEEDS_REVIEW state")

    outcome = payload.outcome
    notes = payload.notes or "Manual review decision"

    claim = db.query(Claim).filter_by(id=claim_id).first()
    if outcome == "APPROVED":
        member = claim.member
        policy = member.policy
        result = adjudicate_line_item(db, li, member, policy, commit_accumulators=True, skip_prior_auth=True)
        li.status = LineItemStatus.APPROVED
        li.approved_amount = result.approved_amount
        li.member_responsibility = result.member_responsibility
        li.adjudication_notes = (result.adjudication_notes or "") + f"\nManual review: {notes}"
    else:
        li.status = LineItemStatus.DENIED
        li.denial_reason = notes
        li.approved_amount = 0
        li.member_responsibility = li.billed_amount

    claim.status = compute_claim_status(claim.line_items)
    db.commit()
    db.refresh(li)
    return li


# ---------- Disputes ----------

@router.post("/{claim_id}/line-items/{line_item_id}/disputes", response_model=DisputeOut, status_code=201)
def file_dispute(
    claim_id: str,
    line_item_id: str,
    payload: DisputeIn,
    db: Session = Depends(get_db),
):
    li = db.query(LineItem).filter_by(id=line_item_id, claim_id=claim_id).first()
    if not li:
        raise HTTPException(404, "Line item not found")
    if li.status not in (LineItemStatus.DENIED, LineItemStatus.APPROVED):
        raise HTTPException(400, "Can only dispute APPROVED or DENIED line items")

    open_dispute = next((d for d in li.disputes if d.status == DisputeStatus.OPEN), None)
    if open_dispute:
        raise HTTPException(409, "An open dispute already exists for this line item")

    dispute = Dispute(line_item_id=li.id, reason=payload.reason)
    db.add(dispute)

    claim = db.query(Claim).filter_by(id=claim_id).first()
    claim.status = ClaimStatus.DISPUTED
    db.commit()
    db.refresh(dispute)
    return dispute


@router.patch("/{claim_id}/line-items/{line_item_id}/disputes/{dispute_id}", response_model=DisputeOut)
def resolve_dispute(
    claim_id: str,
    line_item_id: str,
    dispute_id: str,
    payload: DisputeResolveIn,
    db: Session = Depends(get_db),
):
    dispute = db.query(Dispute).filter_by(id=dispute_id, line_item_id=line_item_id).first()
    if not dispute:
        raise HTTPException(404, "Dispute not found")
    if dispute.status != DisputeStatus.OPEN:
        raise HTTPException(400, "Dispute is already resolved")
    if payload.outcome not in (DisputeStatus.UPHELD, DisputeStatus.OVERTURNED):
        raise HTTPException(400, "Outcome must be UPHELD or OVERTURNED")

    dispute.status = payload.outcome
    dispute.resolution_notes = payload.resolution_notes
    dispute.resolved_at = datetime.now(UTC)

    if payload.outcome == DisputeStatus.OVERTURNED:
        li = db.query(LineItem).filter_by(id=line_item_id).first()
        li.status = LineItemStatus.APPROVED
        li.denial_reason = None

    claim = db.query(Claim).filter_by(id=claim_id).first()
    claim.status = compute_claim_status(claim.line_items)
    db.commit()
    db.refresh(dispute)
    return dispute
