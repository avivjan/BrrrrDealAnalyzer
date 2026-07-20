import re
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

_MONTH_YEAR_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class PropertyCashFlowHistoryCreate(BaseModel):
    history_id: Optional[str] = None
    property_id: str
    month_year: str
    monthly_cash_flow: Decimal = Decimal("0")
    cumulative_cash_flow: Decimal = Decimal("0")

    @field_validator("month_year")
    @classmethod
    def validate_month_year(cls, value: str) -> str:
        if not _MONTH_YEAR_RE.match(value):
            raise ValueError("month_year must match YYYY-MM")
        return value


class PropertyCashFlowHistoryUpdate(BaseModel):
    month_year: Optional[str] = None
    monthly_cash_flow: Optional[Decimal] = None
    cumulative_cash_flow: Optional[Decimal] = None

    @field_validator("month_year")
    @classmethod
    def validate_month_year(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not _MONTH_YEAR_RE.match(value):
            raise ValueError("month_year must match YYYY-MM")
        return value


class PropertyCashFlowHistoryRes(BaseModel):
    history_id: str
    property_id: str
    month_year: str
    monthly_cash_flow: Decimal
    cumulative_cash_flow: Decimal
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}
