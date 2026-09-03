from datetime import date as date_cls

from ReqRes.common.reps_schemas import RepsStats


def compute_stats(user: str, entries: list[dict]) -> RepsStats:
    today = date_cls.today()
    days_in_year = 366 if (today.year % 4 == 0 and (today.year % 100 != 0 or today.year % 400 == 0)) else 365
    days_elapsed = max(1, (today - date_cls(today.year, 1, 1)).days + 1)

    user_entries = [e for e in entries if (e.get("user") or "").strip() == user]
    total = round(sum(float(e.get("total_hours") or 0) for e in user_entries), 2)
    material = round(sum(
        float(e.get("total_hours") or 0)
        for e in user_entries
        if e.get("material_participation_rentals")
    ), 2)
    non_material = round(total - material, 2)

    year_pct = (days_elapsed / days_in_year) * 100.0
    reps_pct = (total / 750.0) * 100.0
    mat_pct = (material / 500.0) * 100.0

    return RepsStats(
        user=user,  # type: ignore[arg-type]
        total_hours=total,
        material_hours=material,
        non_material_hours=non_material,
        entry_count=len(user_entries),
        days_elapsed=days_elapsed,
        days_in_year=days_in_year,
        year_progress_pct=round(year_pct, 2),
        reps_750_pct=round(reps_pct, 2),
        material_500_pct=round(mat_pct, 2),
        avg_daily_hours_total=round(total / days_elapsed, 2),
        avg_daily_hours_material=round(material / days_elapsed, 2),
    )
