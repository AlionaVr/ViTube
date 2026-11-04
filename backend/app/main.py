from fastapi import FastAPI

app = FastAPI(
    title="ViTube API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",  # under /api so nginx proxies it with the rest of the API
)


@app.get("/api/health", tags=["system"], summary="Liveness check")
async def health() -> dict[str, str]:
    return {"status": "ok"}
