from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class MatchEvidence(BaseModel):
    factor: str
    value: str
    score: float = Field(ge=0.0, le=1.0)


class ReconciliationResult(BaseModel):
    order_id: str
    gateway_id: Optional[str] = None
    settlement_id: Optional[str] = None

    decision: str

    score: float = Field(ge=0.0, le=1.0)

    matching_factors: Dict[str, float] = Field(default_factory=dict)
    evidence: List[MatchEvidence] = Field(default_factory=list)

    exception_type: Optional[str] = None

    order_amount: Optional[Decimal] = None
    gateway_amount: Optional[Decimal] = None
    settlement_amount: Optional[Decimal] = None


class ValidationResult(BaseModel):
    valid: bool
    errors: List[str] = Field(default_factory=list)