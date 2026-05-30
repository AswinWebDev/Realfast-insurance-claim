import uuid
from datetime import datetime, date, UTC
from decimal import Decimal
from sqlalchemy import (
    String, Boolean, Numeric, Date, DateTime,
    ForeignKey, Integer, UniqueConstraint, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.enums import (
    PolicyTier, ServiceType, ClaimStatus,
    LineItemStatus, AccumulatorType, DisputeStatus
)


def _uuid() -> str:
    return str(uuid.uuid4())


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[PolicyTier] = mapped_column(String, nullable=False)
    annual_deductible: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    out_of_pocket_max: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)

    coverage_rules: Mapped[list["CoverageRule"]] = relationship(back_populates="policy")
    members: Mapped[list["Member"]] = relationship(back_populates="policy")


class CoverageRule(Base):
    __tablename__ = "coverage_rules"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies.id"), nullable=False)
    service_type: Mapped[ServiceType] = mapped_column(String, nullable=False)
    annual_limit: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    covered_pct: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=True)
    copay_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    deductible_applies: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_prior_auth: Mapped[bool] = mapped_column(Boolean, default=False)
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False)

    policy: Mapped["Policy"] = relationship(back_populates="coverage_rules")

    __table_args__ = (
        UniqueConstraint("policy_id", "service_type", name="uq_policy_service"),
    )


class Member(Base):
    __tablename__ = "members"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies.id"), nullable=False)
    enrollment_date: Mapped[date] = mapped_column(Date, nullable=False)
    member_number: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    policy: Mapped["Policy"] = relationship(back_populates="members")
    claims: Mapped[list["Claim"]] = relationship(back_populates="member")
    accumulators: Mapped[list["MemberAccumulator"]] = relationship(back_populates="member")


class MemberAccumulator(Base):
    __tablename__ = "member_accumulators"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    member_id: Mapped[str] = mapped_column(ForeignKey("members.id"), nullable=False)
    benefit_year: Mapped[int] = mapped_column(Integer, nullable=False)
    accumulator_type: Mapped[AccumulatorType] = mapped_column(String, nullable=False)
    service_type: Mapped[str] = mapped_column(String, nullable=True)
    amount_used: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)

    member: Mapped["Member"] = relationship(back_populates="accumulators")

    __table_args__ = (
        UniqueConstraint(
            "member_id", "benefit_year", "accumulator_type", "service_type",
            name="uq_member_accumulator"
        ),
    )


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    claim_number: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    member_id: Mapped[str] = mapped_column(ForeignKey("members.id"), nullable=False)
    provider_name: Mapped[str] = mapped_column(String, nullable=False)
    provider_npi: Mapped[str] = mapped_column(String, nullable=True)
    submission_date: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    status: Mapped[ClaimStatus] = mapped_column(String, default=ClaimStatus.SUBMITTED)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    member: Mapped["Member"] = relationship(back_populates="claims")
    line_items: Mapped[list["LineItem"]] = relationship(back_populates="claim", cascade="all, delete-orphan")


class LineItem(Base):
    __tablename__ = "line_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), nullable=False)
    service_type: Mapped[ServiceType] = mapped_column(String, nullable=False)
    procedure_code: Mapped[str] = mapped_column(String, nullable=True)
    diagnosis_code: Mapped[str] = mapped_column(String, nullable=True)
    service_date: Mapped[date] = mapped_column(Date, nullable=False)
    billed_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    approved_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    member_responsibility: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[LineItemStatus] = mapped_column(String, default=LineItemStatus.PENDING)
    denial_reason: Mapped[str] = mapped_column(Text, nullable=True)
    adjudication_notes: Mapped[str] = mapped_column(Text, nullable=True)

    claim: Mapped["Claim"] = relationship(back_populates="line_items")
    disputes: Mapped[list["Dispute"]] = relationship(back_populates="line_item", cascade="all, delete-orphan")


class Dispute(Base):
    __tablename__ = "disputes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    line_item_id: Mapped[str] = mapped_column(ForeignKey("line_items.id"), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DisputeStatus] = mapped_column(String, default=DisputeStatus.OPEN)
    resolution_notes: Mapped[str] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    line_item: Mapped["LineItem"] = relationship(back_populates="disputes")
