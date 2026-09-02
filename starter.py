from app.factory import create_app
from app.config import settings

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("starter:app", host="0.0.0.0", port=settings.port, reload=False)
