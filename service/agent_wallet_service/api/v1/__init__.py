"""API v1 router aggregation."""

from fastapi import APIRouter

from agent_wallet_service.api.v1 import (
    admin,
    holds,
    payment_intents,
    refunds,
    resolve,
    transfers,
    wallets,
)

router = APIRouter()

# Include all v1 routers
router.include_router(wallets.router, prefix="/wallets", tags=["wallets"])
router.include_router(transfers.router, prefix="/transfers", tags=["transfers"])
router.include_router(holds.router, prefix="/holds", tags=["holds"])
router.include_router(payment_intents.router, prefix="/payment_intents", tags=["payment_intents"])
router.include_router(refunds.router, prefix="/refunds", tags=["refunds"])
router.include_router(resolve.router, prefix="/resolve", tags=["resolve"])
router.include_router(admin.router, prefix="/admin", tags=["admin"])
