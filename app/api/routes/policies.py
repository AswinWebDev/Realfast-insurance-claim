from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import Policy
from app.schemas.schemas import PolicyOut

router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("/", response_model=list[PolicyOut])
def list_policies(db: Session = Depends(get_db)):
    return db.query(Policy).all()


@router.get("/{policy_id}", response_model=PolicyOut)
def get_policy(policy_id: str, db: Session = Depends(get_db)):
    from fastapi import HTTPException
    p = db.query(Policy).filter_by(id=policy_id).first()
    if not p:
        raise HTTPException(404, "Policy not found")
    return p
