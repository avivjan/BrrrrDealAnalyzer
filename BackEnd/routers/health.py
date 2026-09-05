"""GET /helloworld."""

from fastapi import APIRouter

from BL.health.helloworld import helloworld as helloworld_bl

router = APIRouter()


@router.get("/helloworld")
def helloworld() -> dict:
    return helloworld_bl()
