from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import Member
from app.schemas.schemas import MemberOut, MemberDetailOut, AccumulatorOut

router = APIRouter(prefix="/members", tags=["members"])


@router.get("/", response_model=list[MemberOut])
def list_members(db: Session = Depends(get_db)):
    members = db.query(Member).all()
    result = []
    for m in members:
        out = MemberOut.model_validate(m)
        out.policy_name = m.policy.name
        out.policy_tier = m.policy.tier
        result.append(out)
    return result


@router.get("/{member_id}", response_model=MemberDetailOut)
def get_member(member_id: str, db: Session = Depends(get_db)):
    m = db.query(Member).filter_by(id=member_id).first()
    if not m:
        raise HTTPException(404, "Member not found")
    out = MemberDetailOut.model_validate(m)
    out.policy_name = m.policy.name
    out.policy_tier = m.policy.tier
    out.accumulators = [AccumulatorOut.model_validate(a) for a in m.accumulators]
    return out
