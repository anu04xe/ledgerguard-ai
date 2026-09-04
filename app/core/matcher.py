from datetime import date
from decimal import Decimal
from typing import List, Tuple

from rapidfuzz.fuzz import ratio

from app.core.models import MatchEvidence, ReconciliationResult
from app.core.normalizer import (
    normalize_amount,
    normalize_date,
    normalize_reference,
)


AUTO_MATCH_THRESHOLD = 0.90
REVIEW_THRESHOLD = 0.65
SETTLEMENT_WINDOW_DAYS = 7


def reference_score(a: str, b: str) -> float:
    a = normalize_reference(a)
    b = normalize_reference(b)

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    return ratio(a, b) / 100.0


def amount_score(a, b) -> float:
    a = normalize_amount(a)
    b = normalize_amount(b)

    if a is None or b is None:
        return 0.0

    if a == b:
        return 1.0

    difference = abs(a - b)

    # Financial matching is intentionally strict.
    if difference <= Decimal("0.01"):
        return 1.0

    if difference <= Decimal("1.00"):
        return 0.7

    return 0.0


def date_score(order_date, transaction_date) -> float:
    a = normalize_date(order_date)
    b = normalize_date(transaction_date)

    if a is None or b is None:
        return 0.0

    difference = abs((a - b).days)

    if difference == 0:
        return 1.0
    if difference <= 2:
        return 0.8
    if difference <= 7:
        return 0.5

    return 0.0


def candidate_score(order, gateway) -> Tuple[float, dict, list]:
    ref = reference_score(order.order_id, gateway.order_reference)
    amount = amount_score(order.amount, gateway.amount)
    currency = 1.0 if order.currency == gateway.currency else 0.0
    captured = date_score(order.order_date, gateway.captured_at)

    # Reference is the strongest signal.
    score = (
        ref * 0.50
        + amount * 0.30
        + currency * 0.10
        + captured * 0.10
    )

    factors = {
        "reference": ref,
        "amount": amount,
        "currency": currency,
        "date": captured,
    }

    evidence = [
        MatchEvidence(
            factor="reference",
            value=f"reference similarity={ref:.2f}",
            score=ref,
        ),
        MatchEvidence(
            factor="amount",
            value=f"amount compatibility={amount:.2f}",
            score=amount,
        ),
        MatchEvidence(
            factor="currency",
            value=f"currency compatibility={currency:.2f}",
            score=currency,
        ),
        MatchEvidence(
            factor="date",
            value=f"date compatibility={captured:.2f}",
            score=captured,
        ),
    ]

    return score, factors, evidence


def find_gateway_candidates(order, gateways):
    scored = []

    for gateway in gateways:
        score, factors, evidence = candidate_score(order, gateway)

        if score >= REVIEW_THRESHOLD:
            scored.append((score, gateway, factors, evidence))

    return sorted(scored, key=lambda x: x[0], reverse=True)


def settlement_score(gateway, settlement):
    ref = reference_score(
        gateway.gateway_ref,
        settlement.gateway_ref,
    )

    amount = amount_score(
        gateway.amount,
        settlement.amount,
    )

    settlement_date = normalize_date(settlement.settlement_date)
    captured_date = normalize_date(gateway.captured_at)

    if settlement_date and captured_date:
        days = (settlement_date - captured_date).days

        if days < 0:
            date_factor = 0.0
        elif days <= SETTLEMENT_WINDOW_DAYS:
            date_factor = 1.0
        else:
            date_factor = 0.3
    else:
        date_factor = 0.0

    score = (
        ref * 0.55
        + amount * 0.30
        + date_factor * 0.15
    )

    factors = {
        "reference": ref,
        "amount": amount,
        "settlement_date": date_factor,
    }

    evidence = [
        MatchEvidence(
            factor="settlement_reference",
            value=f"reference similarity={ref:.2f}",
            score=ref,
        ),
        MatchEvidence(
            factor="settlement_amount",
            value=f"amount compatibility={amount:.2f}",
            score=amount,
        ),
        MatchEvidence(
            factor="settlement_date",
            value=f"settlement timing={date_factor:.2f}",
            score=date_factor,
        ),
    ]

    return score, factors, evidence


def reconcile_order(order, gateways, settlements):
    """
    Reconcile one order against gateway and settlement records.

    IMPORTANT:
    This function intentionally has no knowledge of ground_truth.csv.
    """

    gateway_candidates = find_gateway_candidates(order, gateways)

    if not gateway_candidates:
        return ReconciliationResult(
            order_id=order.order_id,
            decision="EXCEPTION",
            score=0.0,
            exception_type="missing_gateway",
            order_amount=order.amount,
            evidence=[
                MatchEvidence(
                    factor="gateway",
                    value="No compatible gateway transaction found",
                    score=0.0,
                )
            ],
        )

    best = gateway_candidates[0]
    gateway_score, gateway, gateway_factors, gateway_evidence = best

    # If the top two candidates are too close, the case is ambiguous.
    if len(gateway_candidates) > 1:
        second_score = gateway_candidates[1][0]

        if gateway_score - second_score < 0.05:
            return ReconciliationResult(
                order_id=order.order_id,
                gateway_id=gateway.gateway_ref,
                decision="NEEDS_AI_REVIEW",
                score=gateway_score,
                matching_factors=gateway_factors,
                evidence=gateway_evidence + [
                    MatchEvidence(
                        factor="ambiguity",
                        value=(
                            f"top candidates are too close: "
                            f"{gateway_score:.2f} vs {second_score:.2f}"
                        ),
                        score=0.0,
                    )
                ],
                order_amount=order.amount,
                gateway_amount=gateway.amount,
            )

    if gateway.currency != order.currency:
        return ReconciliationResult(
            order_id=order.order_id,
            gateway_id=gateway.gateway_ref,
            decision="EXCEPTION",
            score=gateway_score,
            matching_factors=gateway_factors,
            exception_type="currency_mismatch",
            evidence=gateway_evidence,
            order_amount=order.amount,
            gateway_amount=gateway.amount,
        )

    if normalize_amount(gateway.amount) != normalize_amount(order.amount):
        return ReconciliationResult(
            order_id=order.order_id,
            gateway_id=gateway.gateway_ref,
            decision="EXCEPTION",
            score=gateway_score,
            matching_factors=gateway_factors,
            exception_type="amount_mismatch",
            evidence=gateway_evidence + [
                MatchEvidence(
                    factor="amount_mismatch",
                    value=(
                        f"order={order.amount}, "
                        f"gateway={gateway.amount}"
                    ),
                    score=0.0,
                )
            ],
            order_amount=order.amount,
            gateway_amount=gateway.amount,
        )

    # Find settlements belonging to this gateway.
    settlement_candidates = []

    for settlement in settlements:
        score, factors, evidence = settlement_score(
            gateway,
            settlement,
        )

        if score >= REVIEW_THRESHOLD:
            settlement_candidates.append(
                (score, settlement, factors, evidence)
            )

    settlement_candidates.sort(
        key=lambda x: x[0],
        reverse=True,
    )

    if not settlement_candidates:
        return ReconciliationResult(
            order_id=order.order_id,
            gateway_id=gateway.gateway_ref,
            decision="EXCEPTION",
            score=gateway_score,
            matching_factors=gateway_factors,
            exception_type="missing_settlement",
            evidence=gateway_evidence + [
                MatchEvidence(
                    factor="settlement",
                    value="No compatible settlement found",
                    score=0.0,
                )
            ],
            order_amount=order.amount,
            gateway_amount=gateway.amount,
        )

    best_settlement = settlement_candidates[0]
    settlement_score_value, settlement, settlement_factors, settlement_evidence = (
        best_settlement
    )

    # Duplicate settlement detection.
    if len(settlement_candidates) > 1:
        return ReconciliationResult(
            order_id=order.order_id,
            gateway_id=gateway.gateway_ref,
            settlement_id=settlement.settlement_id,
            decision="EXCEPTION",
            score=min(gateway_score, settlement_score_value),
            matching_factors={
                **gateway_factors,
                **{
                    f"settlement_{k}": v
                    for k, v in settlement_factors.items()
                },
            },
            exception_type="duplicate_settlement",
            evidence=gateway_evidence + settlement_evidence + [
                MatchEvidence(
                    factor="duplicate",
                    value=(
                        f"{len(settlement_candidates)} settlement "
                        "candidates found"
                    ),
                    score=0.0,
                )
            ],
            order_amount=order.amount,
            gateway_amount=gateway.amount,
            settlement_amount=settlement.amount,
        )

    if normalize_amount(settlement.amount) != normalize_amount(gateway.amount):
        return ReconciliationResult(
            order_id=order.order_id,
            gateway_id=gateway.gateway_ref,
            settlement_id=settlement.settlement_id,
            decision="EXCEPTION",
            score=min(gateway_score, settlement_score_value),
            matching_factors=gateway_factors,
            exception_type="settlement_amount_mismatch",
            evidence=gateway_evidence + settlement_evidence,
            order_amount=order.amount,
            gateway_amount=gateway.amount,
            settlement_amount=settlement.amount,
        )

    settlement_date = normalize_date(settlement.settlement_date)
    captured_date = normalize_date(gateway.captured_at)

    if settlement_date and captured_date:
        delay = (settlement_date - captured_date).days

        if delay > SETTLEMENT_WINDOW_DAYS:
            return ReconciliationResult(
                order_id=order.order_id,
                gateway_id=gateway.gateway_ref,
                settlement_id=settlement.settlement_id,
                decision="EXCEPTION",
                score=min(gateway_score, settlement_score_value),
                matching_factors=gateway_factors,
                exception_type="delayed_settlement",
                evidence=gateway_evidence + settlement_evidence + [
                    MatchEvidence(
                        factor="delay",
                        value=f"settlement delayed by {delay} days",
                        score=0.0,
                    )
                ],
                order_amount=order.amount,
                gateway_amount=gateway.amount,
                settlement_amount=settlement.amount,
            )

    final_score = min(gateway_score, settlement_score_value)

    if final_score >= AUTO_MATCH_THRESHOLD:
        decision = "MATCH"
    else:
        decision = "NEEDS_AI_REVIEW"

    return ReconciliationResult(
        order_id=order.order_id,
        gateway_id=gateway.gateway_ref,
        settlement_id=settlement.settlement_id,
        decision=decision,
        score=final_score,
        matching_factors={
            **gateway_factors,
            **{
                f"settlement_{k}": v
                for k, v in settlement_factors.items()
            },
        },
        evidence=gateway_evidence + settlement_evidence,
        order_amount=order.amount,
        gateway_amount=gateway.amount,
        settlement_amount=settlement.amount,
    )
def reconcile_all(orders, gateways, settlements):
        return [
            reconcile_order(order, gateways, settlements)
            for order in orders
        ]