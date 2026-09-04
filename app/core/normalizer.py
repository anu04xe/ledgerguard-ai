import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional


def normalize_reference(value: Optional[str]) -> str:
    """Return a canonical transaction reference."""
    if value is None:
        return ""

    value = str(value).strip().upper()

    # Keep alphanumeric characters only.
    value = re.sub(r"[^A-Z0-9]", "", value)

    # Normalize common prefixes.
    if value.startswith("ORDER"):
        value = "ORD" + value[5:]

    return value


def normalize_amount(value) -> Optional[Decimal]:
    if value is None:
        return None

    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def normalize_date(value) -> Optional[date]:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    try:
        return datetime.fromisoformat(str(value)).date()
    except (ValueError, TypeError):
        return None
