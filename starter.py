import logging

import uvicorn

from app.config import settings
from app.factory import create_app

app = create_app()

if __name__ == "__main__":
    logging.getLogger("android_gpt").info(
        "Starting server at http://%s:%s",
        settings.host,
        settings.port,
    )
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=False,
        access_log=True,
        log_level=settings.log_level.lower(),
    )
