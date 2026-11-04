from DAL.data_models import LiquidityTransaction, LiquidityRecurringTransaction, LiquiditySettings
from ReqRes.common.liquidity_schemas import (
    LiquidityTransactionRes,
    LiquidityRecurringTransactionRes,
    LiquidityRecurringOccurrenceStateRes,
    LiquiditySettingsRes,
)


def txn_to_res(txn: LiquidityTransaction) -> LiquidityTransactionRes:
    return LiquidityTransactionRes(
        id=str(txn.id),
        effective_date=txn.effective_date,
        description=txn.description,
        amount_dollars=float(txn.amount_dollars),
        done_at=txn.done_at.isoformat() if txn.done_at else None,
        originally_planned_date=txn.originally_planned_date,
        user_overrode_date=bool(txn.user_overrode_date),
        user_overrode_amount=bool(txn.user_overrode_amount),
        source_deal_board=txn.source_deal_board,
        source_deal_id=str(txn.source_deal_id) if txn.source_deal_id else None,
        source_item_key=txn.source_item_key,
        source_occurrence_number=txn.source_occurrence_number,
        sequence_within_day=txn.sequence_within_day,
        created_because_refi_is_late=bool(txn.created_because_refi_is_late),
        no_longer_in_the_deal=bool(txn.no_longer_in_the_deal),
        created_at=txn.created_at.isoformat() if txn.created_at else None,
        updated_at=txn.updated_at.isoformat() if txn.updated_at else None,
    )


def recurring_to_res(rule: LiquidityRecurringTransaction) -> LiquidityRecurringTransactionRes:
    return LiquidityRecurringTransactionRes(
        id=str(rule.id),
        description=rule.description,
        amount_dollars=float(rule.amount_dollars),
        start_date=rule.start_date,
        end_date=rule.end_date,
        occurrences=rule.occurrences,
        frequency=rule.frequency,  # type: ignore[arg-type]
        interval=int(rule.interval or 1),
        occurrences_can_be_overdue_from=rule.occurrences_can_be_overdue_from,
        occurrence_states=[
            LiquidityRecurringOccurrenceStateRes(
                scheduled_date=state.scheduled_date,
                done_at=state.done_at.isoformat() if state.done_at else None,
                moved_to_date=state.moved_to_date,
            )
            for state in rule.occurrence_states
        ],
        created_at=rule.created_at.isoformat() if rule.created_at else None,
        updated_at=rule.updated_at.isoformat() if rule.updated_at else None,
    )


def settings_to_res(settings: LiquiditySettings) -> LiquiditySettingsRes:
    return LiquiditySettingsRes(
        opening_balance_dollars=float(settings.opening_balance_dollars),
        opening_balance_date=settings.opening_balance_date,
        reserve_dollars=float(settings.reserve_dollars),
        mercury_account_ids_counted_as_cash=settings.mercury_account_ids_counted_as_cash,
        timezone_name=settings.timezone_name or "America/New_York",
        updated_at=settings.updated_at.isoformat() if settings.updated_at else None,
    )
