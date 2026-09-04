from pathlib import Path

import pandas as pd

from app.data.generator import (
    DATA_DIR,
    N_ORDERS,
    SEED,
    generate_synthetic_dataset,
    write_synthetic_dataset,
)
from app.data.schemas import ALLOWED_CURRENCIES, EXCEPTION_TYPES

ORDER_COLUMNS = [
    "order_id",
    "customer_id",
    "amount",
    "currency",
    "order_date",
    "description",
]
GATEWAY_COLUMNS = [
    "gateway_ref",
    "order_reference",
    "amount",
    "currency",
    "captured_at",
    "status",
    "description",
]
SETTLEMENT_COLUMNS = [
    "settlement_id",
    "gateway_ref",
    "amount",
    "settlement_date",
    "status",
    "bank_reference",
]
GROUND_TRUTH_COLUMNS = [
    "order_id",
    "expected_gateway_relationship",
    "expected_settlement_relationship",
    "expected_outcome",
    "exception_type",
]


def test_exactly_150_orders():
    orders, _, _, _ = generate_synthetic_dataset(seed=SEED)
    assert len(orders) == N_ORDERS == 150
    assert orders["order_id"].nunique() == 150


def test_required_columns():
    orders, gateway, settlements, ground_truth = generate_synthetic_dataset(seed=SEED)
    assert list(orders.columns) == ORDER_COLUMNS
    assert list(gateway.columns) == GATEWAY_COLUMNS
    assert list(settlements.columns) == SETTLEMENT_COLUMNS
    assert list(ground_truth.columns) == GROUND_TRUTH_COLUMNS


def test_generation_is_reproducible():
    first = generate_synthetic_dataset(seed=SEED)
    second = generate_synthetic_dataset(seed=SEED)
    for left, right in zip(first, second):
        pd.testing.assert_frame_equal(left, right)


def test_intended_anomaly_types_are_present():
    _, _, _, ground_truth = generate_synthetic_dataset(seed=SEED)
    present = set(ground_truth["exception_type"].fillna("").tolist())
    present.discard("")
    assert EXCEPTION_TYPES.issubset(present)
    assert (ground_truth["expected_outcome"] == "reconciled").any()
    assert (ground_truth["exception_type"] == "").sum() == 90


def test_ground_truth_has_expected_records():
    orders, _, _, ground_truth = generate_synthetic_dataset(seed=SEED)
    assert len(ground_truth) == 150
    assert set(ground_truth["order_id"]) == set(orders["order_id"])
    assert set(ground_truth["expected_outcome"]) == {"reconciled", "exception"}
    counts = ground_truth["exception_type"].value_counts(dropna=False).to_dict()
    assert counts.get("", 0) == 90
    assert counts["amount_mismatch"] == 10
    assert counts["missing_gateway"] == 10
    assert counts["missing_settlement"] == 10
    assert counts["duplicate_settlement"] == 8
    assert counts["delayed_settlement"] == 8
    assert counts["inconsistent_reference"] == 6
    assert counts["ambiguous_reference"] == 4
    assert counts["invalid_record"] == 4


def test_anomaly_patterns_exist_in_source_tables():
    orders, gateway, settlements, ground_truth = generate_synthetic_dataset(seed=SEED)
    order_ids = set(orders["order_id"])

    missing_gw_ids = set(
        ground_truth.loc[
            ground_truth["exception_type"] == "missing_gateway", "order_id"
        ]
    )
    assert len(missing_gw_ids) == 10
    assert gateway["order_reference"].isin(missing_gw_ids).sum() == 0

    missing_stl_ids = set(
        ground_truth.loc[
            ground_truth["exception_type"] == "missing_settlement", "order_id"
        ]
    )
    missing_stl_refs = set(
        gateway.loc[gateway["order_reference"].isin(missing_stl_ids), "gateway_ref"]
    )
    assert len(missing_stl_refs) == 10
    assert settlements["gateway_ref"].isin(missing_stl_refs).sum() == 0

    dup_ids = set(
        ground_truth.loc[
            ground_truth["exception_type"] == "duplicate_settlement", "order_id"
        ]
    )
    dup_refs = set(gateway.loc[gateway["order_reference"].isin(dup_ids), "gateway_ref"])
    dup_counts = settlements.loc[
        settlements["gateway_ref"].isin(dup_refs), "gateway_ref"
    ].value_counts()
    assert (dup_counts == 2).all()
    assert len(dup_counts) == 8

    delayed_ids = set(
        ground_truth.loc[
            ground_truth["exception_type"] == "delayed_settlement", "order_id"
        ]
    )
    delayed_gateways = gateway.loc[gateway["order_reference"].isin(delayed_ids)]
    merged = delayed_gateways.merge(settlements, on="gateway_ref", suffixes=("_g", "_s"))
    captured = pd.to_datetime(merged["captured_at"])
    settled = pd.to_datetime(merged["settlement_date"])
    assert ((settled - captured).dt.days >= 10).all()

    inconsistent_ids = set(
        ground_truth.loc[
            ground_truth["exception_type"] == "inconsistent_reference", "order_id"
        ]
    )
    inconsistent_refs = gateway["order_reference"]
    assert not set(inconsistent_refs).issuperset(inconsistent_ids)
    assert inconsistent_ids.isdisjoint(set(gateway["order_reference"]))

    ambiguous_refs = gateway.loc[
        gateway["order_reference"].isin(
            gateway.groupby("order_reference").filter(lambda g: len(g) > 1)[
                "order_reference"
            ]
        ),
        "order_reference",
    ]
    assert ambiguous_refs.nunique() == 2
    assert (ambiguous_refs.value_counts() == 2).all()

    mismatch_ids = set(
        ground_truth.loc[ground_truth["exception_type"] == "amount_mismatch", "order_id"]
    )
    mismatch_rows = orders.loc[orders["order_id"].isin(mismatch_ids), ["order_id", "amount"]]
    gw_join = mismatch_rows.merge(
        gateway, left_on="order_id", right_on="order_reference", suffixes=("_o", "_g")
    )
    assert (gw_join["amount_o"].astype(float) != gw_join["amount_g"].astype(float)).all()

    invalid_ids = set(
        ground_truth.loc[ground_truth["exception_type"] == "invalid_record", "order_id"]
    )
    invalid_orders = orders.loc[orders["order_id"].isin(invalid_ids)]
    amounts = invalid_orders["amount"].astype(float)
    currencies = invalid_orders["currency"].str.strip()
    assert (
        (amounts <= 0)
        | (~currencies.isin(ALLOWED_CURRENCIES))
    ).all()
    assert order_ids == set(ground_truth["order_id"])


def test_amounts_and_currencies_valid_for_non_invalid_records():
    orders, gateway, settlements, ground_truth = generate_synthetic_dataset(seed=SEED)
    invalid_ids = set(
        ground_truth.loc[ground_truth["exception_type"] == "invalid_record", "order_id"]
    )
    valid_orders = orders.loc[~orders["order_id"].isin(invalid_ids)]
    _assert_valid_money(valid_orders["amount"], valid_orders["currency"])

    invalid_gw_mask = gateway["status"].eq("UNKNOWN")
    _assert_valid_money(
        gateway.loc[~invalid_gw_mask, "amount"],
        gateway.loc[~invalid_gw_mask, "currency"],
    )

    invalid_gw_refs = set(gateway.loc[invalid_gw_mask, "gateway_ref"])
    valid_settlements = settlements.loc[~settlements["gateway_ref"].isin(invalid_gw_refs)]
    amounts = valid_settlements["amount"].astype(float)
    assert (amounts > 0).all()
    assert amounts.eq(amounts.round(2)).all()


def test_csv_files_written_with_expected_counts(tmp_path: Path):
    write_synthetic_dataset(output_dir=tmp_path, seed=SEED)
    orders = pd.read_csv(tmp_path / "orders.csv")
    gateway = pd.read_csv(tmp_path / "gateway.csv")
    settlements = pd.read_csv(tmp_path / "settlements.csv")
    ground_truth = pd.read_csv(tmp_path / "ground_truth.csv")
    assert len(orders) == 150
    assert len(ground_truth) == 150
    assert len(gateway) == 140
    assert len(settlements) == 138


def test_committed_dataset_matches_generator():
    generated = generate_synthetic_dataset(seed=SEED)
    names = ("orders.csv", "gateway.csv", "settlements.csv", "ground_truth.csv")
    for frame, name in zip(generated, names):
        on_disk = pd.read_csv(DATA_DIR / name, dtype=str, keep_default_na=False)
        generated_as_str = frame.astype(str)
        pd.testing.assert_frame_equal(generated_as_str, on_disk)


def _assert_valid_money(amounts: pd.Series, currencies: pd.Series) -> None:
    values = amounts.astype(float)
    assert (values > 0).all()
    assert values.eq(values.round(2)).all()
    assert set(currencies) <= ALLOWED_CURRENCIES
