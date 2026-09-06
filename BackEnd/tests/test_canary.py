"""Throwaway canary: proves a failing test turns the CI check red and blocks the merge.

This file is never meant to be merged. The PR carrying it is closed once the
red check has been observed.
"""


def test_canary_must_fail():
    assert False, "CI canary: this failure is intentional"
