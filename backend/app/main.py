from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.core.settings import settings, validate_runtime_settings
from app.db.session import init_db
from app.api.v1 import auth, patients, chat, reports, whatsapp, orders, health_metrics, maps


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_runtime_settings()
    await init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# GZip response compression for low latency payload transfers
app.add_middleware(GZipMiddleware, minimum_size=500)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(patients.router, prefix=settings.api_v1_prefix)
app.include_router(chat.router, prefix=settings.api_v1_prefix)
app.include_router(reports.router, prefix=settings.api_v1_prefix)
app.include_router(whatsapp.router, prefix=settings.api_v1_prefix)
app.include_router(orders.router, prefix=settings.api_v1_prefix)
app.include_router(health_metrics.router, prefix=settings.api_v1_prefix)
app.include_router(maps.router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok", "app": settings.app_name}
