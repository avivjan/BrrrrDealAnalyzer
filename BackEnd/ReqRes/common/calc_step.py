from pydantic import BaseModel


class CalcStep(BaseModel):
    """A single self-documenting line in a calculation.

    `label`   - human-readable name of the variable ("Operating Expenses").
    `value`   - the numeric result of the step (always a float for JSON).
    `formula` - the literal expression evaluated, with concrete values
                substituted (e.g. "$2000 - $800 - $1000 = $200").
    """

    label: str
    value: float
    formula: str
