from pathlib import Path
import pandas as pd

from app.data.schemas import (
    GatewayRecord,
    OrderRecord,
    SettlementRecord,
)
from app.core.matcher import reconcile_all


DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def load_data():
    orders_df = pd.read_csv(DATA_DIR / "orders.csv")
    gateways_df = pd.read_csv(DATA_DIR / "gateway.csv")
    settlements_df = pd.read_csv(DATA_DIR / "settlements.csv")

    orders = [
        OrderRecord.model_validate(row.to_dict())
        for _, row in orders_df.iterrows()
    ]

    gateways = [
        GatewayRecord.model_validate(row.to_dict())
        for _, row in gateways_df.iterrows()
    ]

    settlements = [
        SettlementRecord.model_validate(row.to_dict())
        for _, row in settlements_df.iterrows()
    ]

    return orders, gateways, settlements


def load_ground_truth():
    """Load ground truth for evaluation only.

    Ground truth is never used by the reconciliation engine.
    It exists exclusively for measuring system performance.
    """
    import math
    import pandas as pd

    from app.data.schemas import GroundTruthRecord

    path = DATA_DIR / "ground_truth.csv"

    df = pd.read_csv(path)

    records = []

    for row in df.to_dict(orient="records"):
        cleaned = {}

        for key, value in row.items():
            if value is None:
                cleaned[key] = ""
            elif isinstance(value, float) and math.isnan(value):
                cleaned[key] = ""
            else:
                cleaned[key] = value

        records.append(
            GroundTruthRecord(**cleaned)
        )

    return records


    
def main():
    orders, gateways, settlements = load_data()

    results = reconcile_all(
        orders,
        gateways,
        settlements,
    )

    counts = {}

    for result in results:
        counts[result.decision] = counts.get(result.decision, 0) + 1

    print("\nLedgerGuard Reconciliation")
    print("=" * 35)
    print(f"Orders processed: {len(results)}")

    for decision, count in sorted(counts.items()):
        print(f"{decision:20} {count}")

    print("=" * 35)


if __name__ == "__main__":
    main()
