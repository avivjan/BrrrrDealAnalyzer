"""Make the Member Loan tables append-only at the database level. Idempotent.

Proposals, decisions and audit entries refuse every UPDATE and DELETE. A
statement send may change exactly once: `status` from `sending` to `sent` or
`failed`, filling `sent_at`, `objection_deadline` and `error_text`; nothing
else on the row may change and it can never be deleted.

TRUNCATE does not fire row triggers; only the test harness uses it
(`tests/conftest.py::clean_database`). Direct edits by someone with database
access are caught by the hash chains instead (`GET /member-loan/integrity`).
"""

from sqlalchemy import text

REFUSE_ROW_CHANGE_FUNCTION = """
CREATE OR REPLACE FUNCTION member_loan_refuse_row_change() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'member loan history is append-only: % on % is not allowed', TG_OP, TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;
"""

STATEMENT_SEND_STATUS_ONLY_FUNCTION = """
CREATE OR REPLACE FUNCTION member_loan_statement_send_status_only() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'member loan statement sends cannot be deleted';
    END IF;
    IF OLD.status <> 'sending' OR NEW.status NOT IN ('sent', 'failed') THEN
        RAISE EXCEPTION 'a member loan statement send may only move once from sending to sent or failed';
    END IF;
    IF NEW.id IS DISTINCT FROM OLD.id
        OR NEW.statement_month IS DISTINCT FROM OLD.statement_month
        OR NEW.is_dry_run IS DISTINCT FROM OLD.is_dry_run
        OR NEW.recipients::text IS DISTINCT FROM OLD.recipients::text
        OR NEW.sender_address IS DISTINCT FROM OLD.sender_address
        OR NEW.statement_snapshot::text IS DISTINCT FROM OLD.statement_snapshot::text
        OR NEW.engine_version IS DISTINCT FROM OLD.engine_version
        OR NEW.pdf_sha256 IS DISTINCT FROM OLD.pdf_sha256
        OR NEW.proposals_left_out_count IS DISTINCT FROM OLD.proposals_left_out_count
        OR NEW.started_at IS DISTINCT FROM OLD.started_at THEN
        RAISE EXCEPTION 'only the status fields of a member loan statement send may change';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

APPEND_ONLY_TRIGGER_BY_TABLE = {
    "member_loan_events": "member_loan_refuse_row_change",
    "member_loan_event_decisions": "member_loan_refuse_row_change",
    "member_loan_audit_entries": "member_loan_refuse_row_change",
    "member_loan_statement_sends": "member_loan_statement_send_status_only",
}


def add_member_loan_append_only_triggers(engine) -> None:
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as connection:
        connection.execute(text(REFUSE_ROW_CHANGE_FUNCTION))
        connection.execute(text(STATEMENT_SEND_STATUS_ONLY_FUNCTION))
        for table_name, function_name in APPEND_ONLY_TRIGGER_BY_TABLE.items():
            trigger_name = f"{table_name}_append_only"
            connection.execute(text(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}"))
            connection.execute(text(
                f"CREATE TRIGGER {trigger_name} BEFORE UPDATE OR DELETE ON {table_name} "
                f"FOR EACH ROW EXECUTE FUNCTION {function_name}()"
            ))
