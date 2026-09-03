from DAL.data_models import RepsPerson, RepsActivityCategory
from ReqRes.common.reps_schemas import RepsPersonRes, RepsActivityCategoryRes


def person_to_res(p: RepsPerson) -> RepsPersonRes:
    return RepsPersonRes(
        id=str(p.id),
        name=p.name,
        role=p.role,
        notes=p.notes,
        created_at=p.created_at.isoformat() if p.created_at else None,
        updated_at=p.updated_at.isoformat() if p.updated_at else None,
    )


def category_to_res(c: RepsActivityCategory) -> RepsActivityCategoryRes:
    return RepsActivityCategoryRes(
        id=str(c.id),
        name=c.name,
        sort_order=c.sort_order or 0,
        is_default=bool(c.is_default),
    )
