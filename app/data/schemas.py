"""Record schemas for synthetic payment data.

These models describe orders, gateway captures, bank settlements, and
evaluation-only ground truth. Ground truth must not be consumed by a
reconciliation engine.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


ALLOWED_CURRENCIES = frozenset({"USD", "EUR", "GBP", "INR"})

EXCEPTION_TYPES = frozenset(
    {
        "amount_mismatch",
        "missing_gateway",
        "missing_settlement",
        "duplicate_settlement",
        "delayed_settlement",
        "inconsistent_reference",
        "ambiguous_reference",
        "invalid_record",
    }
)


class OrderRecord(BaseModel):
    order_id: str
    customer_id: str
    amount: Decimal
    currency: str
    order_date: date
    description: str


class GatewayRecord(BaseModel):
    gateway_ref: str
    order_reference: str
    amount: Decimal
    currency: str
    captured_at: datetime
    status: str
    description: str


class SettlementRecord(BaseModel):
    settlement_id: str
    gateway_ref: str
    amount: Decimal
    settlement_date: date
    status: str
    bank_reference: str


class GroundTruthRecord(BaseModel):
    """Evaluation labels only. Never feed this to reconciliation."""

    order_id: str
    expected_gateway_relationship: str
    expected_settlement_relationship: str
    expected_outcome: str
    exception_type: Optional[str] = Field(default="")

    @field_validator("exception_type", mode="before")
    @classmethod
    def empty_exception(cls, value: Optional[str]) -> str:
        if value is None:
            return ""
        return value
