"""Point d'entrée FastAPI — voir PROJECT_V1.md §7."""
import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from valo.config import settings
from valo.logging import configure_logging
from valo.routers import comps, runs, targets, transactions

configure_logging()

if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment)

app = FastAPI(title="outil-valo-comparables", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(targets.router)
app.include_router(comps.router)
app.include_router(runs.router)
app.include_router(transactions.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
