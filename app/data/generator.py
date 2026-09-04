"""Synthetic payment dataset generator.

Ground-truth labels are written for later evaluation only. A future
reconciliation engine must not read ground_truth.csv.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import List, Sequence, Tuple

import pandas as pd

from app.data.schemas import (
    GatewayRecord,
    GroundTruthRecord,
    OrderRecord,
    SettlementRecord,
)

SEED = 42
N_ORDERS = 150

# Scenario counts sum to N_ORDERS.
SCENARIO_COUNTS = {
    "success": 90,
    "amount_mismatch": 10,
    "missing_gateway": 10,
    "missing_settlement": 10,
    "duplicate_settlement": 8,
    "delayed_settlement": 8,
    "inconsistent_reference": 6,
    "ambiguous_reference": 4,
    "invalid_record": 4,
}

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

_DESCRIPTIONS = (
    "Card checkout — online store",
    "Monthly SaaS subscription",
    "Invoice payment",
    "Marketplace payout capture",
    "Mobile wallet top-up",
    "Hotel pre-authorization capture",
    "Utility bill payment",
    "Insurance premium debit",
)


def _money(rng: random.Random) -> Decimal:
    cents = rng.randint(1250, 499_999)
    return Decimal(cents) / Decimal(100)


def _currency(rng: random.Random) -> str:
    return rng.choice(("USD", "EUR", "GBP", "INR"))


def _scenario_list() -> List[str]:
    scenarios: List[str] = []
    for name, count in SCENARIO_COUNTS.items():
        scenarios.extend([name] * count)
    if len(scenarios) != N_ORDERS:
        raise ValueError("scenario counts must sum to N_ORDERS")
    return scenarios


def _order_id(index: int) -> str:
    return f"ORD-{index:04d}"


def _customer_id(rng: random.Random) -> str:
    return f"CUST-{rng.randint(1000, 8999)}"


def _gateway_ref(seq: int) -> str:
    return f"GW-{seq:07d}"


def _settlement_id(seq: int) -> str:
    return f"STL-{seq:07d}"


def _bank_reference(seq: int) -> str:
    return f"BANK-ACH-{seq:06d}"


def _captured_at(order_day: date, rng: random.Random) -> datetime:
    return datetime(
        order_day.year,
        order_day.month,
        order_day.day,
        rng.randint(8, 20),
        rng.randint(0, 59),
        rng.randint(0, 59),
    ) + timedelta(hours=rng.randint(0, 36))


def _mangle_reference(order_id: str, rng: random.Random) -> str:
    variants = (
        order_id.lower(),
        order_id.replace("-", ""),
        order_id.replace("-", "_"),
        f" {order_id} ",
        order_id.replace("ORD-", "ord:"),
    )
    return rng.choice(variants)


def generate_synthetic_dataset(
    seed: int = SEED,
    n_orders: int = N_ORDERS,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build orders, gateway, settlements, and evaluation-only ground truth."""
    if n_orders != N_ORDERS:
        raise ValueError(f"this generator produces exactly {N_ORDERS} orders")

    rng = random.Random(seed)
    scenarios = _scenario_list()
    # Keep ambiguous pairs contiguous; shuffle the rest for mix.
    ambiguous = ["ambiguous_reference"] * SCENARIO_COUNTS["ambiguous_reference"]
    head = [s for s in scenarios if s != "ambiguous_reference"]
    rng.shuffle(head)
    scenarios = head + ambiguous

    orders: List[OrderRecord] = []
    gateways: List[GatewayRecord] = []
    settlements: List[SettlementRecord] = []
    truths: List[GroundTruthRecord] = []

    gw_seq = 1
    stl_seq = 1
    start_day = date(2026, 6, 1)
    pending_ambiguous: List[int] = []

    for index, scenario in enumerate(scenarios, start=1):
        oid = _order_id(index)
        amount = _money(rng)
        currency = _currency(rng)
        order_day = start_day + timedelta(days=rng.randint(0, 75))
        description = rng.choice(_DESCRIPTIONS)
        customer_id = _customer_id(rng)

        if scenario == "invalid_record":
            invalid_kind = index % 4
            if invalid_kind == 0:
                amount = Decimal("-15.00")
            elif invalid_kind == 1:
                currency = "ZZZ"
            elif invalid_kind == 2:
                amount = Decimal("0.00")
            else:
                currency = ""

            orders.append(
                OrderRecord(
                    order_id=oid,
                    customer_id=customer_id,
                    amount=amount,
                    currency=currency or " ",
                    order_date=order_day,
                    description=description,
                )
            )
            gref = _gateway_ref(gw_seq)
            gw_seq += 1
            captured = _captured_at(order_day, rng)
            gateways.append(
                GatewayRecord(
                    gateway_ref=gref,
                    order_reference=oid,
                    amount=amount,
                    currency=currency or " ",
                    captured_at=captured,
                    status="UNKNOWN",
                    description=description,
                )
            )
            settlements.append(
                SettlementRecord(
                    settlement_id=_settlement_id(stl_seq),
                    gateway_ref=gref,
                    amount=amount,
                    settlement_date=captured.date(),
                    status="ERROR",
                    bank_reference="UNAVAILABLE",
                )
            )
            stl_seq += 1
            truths.append(
                GroundTruthRecord(
                    order_id=oid,
                    expected_gateway_relationship="invalid",
                    expected_settlement_relationship="invalid",
                    expected_outcome="exception",
                    exception_type="invalid_record",
                )
            )
            continue

        orders.append(
            OrderRecord(
                order_id=oid,
                customer_id=customer_id,
                amount=amount,
                currency=currency,
                order_date=order_day,
                description=description,
            )
        )

        if scenario == "missing_gateway":
            truths.append(
                GroundTruthRecord(
                    order_id=oid,
                    expected_gateway_relationship="missing",
                    expected_settlement_relationship="none",
                    expected_outcome="exception",
                    exception_type="missing_gateway",
                )
            )
            continue

        gref = _gateway_ref(gw_seq)
        gw_seq += 1
        captured = _captured_at(order_day, rng)
        gw_amount = amount
        order_reference = oid
        gw_status = "captured"
        gw_currency = currency

        if scenario == "amount_mismatch":
            delta = Decimal(rng.choice([50, 75, 100, 125, 250])) / Decimal(100)
            gw_amount = amount + delta
        elif scenario == "inconsistent_reference":
            order_reference = _mangle_reference(oid, rng)
        elif scenario == "ambiguous_reference":
            pending_ambiguous.append(len(gateways))

        gateways.append(
            GatewayRecord(
                gateway_ref=gref,
                order_reference=order_reference,
                amount=gw_amount,
                currency=gw_currency,
                captured_at=captured,
                status=gw_status,
                description=description,
            )
        )

        if scenario == "missing_settlement":
            truths.append(
                GroundTruthRecord(
                    order_id=oid,
                    expected_gateway_relationship="matched",
                    expected_settlement_relationship="missing",
                    expected_outcome="exception",
                    exception_type="missing_settlement",
                )
            )
            continue

        settle_amount = gw_amount if scenario != "amount_mismatch" else gw_amount
        if scenario == "amount_mismatch" and rng.random() < 0.5:
            settle_amount = amount

        if scenario == "delayed_settlement":
            settle_day = captured.date() + timedelta(days=rng.randint(10, 21))
        else:
            settle_day = captured.date() + timedelta(days=rng.randint(0, 3))

        settlements.append(
            SettlementRecord(
                settlement_id=_settlement_id(stl_seq),
                gateway_ref=gref,
                amount=settle_amount,
                settlement_date=settle_day,
                status="settled",
                bank_reference=_bank_reference(stl_seq),
            )
        )
        stl_seq += 1

        if scenario == "duplicate_settlement":
            extra_day = settle_day + timedelta(days=rng.randint(0, 2))
            settlements.append(
                SettlementRecord(
                    settlement_id=_settlement_id(stl_seq),
                    gateway_ref=gref,
                    amount=settle_amount,
                    settlement_date=extra_day,
                    status="settled",
                    bank_reference=_bank_reference(stl_seq),
                )
            )
            stl_seq += 1

        if scenario == "success":
            truths.append(
                GroundTruthRecord(
                    order_id=oid,
                    expected_gateway_relationship="matched",
                    expected_settlement_relationship="matched",
                    expected_outcome="reconciled",
                    exception_type="",
                )
            )
        elif scenario == "amount_mismatch":
            truths.append(
                GroundTruthRecord(
                    order_id=oid,
                    expected_gateway_relationship="matched",
                    expected_settlement_relationship="matched",
                    expected_outcome="exception",
                    exception_type="amount_mismatch",
                )
            )
        elif scenario == "duplicate_settlement":
            truths.append(
                GroundTruthRecord(
                    order_id=oid,
                    expected_gateway_relationship="matched",
                    expected_settlement_relationship="duplicate",
                    expected_outcome="exception",
                    exception_type="duplicate_settlement",
                )
            )
        elif scenario == "delayed_settlement":
            truths.append(
                GroundTruthRecord(
                    order_id=oid,
                    expected_gateway_relationship="matched",
                    expected_settlement_relationship="delayed",
                    expected_outcome="exception",
                    exception_type="delayed_settlement",
                )
            )
        elif scenario == "inconsistent_reference":
            truths.append(
                GroundTruthRecord(
                    order_id=oid,
                    expected_gateway_relationship="inconsistent",
                    expected_settlement_relationship="matched",
                    expected_outcome="exception",
                    exception_type="inconsistent_reference",
                )
            )
        elif scenario == "ambiguous_reference":
            truths.append(
                GroundTruthRecord(
                    order_id=oid,
                    expected_gateway_relationship="ambiguous",
                    expected_settlement_relationship="matched",
                    expected_outcome="exception",
                    exception_type="ambiguous_reference",
                )
            )

    _apply_ambiguous_references(gateways, pending_ambiguous)

    return (
        _to_frame(orders),
        _to_frame(gateways),
        _to_frame(settlements),
        _to_frame(truths),
    )


def _apply_ambiguous_references(
    gateways: List[GatewayRecord], pending_indexes: Sequence[int]
) -> None:
    """Give each consecutive pair of ambiguous orders the same gateway reference text."""
    shared_labels = ("INV-8841", "INV-2260")
    pairs = list(zip(pending_indexes[0::2], pending_indexes[1::2], shared_labels))
    for left, right, label in pairs:
        gateways[left] = gateways[left].model_copy(update={"order_reference": label})
        gateways[right] = gateways[right].model_copy(update={"order_reference": label})


def _to_frame(models: Sequence) -> pd.DataFrame:
    rows = []
    for model in models:
        payload = model.model_dump()
        for key, value in payload.items():
            if isinstance(value, Decimal):
                payload[key] = f"{value:.2f}"
            elif isinstance(value, datetime):
                payload[key] = value.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(value, date):
                payload[key] = value.isoformat()
        rows.append(payload)
    return pd.DataFrame(rows)


def write_synthetic_dataset(
    output_dir: Path | None = None,
    seed: int = SEED,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Write CSVs under data/. Ground truth is evaluation-only."""
    output_dir = output_dir or DATA_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    orders, gateway, settlements, ground_truth = generate_synthetic_dataset(seed=seed)
    orders.to_csv(output_dir / "orders.csv", index=False)
    gateway.to_csv(output_dir / "gateway.csv", index=False)
    settlements.to_csv(output_dir / "settlements.csv", index=False)
    ground_truth.to_csv(output_dir / "ground_truth.csv", index=False)
    return orders, gateway, settlements, ground_truth


if __name__ == "__main__":
    write_synthetic_dataset()
