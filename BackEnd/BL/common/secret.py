"""A secret value that cannot be printed by accident.

`Secret` wraps a credential in a `bytearray` and only hands the plaintext out
through `reveal()`, which callers use at the single point where the value is
needed (an `Authorization` header). `repr()`, `str()`, f-strings and logging
all see `Secret(***)`. `wipe()` zeroes the buffer; Python strings are
immutable, so this is best-effort hygiene rather than a guarantee (see
SECURITY_PLAN.md Appendix A.4).
"""

from __future__ import annotations

import hmac


class Secret:
    __slots__ = ("_buf",)

    def __init__(self, value: str | bytes | None):
        raw = value.encode() if isinstance(value, str) else bytes(value or b"")
        self._buf = bytearray(raw)

    def reveal(self) -> str:
        return bytes(self._buf).decode()

    def wipe(self) -> None:
        for i in range(len(self._buf)):
            self._buf[i] = 0
        del self._buf[:]

    def __bool__(self) -> bool:
        return len(self._buf) > 0

    def __len__(self) -> int:
        return len(self._buf)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Secret):
            return hmac.compare_digest(bytes(self._buf), bytes(other._buf))
        return NotImplemented

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return "Secret(***)"

    __str__ = __repr__

    def __format__(self, spec: str) -> str:
        return "Secret(***)"
