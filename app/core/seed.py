from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.models import Policy, CoverageRule, Member
from app.models.enums import PolicyTier, ServiceType


def seed(db: Session) -> None:
    if db.query(Policy).count() > 0:
        return

    diamond = Policy(
        id="policy-diamond",
        name="Diamond Plan",
        tier=PolicyTier.DIAMOND,
        annual_deductible=Decimal("500.00"),
        out_of_pocket_max=Decimal("3000.00"),
        effective_date=date(2026, 1, 1),
    )
    gold = Policy(
        id="policy-gold",
        name="Gold Plan",
        tier=PolicyTier.GOLD,
        annual_deductible=Decimal("1000.00"),
        out_of_pocket_max=Decimal("5000.00"),
        effective_date=date(2026, 1, 1),
    )
    bronze = Policy(
        id="policy-bronze",
        name="Bronze Plan",
        tier=PolicyTier.BRONZE,
        annual_deductible=Decimal("2500.00"),
        out_of_pocket_max=Decimal("8000.00"),
        effective_date=date(2026, 1, 1),
    )
    db.add_all([diamond, gold, bronze])

    # ------------------------------------------------------------------
    # Coverage rules — (policy, service_type, limit, pct, copay, deductible_applies, prior_auth, excluded)
    # ------------------------------------------------------------------
    rules = [
        # Diamond
        (diamond, ServiceType.PRIMARY_CARE,      5000,  0.90, 10,  False, False, False),
        (diamond, ServiceType.SPECIALIST,         8000,  0.85, 30,  True,  False, False),
        (diamond, ServiceType.EMERGENCY_ROOM,    20000,  0.90, 100, True,  False, False),
        (diamond, ServiceType.URGENT_CARE,        5000,  0.90, 25,  False, False, False),
        (diamond, ServiceType.INPATIENT,         50000,  0.85, 250, True,  True,  False),
        (diamond, ServiceType.OUTPATIENT_SURGERY,30000,  0.85, 150, True,  True,  False),
        (diamond, ServiceType.LAB,                3000,  1.00, 0,   False, False, False),
        (diamond, ServiceType.IMAGING,            5000,  0.90, 50,  True,  False, False),
        (diamond, ServiceType.PRESCRIPTION,       4000,  0.80, 15,  False, False, False),
        (diamond, ServiceType.PHYSICAL_THERAPY,   5000,  0.85, 30,  True,  False, False),
        (diamond, ServiceType.MENTAL_HEALTH,      6000,  0.90, 20,  True,  False, False),
        # Gold
        (gold, ServiceType.PRIMARY_CARE,          3000,  0.80, 20,  True,  False, False),
        (gold, ServiceType.SPECIALIST,             5000,  0.75, 50,  True,  False, False),
        (gold, ServiceType.EMERGENCY_ROOM,        15000,  0.80, 150, True,  False, False),
        (gold, ServiceType.URGENT_CARE,            3000,  0.80, 40,  True,  False, False),
        (gold, ServiceType.INPATIENT,             35000,  0.75, 400, True,  True,  False),
        (gold, ServiceType.OUTPATIENT_SURGERY,    20000,  0.75, 200, True,  True,  False),
        (gold, ServiceType.LAB,                    2000,  0.90, 10,  True,  False, False),
        (gold, ServiceType.IMAGING,                3000,  0.80, 75,  True,  False, False),
        (gold, ServiceType.PRESCRIPTION,           2500,  0.70, 25,  True,  False, False),
        (gold, ServiceType.PHYSICAL_THERAPY,       3000,  0.75, 45,  True,  False, False),
        (gold, ServiceType.MENTAL_HEALTH,          4000,  0.80, 35,  True,  False, False),
        # Bronze
        (bronze, ServiceType.PRIMARY_CARE,         1500,  0.60, 40,  True,  False, False),
        (bronze, ServiceType.SPECIALIST,            2500,  0.55, 75,  True,  False, False),
        (bronze, ServiceType.EMERGENCY_ROOM,       10000,  0.65, 250, True,  False, False),
        (bronze, ServiceType.URGENT_CARE,           1500,  0.60, 60,  True,  False, False),
        (bronze, ServiceType.INPATIENT,            20000,  0.60, 600, True,  True,  False),
        (bronze, ServiceType.OUTPATIENT_SURGERY,   10000,  0.60, 300, True,  True,  False),
        (bronze, ServiceType.LAB,                   1000,  0.70, 20,  True,  False, False),
        (bronze, ServiceType.IMAGING,               1500,  0.65, 100, True,  False, False),
        (bronze, ServiceType.PRESCRIPTION,          1200,  0.55, 40,  True,  False, False),
        (bronze, ServiceType.PHYSICAL_THERAPY,      None,  None, 0,   False, False, True),  # excluded
        (bronze, ServiceType.MENTAL_HEALTH,         2000,  0.60, 50,  True,  False, False),
    ]

    for policy, svc, limit, pct, copay, ded, auth, excl in rules:
        db.add(CoverageRule(
            policy_id=policy.id,
            service_type=svc,
            annual_limit=Decimal(str(limit)) if limit is not None else None,
            covered_pct=Decimal(str(pct)) if pct is not None else None,
            copay_amount=Decimal(str(copay)),
            deductible_applies=ded,
            requires_prior_auth=auth,
            is_excluded=excl,
        ))

    members = [
        Member(
            id="member-001",
            name="Alice Johnson",
            date_of_birth=date(1985, 3, 14),
            policy_id=diamond.id,
            enrollment_date=date(2026, 1, 1),
            member_number="MBR-00001",
        ),
        Member(
            id="member-002",
            name="Bob Martinez",
            date_of_birth=date(1979, 7, 22),
            policy_id=gold.id,
            enrollment_date=date(2026, 1, 1),
            member_number="MBR-00002",
        ),
        Member(
            id="member-003",
            name="Carol Chen",
            date_of_birth=date(1992, 11, 5),
            policy_id=bronze.id,
            enrollment_date=date(2026, 1, 1),
            member_number="MBR-00003",
        ),
        Member(
            id="member-004",
            name="David Park",
            date_of_birth=date(1968, 1, 30),
            policy_id=diamond.id,
            enrollment_date=date(2026, 1, 1),
            member_number="MBR-00004",
        ),
        Member(
            id="member-005",
            name="Emma Wilson",
            date_of_birth=date(2001, 6, 18),
            policy_id=gold.id,
            enrollment_date=date(2026, 1, 1),
            member_number="MBR-00005",
        ),
    ]
    db.add_all(members)
    db.commit()
