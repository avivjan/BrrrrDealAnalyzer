"""The result tiles of the website's deal modals, in the order they appear there.

The PDF report offers exactly these results (the "Generate Report" picker lists
them) and titles each section with the tile's own caption, so the report reads
like the popup the tile opens ("How Cash Flow is calculated"). Mirrors
`frontend/src/components/deal/reportResultTiles.ts` and the
`ResultTileWithCalculationButton` rows of `MyDeals.vue` / `BoughtDeals.vue`;
`tests/test_report_pdf.py` pins all three together.

Each entry is (result key = breakdown section key, tile label, unit).
"""

from __future__ import annotations

from typing import NamedTuple

from BL.analyze.explain.brrr import BRRR_SECTIONS
from BL.analyze.explain.flip import FLIP_SECTIONS


class ReportResultTile(NamedTuple):
    result_key: str
    tile_label: str
    unit: str


def _tiles_with_section_units(sections, key_and_tile_label_pairs) -> list[ReportResultTile]:
    unit_by_section_key = {key: unit for key, _label, unit in sections}
    return [
        ReportResultTile(result_key, tile_label, unit_by_section_key[result_key])
        for result_key, tile_label in key_and_tile_label_pairs
    ]


BRRRR_REPORT_RESULT_TILES: list[ReportResultTile] = _tiles_with_section_units(BRRR_SECTIONS, [
    ("cash_flow", "Cash Flow"),
    ("cash_out", "Cash Out"),
    ("cash_out_routi", "Cash-Out Routi"),
    ("cash_on_cash", "CoC"),
    ("dscr", "DSCR"),
    ("equity", "Equity"),
    ("roi", "ROI"),
    ("net_profit", "Net Profit"),
    ("total_cash_needed_for_deal", "Cash Needed"),
    ("cash_to_close_buy", "Cash to Close (Buy)"),
    ("cash_out_routi_conservative", "Cash-Out Routi (Lowest ARV)"),
    ("stolen_money", "Stolen Money"),
])

FLIP_REPORT_RESULT_TILES: list[ReportResultTile] = _tiles_with_section_units(FLIP_SECTIONS, [
    ("net_profit", "Net Profit"),
    ("roi", "ROI"),
    ("annualized_roi", "Annualized ROI"),
    ("total_cash_needed", "Cash Needed"),
    ("total_cash_needed_with_buffer", "Cash Needed (Buffered)"),
    ("total_holding_costs", "Holding Costs"),
    ("total_hml_interest", "HML Interest"),
])


def report_result_tiles_for_deal_type(deal_type: str) -> list[ReportResultTile]:
    return FLIP_REPORT_RESULT_TILES if (deal_type or "").upper() == "FLIP" else BRRRR_REPORT_RESULT_TILES


class UnknownReportResultKeys(ValueError):
    """A requested result key that is not one of the deal type's tiles, or an empty selection."""


def select_report_result_tiles(deal_type: str, selected_result_keys: list[str] | None) -> list[ReportResultTile]:
    """The tiles to render, in tile order. `None` means every tile; duplicates collapse.

    Raises `UnknownReportResultKeys` for an empty selection or any key the deal type has no tile for.
    """
    tiles = report_result_tiles_for_deal_type(deal_type)
    if selected_result_keys is None:
        return list(tiles)
    requested_keys = set(selected_result_keys)
    if not requested_keys:
        raise UnknownReportResultKeys("Choose at least one result for the report.")
    known_keys = {tile.result_key for tile in tiles}
    unknown_keys = sorted(requested_keys - known_keys)
    if unknown_keys:
        raise UnknownReportResultKeys(
            f"Unknown result key(s) for a {deal_type} report: {', '.join(unknown_keys)}. "
            f"Valid keys: {', '.join(tile.result_key for tile in tiles)}."
        )
    return [tile for tile in tiles if tile.result_key in requested_keys]
