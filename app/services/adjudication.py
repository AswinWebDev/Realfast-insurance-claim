from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session
from app.models.models import LineItem, MemberAccumulator, Policy, CoverageRule, Member
from app.models.enums import AccumulatorType, LineItemStatus


@dataclass
class AdjudicationResult:
    status: LineItemStatus
    approved_amount: Decimal
    member_responsibility: Decimal
    denial_reason: str | None
    adjudication_notes: str


def _cents(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _get_or_create_accumulator(
    db: Session,
    member_id: str,
    benefit_year: int,
    acc_type: AccumulatorType,
    service_type: str | None = None,
) -> MemberAccumulator:
    acc = db.query(MemberAccumulator).filter_by(
        member_id=member_id,
        benefit_year=benefit_year,
        accumulator_type=acc_type,
        service_type=service_type,
    ).first()
    if not acc:
        acc = MemberAccumulator(
            member_id=member_id,
            benefit_year=benefit_year,
            accumulator_type=acc_type,
            service_type=service_type,
            amount_used=Decimal("0.00"),
        )
        db.add(acc)
        db.flush()
    return acc


def adjudicate_line_item(
    db: Session,
    line_item: LineItem,
    member: Member,
    policy: Policy,
    commit_accumulators: bool = True,
    skip_prior_auth: bool = False,
) -> AdjudicationResult:
    """
    Runs the 9-step adjudication process for a single line item.
    If commit_accumulators=True, increments MemberAccumulators on approval.
    Wrapping callers should manage the transaction.
    """
    notes: list[str] = []
    benefit_year = line_item.service_date.year

    # Step 1 — coverage check
    rule: CoverageRule | None = next(
        (r for r in policy.coverage_rules if r.service_type == line_item.service_type),
        None,
    )
    if rule is None:
        reason = f"Service type '{line_item.service_type}' is not recognized or covered under your {policy.name}"
        notes.append(f"Step 1 FAIL: {reason}")
        return AdjudicationResult(LineItemStatus.DENIED, Decimal("0"), line_item.billed_amount, reason, "\n".join(notes))

    if rule.is_excluded:
        reason = f"{line_item.service_type.replace('_', ' ').title()} is not a covered benefit under the {policy.name}"
        notes.append(f"Step 1 FAIL: {reason}")
        return AdjudicationResult(LineItemStatus.DENIED, Decimal("0"), line_item.billed_amount, reason, "\n".join(notes))

    notes.append(f"Step 1 PASS: {line_item.service_type} is covered under {policy.name}")

    # Step 2 — prior auth check
    if rule.requires_prior_auth and not skip_prior_auth:
        notes.append("Step 2: Prior authorization required — escalating to manual review")
        return AdjudicationResult(
            LineItemStatus.NEEDS_REVIEW,
            Decimal("0"),
            Decimal("0"),
            None,
            "\n".join(notes),
        )
    if skip_prior_auth:
        notes.append("Step 2 PASS: Prior authorization confirmed via manual review")
    else:
        notes.append("Step 2 PASS: No prior authorization required")

    # Step 3 — annual benefit limit check
    svc_acc = _get_or_create_accumulator(
        db, member.id, benefit_year, AccumulatorType.SERVICE_BENEFIT, line_item.service_type
    )
    remaining_benefit = _cents(rule.annual_limit - svc_acc.amount_used)
    notes.append(
        f"Step 3: Annual limit ${rule.annual_limit}, used ${svc_acc.amount_used}, remaining ${remaining_benefit}"
    )
    if remaining_benefit <= Decimal("0"):
        reason = (
            f"Annual benefit limit of ${rule.annual_limit} for "
            f"{line_item.service_type.replace('_', ' ').title()} has been fully exhausted "
            f"for benefit year {benefit_year}"
        )
        notes.append(f"Step 3 FAIL: {reason}")
        return AdjudicationResult(LineItemStatus.DENIED, Decimal("0"), line_item.billed_amount, reason, "\n".join(notes))

    # Step 4 — copay deduction
    copay = _cents(rule.copay_amount or Decimal("0"))
    member_owes = copay
    adjudicable = _cents(line_item.billed_amount - copay)
    notes.append(f"Step 4: Copay ${copay} deducted, adjudicable amount ${adjudicable}")

    if adjudicable <= Decimal("0"):
        reason = (
            f"Billed amount of ${line_item.billed_amount} does not exceed "
            f"the applicable copay of ${copay}; member responsible for full amount"
        )
        notes.append(f"Step 4 RESULT: {reason}")
        return AdjudicationResult(LineItemStatus.APPROVED, Decimal("0"), _cents(line_item.billed_amount), reason, "\n".join(notes))

    # Step 5 — deductible application
    ded_applied = Decimal("0")
    if rule.deductible_applies:
        ded_acc = _get_or_create_accumulator(
            db, member.id, benefit_year, AccumulatorType.DEDUCTIBLE
        )
        ded_remaining = _cents(policy.annual_deductible - ded_acc.amount_used)
        ded_applied = _cents(min(adjudicable, ded_remaining))
        member_owes += ded_applied
        adjudicable = _cents(adjudicable - ded_applied)
        notes.append(
            f"Step 5: Deductible remaining ${ded_remaining}, applied ${ded_applied} to deductible, "
            f"adjudicable after deductible ${adjudicable}"
        )
    else:
        notes.append("Step 5: Deductible does not apply to this service")

    if adjudicable <= Decimal("0"):
        reason = (
            f"Full billed amount applied to outstanding deductible of "
            f"${policy.annual_deductible}; $0 payable by insurance at this time"
        )
        notes.append(f"Step 5 RESULT: {reason}")
        if commit_accumulators:
            ded_acc.amount_used = _cents(ded_acc.amount_used + ded_applied)
            oop_acc = _get_or_create_accumulator(
                db, member.id, benefit_year, AccumulatorType.OOP_MAX
            )
            oop_acc.amount_used = _cents(oop_acc.amount_used + member_owes)
        return AdjudicationResult(LineItemStatus.APPROVED, Decimal("0"), _cents(member_owes), reason, "\n".join(notes))

    # Step 6 — co-insurance
    covered_pct = rule.covered_pct or Decimal("0")
    insurance_share = _cents(adjudicable * covered_pct)
    member_coinsurance = _cents(adjudicable - insurance_share)
    member_owes += member_coinsurance
    notes.append(
        f"Step 6: Insurance covers {int(covered_pct * 100)}% = ${insurance_share}, "
        f"member co-insurance = ${member_coinsurance}"
    )

    # Step 7 — cap at remaining annual benefit limit
    approved_amount = _cents(min(insurance_share, remaining_benefit))
    # svc_benefit_charge is what counts against the service limit — always capped at remaining_benefit
    svc_benefit_charge = approved_amount
    if approved_amount < insurance_share:
        # The insurer simply won't pay above the limit — this is NOT added to member_owes.
        # Amounts above the annual benefit limit do not count toward OOP max. The provider
        # writes off the excess (in-network) or bills the member outside the insurance system.
        partial_msg = (
            f"Annual benefit limit has ${remaining_benefit} remaining; "
            f"insurance pays ${approved_amount}, remaining ${_cents(insurance_share - approved_amount)} "
            f"is above the annual limit and not covered"
        )
        notes.append(f"Step 7: PARTIAL — {partial_msg}")
    else:
        notes.append(f"Step 7: Full insurance share ${approved_amount} within annual limit")

    # Step 8 — OOP max check
    oop_acc = _get_or_create_accumulator(
        db, member.id, benefit_year, AccumulatorType.OOP_MAX
    )
    oop_remaining = _cents(policy.out_of_pocket_max - oop_acc.amount_used)
    notes.append(
        f"Step 8: OOP max ${policy.out_of_pocket_max}, used ${oop_acc.amount_used}, remaining ${oop_remaining}"
    )
    if member_owes > oop_remaining:
        excess = _cents(member_owes - oop_remaining)
        approved_amount = _cents(approved_amount + excess)
        member_owes = oop_remaining
        notes.append(
            f"Step 8: OOP max reached — insurance absorbs extra ${excess}, "
            f"member capped at ${member_owes}"
        )
    # svc_benefit_charge is not adjusted by OOP — the service limit cap from Step 7 is final

    # Step 9 — commit accumulators and approve
    notes.append(
        f"Step 9 APPROVE: insurance pays ${approved_amount}, member owes ${member_owes}"
    )

    if commit_accumulators:
        svc_acc.amount_used = _cents(svc_acc.amount_used + svc_benefit_charge)

        if rule.deductible_applies and ded_applied > Decimal("0"):
            ded_acc = _get_or_create_accumulator(
                db, member.id, benefit_year, AccumulatorType.DEDUCTIBLE
            )
            ded_acc.amount_used = _cents(ded_acc.amount_used + ded_applied)

        oop_acc.amount_used = _cents(oop_acc.amount_used + member_owes)

    return AdjudicationResult(
        status=LineItemStatus.APPROVED,
        approved_amount=approved_amount,
        member_responsibility=_cents(member_owes),
        denial_reason=None,
        adjudication_notes="\n".join(notes),
    )


def compute_claim_status(line_items: list[LineItem]):
    from app.models.enums import ClaimStatus
    statuses = {li.status for li in line_items}
    if LineItemStatus.NEEDS_REVIEW in statuses:
        return ClaimStatus.UNDER_REVIEW
    if statuses == {LineItemStatus.APPROVED}:
        return ClaimStatus.APPROVED
    if statuses == {LineItemStatus.DENIED}:
        return ClaimStatus.DENIED
    return ClaimStatus.PARTIALLY_APPROVED
