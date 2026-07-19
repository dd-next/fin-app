"""FinApp v2 FastAPI entrypoint."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.assets import router as assets_router, seed_default_assets
from app.accounts import router as accounts_router
from app.auth import router as auth_router
from app.categories import router as categories_router
from app.db import SessionLocal
from app.workspaces import router as workspaces_router
from app.valuation_rates import router as valuation_rates_router
from app.transactions import router as transactions_router
from app.sharing import router as sharing_router
from app.plan import router as plan_router
from app.periods import router as periods_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    del app
    async with SessionLocal() as session:
        await seed_default_assets(session)
    yield


app = FastAPI(title="FinApp v2", lifespan=lifespan)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(workspaces_router, prefix="/api/v1")
app.include_router(valuation_rates_router, prefix="/api/v1")
app.include_router(assets_router, prefix="/api/v1")
app.include_router(categories_router, prefix="/api/v1")
app.include_router(accounts_router, prefix="/api/v1")
app.include_router(transactions_router, prefix="/api/v1")
app.include_router(sharing_router, prefix="/api/v1")
app.include_router(plan_router, prefix="/api/v1")
app.include_router(periods_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}


STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
