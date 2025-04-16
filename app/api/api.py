from fastapi import APIRouter

from app.api.v1 import items, users, fees, predictions, ccxt

api_router = APIRouter()
api_router.include_router(items.router, prefix="/items", tags=["items"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(fees.router, prefix="/fees", tags=["fees"])
api_router.include_router(predictions.router, prefix="/v1", tags=["predictions"])
api_router.include_router(ccxt.router, prefix="/v1/ccxt", tags=["ccxt"]) 