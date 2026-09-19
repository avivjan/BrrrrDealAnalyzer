"""Add the BRRRR lifecycle columns to the two BRRRR deal tables, backfilling existing rows.

Purely additive and idempotent: each column is added (with its DDL default) and backfilled
in one transaction via `add_column_if_missing`, under the runner's advisory lock. Old
processes ignore columns they do not map; new processes never read a NULL where the model
expects a value, because the backfill runs before the first request. Fresh databases get
the columns from `create_all` and this becomes a no-op.

Owner's decision: existing deals take the NEW defaults (an old deal re-analyzes under the new
model), with two exceptions that preserve what the deal already said:

* `construction_loan_budget_in_thousands` mirrors the legacy `use_HM_for_rehab` flag: a
  hard-money-funded rehab becomes a budget equal to the rehab with its contingency, so the
  leverage (and the payoff at refi) is unchanged; a cash rehab becomes a 0 budget.
* `buy_closing_date` stays NULL (unknown), which leaves every date-driven figure out until
  the owner types the date.

The backfill literal must equal the SQLAlchemy `default=` in
`DAL/data_models/common/brrr_lifecycle.py` and the Pydantic default in
`ReqRes/common/brrr_lifecycle_inputs.py`, because a PUT rewrites every column.
"""

from sqlalchemy import text

from migrations.add_column import add_column_if_missing

BRRR_TABLES = ("active_deals", "bought_brrrr_deals")

# (column, DDL, backfill SQL for existing rows; None = leave NULL)
BRRR_LIFECYCLE_COLUMNS = (
    # Buy
    ("buy_closing_date", "DATE", None),
    ("earnest_money_deposit", "NUMERIC(12,2) DEFAULT 5000", "5000"),
    ("loan_charges_buy", "NUMERIC(12,2) DEFAULT 900", "900"),
    ("recording_transfer_buy", "NUMERIC(12,2)", None),
    ("title_mode_buy", "VARCHAR(20) DEFAULT 'standard'", "'standard'"),
    ("title_escrow_buy", "NUMERIC(12,2)", None),
    ("online_notary_buy", "BOOLEAN DEFAULT TRUE", "TRUE"),
    ("other_closing_costs_buy", "NUMERIC(12,2) DEFAULT 0", "0"),
    ("seller_paid_current_year_taxes", "BOOLEAN", None),
    # Rehab
    # Added WITHOUT a DDL default on purpose: Postgres fills existing rows with the default at
    # ADD COLUMN time, which would leave nothing for the CASE backfill to do. The default is
    # set afterwards (below). SQLAlchemy created the mixed-case column as a quoted identifier.
    ("construction_loan_budget_in_thousands", "NUMERIC(14,4)",
     'CASE WHEN "use_HM_for_rehab" THEN rehab_cost_in_thousands * (1 + rehab_contingency_percent / 100) ELSE 0 END'),
    ("rehab_cushion", "NUMERIC(12,2) DEFAULT 5000", "5000"),
    # Rent & holding
    ("days_until_rented", "INTEGER DEFAULT 90", "90"),
    ("monthly_utilities_until_rented", "NUMERIC(12,2) DEFAULT 80", "80"),
    ("maintenance_before_refi", "NUMERIC(12,2) DEFAULT 500", "500"),
    ("appliances", "NUMERIC(12,2) DEFAULT 630", "630"),
    # Refinance
    ("loan_charges_refi", "NUMERIC(12,2) DEFAULT 200", "200"),
    ("recording_transfer_refi", "NUMERIC(12,2)", None),
    ("title_escrow_refi", "NUMERIC(12,2)", None),
    ("online_notary_refi", "BOOLEAN DEFAULT TRUE", "TRUE"),
    ("appraisal_fee", "NUMERIC(12,2) DEFAULT 700", "700"),
    ("survey_fee", "NUMERIC(12,2) DEFAULT 385", "385"),
    ("refi_underwriting_fee", "NUMERIC(12,2) DEFAULT 2000", "2000"),
    ("broker_processing_fee_refi", "NUMERIC(12,2) DEFAULT 395", "395"),
    ("other_closing_costs_refi", "NUMERIC(12,2) DEFAULT 0", "0"),
    ("maintenance_reserve", "NUMERIC(12,2) DEFAULT 1500", "1500"),
    ("vacancy_reserve", "NUMERIC(12,2)", None),
    ("capex_reserve", "NUMERIC(12,2) DEFAULT 2500", "2500"),
    ("lowest_arv_in_thousands", "NUMERIC(14,4)", None),
)


def add_brrr_lifecycle_columns(engine, inspector) -> None:
    for table_name in BRRR_TABLES:
        if table_name not in inspector.get_table_names():
            continue
        before = {col["name"] for col in inspector.get_columns(table_name)}
        for column_name, column_ddl, backfill_value in BRRR_LIFECYCLE_COLUMNS:
            add_column_if_missing(engine, inspector, table_name, column_name, column_ddl, backfill_value)
        if "construction_loan_budget_in_thousands" not in before:
            with engine.begin() as conn:
                conn.execute(text(
                    f"ALTER TABLE {table_name} ALTER COLUMN construction_loan_budget_in_thousands SET DEFAULT 0"
                ))
