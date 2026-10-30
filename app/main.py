import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import alerts, emails
from app.scheduler import load_jobs_from_db, scheduler, start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    load_jobs_from_db()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Email Automation & Alerts Platform",
    description="Schedule one-off or recurring emails, and monitor URLs with email alerts.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(emails.router)
app.include_router(alerts.router)


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "email-automation-platform", "docs": "/docs"}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy", "scheduler_running": scheduler.running}
