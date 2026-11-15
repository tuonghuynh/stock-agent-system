from fastapi import FastAPI

from stock_agent import __version__

app = FastAPI(title="Stock Agent System", version=__version__)


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
def readiness() -> dict[str, str]:
    return {"status": "ready"}
