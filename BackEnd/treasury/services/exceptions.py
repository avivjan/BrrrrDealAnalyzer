"""Domain-level exceptions raised by the treasury services layer."""

class TreasuryError(Exception):
    pass


class NotFoundError(TreasuryError):
    pass


class ValidationError(TreasuryError):
    pass
