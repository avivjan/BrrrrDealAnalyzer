"""Nightly test-report email: parsing, analysis, rendering and sending.

Entry point: ``nightly.main.main(argv)`` (wrapped by ``.github/scripts/nightly_e2e_email.py``).
Pure standard library except ``charts``, which uses matplotlib when available.
"""
