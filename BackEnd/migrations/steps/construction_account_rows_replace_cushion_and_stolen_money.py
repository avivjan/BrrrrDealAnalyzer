"""The Cash Needed schedule lost its `rehab_cushion` and `stolen_money` rows: the construction account's deposit and
return rows replaced them (tasks/todo/ConstructionAccountPerRehab.md).

No liquidity row changes silently. Every BRRRR deal that still has one of the two legacy rows in the liquidity
timeline is flagged `liquidity_rows_out_of_date`, so it shows Re-sync with the before -> after list, and the user
confirms the change.

Runs on every boot, so it must flag each deal once only. A legacy row is "not handled yet" while its
`no_longer_in_the_deal` is false:
- an open legacy row is handled by the re-sync itself (it is removed, or it carries an override and is kept, flagged
  `no_longer_in_the_deal`);
- a done legacy row is never touched by a re-sync, so this step tags it `no_longer_in_the_deal` right away (true: the
  deal's schedule no longer has it; a done row is never counted, so nothing on the timeline moves).
Once the user has re-synced, no legacy row is left unhandled and the deal is never flagged again.
"""

from sqlalchemy import text

LEGACY_ITEM_KEYS_REPLACED_BY_THE_CONSTRUCTION_ACCOUNT_ROWS = ("rehab_cushion", "stolen_money")

# (the liquidity rows' deal board, the deal table)
BRRR_DEAL_TABLE_BY_BOARD = (("my_deals", "active_deals"), ("bought", "bought_brrrr_deals"))

# Constants of this module only, never user input.
_LEGACY_ITEM_KEYS_SQL_LIST = ", ".join(f"'{item_key}'" for item_key in LEGACY_ITEM_KEYS_REPLACED_BY_THE_CONSTRUCTION_ACCOUNT_ROWS)
_LEGACY_ROW_NOT_HANDLED_YET = f"source_item_key IN ({_LEGACY_ITEM_KEYS_SQL_LIST}) AND no_longer_in_the_deal = FALSE"


def flag_deals_with_cushion_or_stolen_money_rows_as_liquidity_out_of_date(engine, inspector) -> None:
    table_names = inspector.get_table_names()
    if "liquidity_transactions" not in table_names:
        return
    liquidity_columns = {column["name"] for column in inspector.get_columns("liquidity_transactions")}
    if not {"source_item_key", "source_deal_board", "source_deal_id", "no_longer_in_the_deal", "done_at"} <= liquidity_columns:
        return
    with engine.begin() as connection:
        for deal_board, deal_table in BRRR_DEAL_TABLE_BY_BOARD:
            if deal_table not in table_names:
                continue
            if "liquidity_rows_out_of_date" not in {column["name"] for column in inspector.get_columns(deal_table)}:
                continue
            connection.execute(
                text(
                    f"UPDATE {deal_table} SET liquidity_rows_out_of_date = TRUE "
                    f"WHERE liquidity_rows_out_of_date = FALSE AND id IN ("
                    f"SELECT source_deal_id FROM liquidity_transactions "
                    f"WHERE source_deal_board = :deal_board AND {_LEGACY_ROW_NOT_HANDLED_YET})"
                ),
                {"deal_board": deal_board},
            )
        connection.execute(
            text(
                f"UPDATE liquidity_transactions SET no_longer_in_the_deal = TRUE "
                f"WHERE done_at IS NOT NULL AND {_LEGACY_ROW_NOT_HANDLED_YET}"
            )
        )
