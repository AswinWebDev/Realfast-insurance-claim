from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from app.models.enums import (
    PolicyTier, ServiceType, ClaimStatus,
    LineItemStatus, DisputeStatus, AccumulatorType
)


# ---------- Policy ----------

class CoverageRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: str
    service_type: ServiceType
    annual_limit: Optional[Decimal]
    covered_pct: Optional[Decimal]
    copay_amount: Decimal
    deductible_applies: bool
    requires_prior_auth: bool
    is_excluded: bool


class PolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: str
    name: str
    tier: PolicyTier
    annual_deductible: Decimal
    out_of_pocket_max: Decimal
    coverage_rules: list[CoverageRuleOut]


# ---------- Member ----------

class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: str
    name: str
    date_of_birth: date
    member_number: str
    enrollment_date: date
    policy_id: str
    policy_name: Optional[str] = None
    policy_tier: Optional[str] = None


class AccumulatorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    accumulator_type: AccumulatorType
    service_type: Optional[str]
    benefit_year: int
    amount_used: Decimal


class MemberDetailOut(MemberOut):
    accumulators: list[AccumulatorOut] = []


# ---------- Claim submission ----------

class LineItemIn(BaseModel):
    service_type: ServiceType
    procedure_code: Optional[str] = None
    diagnosis_code: Optional[str] = None
    service_date: date
    billed_amount: Decimal = Field(gt=0)


class ClaimSubmitIn(BaseModel):
    member_id: str
    provider_name: str
    provider_npi: Optional[str] = None
    line_items: list[LineItemIn] = Field(min_length=1)


# ---------- Claim output ----------

class DisputeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: str
    submitted_at: datetime
    reason: str
    status: DisputeStatus
    resolution_notes: Optional[str]
    resolved_at: Optional[datetime]


class LineItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: str
    service_type: ServiceType
    procedure_code: Optional[str]
    diagnosis_code: Optional[str]
    service_date: date
    billed_amount: Decimal
    approved_amount: Optional[Decimal]
    member_responsibility: Optional[Decimal]
    status: LineItemStatus
    denial_reason: Optional[str]
    adjudication_notes: Optional[str]
    disputes: list[DisputeOut] = []


class ClaimOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: str
    claim_number: str
    member_id: str
    provider_name: str
    provider_npi: Optional[str]
    submission_date: datetime
    status: ClaimStatus
    notes: Optional[str]
    line_items: list[LineItemOut] = []


# ---------- Dispute ----------

class DisputeIn(BaseModel):
    reason: str = Field(min_length=10)


class DisputeResolveIn(BaseModel):
    outcome: DisputeStatus  # UPHELD or OVERTURNED
    resolution_notes: str = Field(min_length=5)


# ---------- Claim actions ----------

class ClaimStatusUpdateIn(BaseModel):
    status: ClaimStatus
    notes: Optional[str] = None


class ReviewDecisionIn(BaseModel):
    outcome: str = Field(pattern="^(APPROVED|DENIED)$")
    notes: Optional[str] = None
