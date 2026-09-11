from typing import Literal, Optional

from pydantic import BaseModel, Field


class CalcTerm(BaseModel):
    """One operand of a sum-type calculation step, in dollars."""

    label: str = Field(..., description="Name of the operand, e.g. 'Down Payment'.")
    value: float = Field(..., description="The operand's value in dollars.")
    sign: Literal["+", "-"] = Field("+", description="Whether the operand is added or subtracted.")


class CalcStep(BaseModel):
    """A single self-documenting line in a calculation.

    `label`   - human-readable name of the variable ("Operating Expenses").
    `value`   - the numeric result of the step (always a float for JSON).
    `unit`    - how to read `value`: dollars, a percentage or a plain ratio.
    `formula` - the literal expression evaluated, with concrete values
                substituted (e.g. "$2000 - $800 - $1000 = $200").
    `terms`   - for a sum-type step, the same expression as structured operands
                (they add up to `value`), so a renderer can stack them.
    `note`    - an optional aside explaining a convention or a special case.
    """

    label: str = Field(..., description="Human-readable name of the step, e.g. 'Net Operating Income (NOI)'.")
    value: float = Field(..., description="The step's result. Read it with `unit`; -1 and -2 are the infinite / undefined sentinels on percentage steps.")
    unit: Literal["money", "pct", "ratio"] = Field("money", description="How to read `value`: 'money' = dollars, 'pct' = percent (12.5 = 12.5%), 'ratio' = a plain multiple (1.2 = 1.2x).")
    formula: str = Field(..., description="The expression evaluated, with the concrete numbers filled in.")
    terms: Optional[list[CalcTerm]] = Field(None, description="For a sum-type step: the operands of `formula`, in order; they add up to `value`. Absent on other steps.")
    note: Optional[str] = Field(None, description="Optional aside: a convention or special case behind this step.")
