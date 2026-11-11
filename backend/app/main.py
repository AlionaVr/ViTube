from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import Depends, FastAPI

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.redis import create_redis
from app.core.storage import get_storage_settings, open_storage
from app.db.session import create_engine, create_sessionmaker
from app.modules.auth.config import get_auth_settings
from app.modules.auth.deps import verify_csrf
from app.modules.auth.router import router as auth_router
from app.modules.auth.sessions import SessionStore
from app.modules.comments.router import router as comments_router
from app.modules.reactions.router import router as reactions_router
from app.modules.search.router import router as search_router
from app.modules.videos.internal import router as internal_router
from app.modules.videos.router import categories_router, me_router
from app.modules.videos.router import router as videos_router
from app.modules.views.router import router as views_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Clients shared for the app's lifetime, like singleton beans. Connections open on first use.
    settings = get_settings()
    auth_settings = get_auth_settings()  # fails at startup, not at the first login
    engine = create_engine(settings)
    app.state.sessionmaker = create_sessionmaker(engine)
    app.state.redis = create_redis(settings)
    app.state.sessions = SessionStore(app.state.redis, auth_settings.session_secret)
    async with AsyncExitStack() as stack:  # closes everything in reverse order on shutdown
        stack.push_async_callback(engine.dispose)
        stack.push_async_callback(app.state.redis.aclose)
        app.state.storage = await stack.enter_async_context(open_storage(get_storage_settings()))
        yield


app = FastAPI(
    title="ViTube API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",  # under /api so nginx proxies it with the rest of the API
    lifespan=lifespan,
    dependencies=[Depends(verify_csrf)],  # every route, present and future (ADR 0005)
)
register_error_handlers(app)
app.include_router(auth_router)
app.include_router(videos_router)
app.include_router(categories_router)
app.include_router(me_router)
app.include_router(search_router)
app.include_router(reactions_router)
app.include_router(comments_router)
app.include_router(views_router)
app.include_router(internal_router)


@app.get("/api/health", tags=["system"], summary="Liveness check")
async def health() -> dict[str, str]:
    return {"status": "ok"}
