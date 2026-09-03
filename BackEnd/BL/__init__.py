"""Business logic layer: framework-agnostic orchestrators, grouped by endpoint
division. BL functions accept only pure Python types, Pydantic models, or DB
sessions, and return pure models or data -- never FastAPI objects. The one
reviewed exception is `HTTPException` raised from `BL.common.deal_validation`
and `BL.common.deal_math.calc_mortgage_payment` (see their docstrings).
"""
