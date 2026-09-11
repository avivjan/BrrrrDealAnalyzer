"""The explanation layer: turns a finished results record into the `breakdowns` the PDF renders.

One module per deal type (`brrr.py`, `flip.py`). Each reads the frozen results
record and the request payload, never recomputes a number, and guards every
equation it narrates with `check(...)` so a change to the math that is not
mirrored here fails loudly instead of printing a stale explanation.
"""
