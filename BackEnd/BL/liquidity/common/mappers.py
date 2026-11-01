from DAL.data_models import LiquidityTransaction, LiquidityRecurringTransaction, LiquiditySettings
from ReqRes.common.liquidity_schemas import (
    LiquidityTransactionRes,
    LiquidityRecurringTransactionRes,
    LiquiditySettingsRes,
)


def txn_to_res(txn: LiquidityTransaction) -> LiquidityTransactionRes:
    return LiquidityTransactionRes(
        id=str(txn.id),
        effective_date=txn.effective_date,
        description=txn.description,
        amount_dollars=float(txn.amount_dollars),
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
        created_at=rule.created_at.isoformat() if rule.created_at else None,
        updated_at=rule.updated_at.isoformat() if rule.updated_at else None,
    )


def settings_to_res(settings: LiquiditySettings) -> LiquiditySettingsRes:
    return LiquiditySettingsRes(
        opening_balance_dollars=float(settings.opening_balance_dollars),
        opening_balance_date=settings.opening_balance_date,
        reserve_dollars=float(settings.reserve_dollars),
        mercury_account_ids_counted_as_cash=settings.mercury_account_ids_counted_as_cash,
        updated_at=settings.updated_at.isoformat() if settings.updated_at else None,
    )
