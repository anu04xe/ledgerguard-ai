import json
from datetime import datetime, timezone
from pathlib import Path


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
        f.write(
            json.dumps(record)
            + "\n"
        )
