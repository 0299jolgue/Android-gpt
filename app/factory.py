import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from .config import settings
from .database import init_db
from .logging_config import setup_logging
from .routes.web import router as web_router
from .routes.api import router as api_router


def create_app() -> FastAPI:
    setup_logging()
    log = logging.getLogger("android_gpt")
    settings.database.parent.mkdir(parents=True, exist_ok=True)
    settings.static.mkdir(parents=True, exist_ok=True)
    settings.generated.mkdir(parents=True, exist_ok=True)
    settings.logs.parent.mkdir(parents=True, exist_ok=True)
    init_db()

    app = FastAPI(title="Android GPT", version="2.1.0")
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, same_site="lax", https_only=False)
    app.mount("/static", StaticFiles(directory=settings.static), name="static")
    app.include_router(web_router)
    app.include_router(api_router, prefix="/api")
    log.info("Application initialized on %s:%s", settings.host, settings.port)
    return app
