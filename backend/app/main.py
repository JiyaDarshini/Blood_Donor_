import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from app.config import settings
from app.database import engine, Base
from app.routers import (
    auth, donors, requests, invitations, donations, rewards, notifications, admin
)
from app.utils.seed import seed_database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bloodsos")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Smart Blood Donation and Emergency Response System API",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS setup
origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",")] if settings.CORS_ORIGINS != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(donors.router, prefix=settings.API_V1_STR)
app.include_router(requests.router, prefix=settings.API_V1_STR)
app.include_router(invitations.router, prefix=settings.API_V1_STR)
app.include_router(donations.router, prefix=settings.API_V1_STR)
app.include_router(rewards.router, prefix=settings.API_V1_STR)
app.include_router(notifications.router, prefix=settings.API_V1_STR)
app.include_router(admin.router, prefix=settings.API_V1_STR)


@app.on_event("startup")
def startup_event():
    logger.info("Initializing Blood SOS Database...")
    Base.metadata.create_all(bind=engine)
    try:
        # Check and migrate columns if needed
        with engine.connect() as conn:
            from sqlalchemy import text
            if "sqlite" in str(engine.url):
                res = conn.execute(text("PRAGMA table_info(users)")).fetchall()
                col_names = [r[1] for r in res]
                if "is_phone_verified" not in col_names:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_phone_verified BOOLEAN DEFAULT 0"))
                    conn.commit()
    except Exception as e:
        logger.warning(f"Database column migration note: {e}")

    try:
        seed_database()
        logger.info("Blood SOS Initialized Successfully.")
    except Exception as e:
        logger.error(f"Seed data check error: {e}")


@app.get("/api/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": "connected"
    }


# Static Frontend Mounting
BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

if FRONTEND_DIR.exists():
    css_path = FRONTEND_DIR / "css"
    js_path = FRONTEND_DIR / "js"
    assets_path = FRONTEND_DIR / "assets"

    if css_path.exists():
        app.mount("/css", StaticFiles(directory=str(css_path)), name="css")
    if js_path.exists():
        app.mount("/js", StaticFiles(directory=str(js_path)), name="js")
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

    # Serve HTML pages directly
    @app.get("/", include_in_schema=False)
    def serve_home():
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/{page_name}.html", include_in_schema=False)
    def serve_page(page_name: str):
        file_path = FRONTEND_DIR / f"{page_name}.html"
        if file_path.exists():
            return FileResponse(file_path)
        return JSONResponse({"error": "Page not found"}, status_code=404)
