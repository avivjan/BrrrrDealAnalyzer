from fastapi import APIRouter

from treasury.controllers.llc_controller import router as llc_router
from treasury.controllers.property_controller import router as property_router
from treasury.controllers.transaction_controller import router as transaction_router
from treasury.controllers.cash_flow_controller import router as cash_flow_router
from treasury.controllers.webhook_controller import router as webhook_router

router = APIRouter()
router.include_router(llc_router)
router.include_router(property_router)
router.include_router(transaction_router)
router.include_router(cash_flow_router)
router.include_router(webhook_router)
