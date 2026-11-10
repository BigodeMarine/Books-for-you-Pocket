"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.routes.catalog import router as catalog_router

app = FastAPI(title="Books for Your Pocket API", version="0.1.0")
app.include_router(catalog_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Report that the API is running."""
    return {"status": "ok"}
