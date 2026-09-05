import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any


AUDIT_FILE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "audit_log.jsonl"
)


def log_investigation(
    order_id,
    exception_type,
    deterministic_score,
    investigation,
):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "order_id": order_id,
        "exception_type": exception_type,
        "deterministic_score": deterministic_score,
        "ai_finding": investigation.get("finding"),
        "ai_confidence": investigation.get("confidence"),
        "recommended_action": investigation.get(
            "recommended_action"
        ),
        "requires_human_review": investigation.get(
            "requires_human_review",
            True,
        ),
    }

    AUDIT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with AUDIT_FILE.open(
        "a",
        encoding="utf-8",
    ) as f:
        f.write(json.dumps(record) + "\n")


def load_audit_log() -> List[Dict[str, Any]]:
    """
    Read previously completed AI investigations.

    The audit log is append-only from the application's perspective.
    Missing or malformed records are skipped rather than crashing
    the dashboard.
    """

    if not AUDIT_FILE.exists():
        return []

    records = []

    with AUDIT_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:

        for line in f:
            line = line.strip()

            if not line:
                continue

            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return records


def get_audit_for_order(
    order_id: str,
) -> List[Dict[str, Any]]:
    """
    Return all investigations previously performed for an order.
    """

    return [
        record
        for record in load_audit_log()
        if record.get("order_id") == order_id
    ]