"""FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(title="Books for Your Pocket API", version="0.1.0")


@app.get("/health")
def health_check() -> dict[str, str]:
    """Report that the API is running."""
    return {"status": "ok"}
