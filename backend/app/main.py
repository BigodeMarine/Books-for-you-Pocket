"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.catalog import router as catalog_router
from app.api.routes.catalog_imports import router as catalog_imports_router
from app.api.routes.external_books import router as external_books_router


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Create and close the shared outbound HTTP client with the application."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
        application.state.google_books_client = client
        yield


app = FastAPI(title="Books for Your Pocket API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(catalog_router)
app.include_router(catalog_imports_router)
app.include_router(external_books_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Report that the API is running."""
    return {"status": "ok"}
