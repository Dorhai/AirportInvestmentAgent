from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import time

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import health, airports, chat, tts
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.agent.llm import OpenAILLMClient
from app.agent.orchestrator import Orchestrator
from app.agent.session import SessionStore
from app.providers.aviation import FaaNasProvider, OpenSkyProvider
from app.providers.aviation_weather import AviationWeatherProvider
from app.providers.openflights import OpenFlightsRoutesProvider
from app.providers.opensky_auth import token_manager_from_settings
from app.providers.bts_on_time import BtsOnTimeProvider
from app.providers.faa_bulk import FaaAcaisFileProvider, FaaAtadsFileProvider
from app.providers.bts_t100 import BtsT100FileProvider
from app.providers.base import AviationProvider, ContextProvider
from app.providers.fallback import CompositeProvider, ContextComposite, SampleProvider
from app.services.airport_service import AirportCatalog, CoordinateLookup
from app.services.analysis_service import AnalysisService
from app.services.tts_service import TTSService


# ---------------------------------------------------------------------------
# Simple in-memory token-bucket rate limiter  (Guardrail 14)
# ---------------------------------------------------------------------------

_RATE_LIMIT_REQUESTS = 60
_RATE_LIMIT_WINDOW_S = 60.0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-client (IP) sliding-window request counter.

    Allows ``_RATE_LIMIT_REQUESTS`` requests per ``_RATE_LIMIT_WINDOW_S``
    seconds.  Resets the counter once the window elapses.
    """

    def __init__(self, app: FastAPI) -> None:  # type: ignore[override]
        super().__init__(app)
        self._clients: dict[str, tuple[float, int]] = {}

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()

        window_start, count = self._clients.get(client_ip, (now, 0))

        if now - window_start >= _RATE_LIMIT_WINDOW_S:
            window_start = now
            count = 0

        count += 1
        self._clients[client_ip] = (window_start, count)

        if count > _RATE_LIMIT_REQUESTS:
            return Response(
                content='{"detail":"Rate limit exceeded. Try again shortly."}',
                status_code=429,
                media_type="application/json",
            )

        return await call_next(request)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    coords = CoordinateLookup()
    catalog = AirportCatalog()
    sample = SampleProvider()

    async with httpx.AsyncClient() as http:
        opensky = OpenSkyProvider(
            http,
            coords,
            timeout_s=max(settings.HTTP_TIMEOUT_S, settings.OPENSKY_TIMEOUT_S),
            token_manager=token_manager_from_settings(
                http, timeout_s=settings.HTTP_TIMEOUT_S
            ),
            window_days=settings.OPENSKY_WINDOW_DAYS,
            request_delay_s=settings.OPENSKY_REQUEST_DELAY_S,
        )
        faa_nas = FaaNasProvider(http, timeout_s=settings.HTTP_TIMEOUT_S)
        
        live_providers: list[AviationProvider] = []
        if settings.BTS_ON_TIME_ENABLED:
            live_providers.append(BtsOnTimeProvider(http, timeout_s=settings.HTTP_TIMEOUT_S))
        live_providers.append(FaaAcaisFileProvider())
        live_providers.append(FaaAtadsFileProvider())
        
        import asyncio
        bts_t100 = await asyncio.to_thread(BtsT100FileProvider)
        live_providers.append(bts_t100)
        app.state.bts_t100 = bts_t100

        if settings.OPENSKY_TRAFFIC_ENABLED and not bts_t100.is_loaded():
            live_providers.append(opensky)
        
        composite = CompositeProvider(live=live_providers, sample=sample)
        context_providers: list[ContextProvider] = [faa_nas]
        if settings.WEATHER_ENABLED:
            context_providers.append(AviationWeatherProvider(http, coords, timeout_s=settings.HTTP_TIMEOUT_S))
        context_providers.append(OpenFlightsRoutesProvider())
        
        context_composite = ContextComposite(providers=context_providers)
        analysis = AnalysisService(
            composite=composite, 
            context_composite=context_composite, 
            catalog=catalog,
            bts_provider=bts_t100
        )

        app.state.coords = coords
        app.state.catalog = catalog
        app.state.analysis = analysis
        app.state.analysis_service = analysis

        if settings.UNIVERSE_WARM_ON_STARTUP:
            import asyncio
            import logging
            logger = logging.getLogger(__name__)
            async def _warm():
                try:
                    await analysis.universe()
                    logger.info("Universe warmed successfully on startup")
                except Exception as e:
                    logger.warning("Failed to warm universe on startup: %s", e)
            asyncio.create_task(_warm())

        sessions = SessionStore()
        llm = OpenAILLMClient(http=http)
        tts_service = TTSService(http)
        app.state.sessions = sessions
        app.state.orchestrator = Orchestrator(
            llm=llm, analysis=analysis, sessions=sessions,
        )
        app.state.tts_service = tts_service

        yield


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(title="AirportIQ API", lifespan=lifespan)

register_exception_handlers(app)

app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(airports.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(tts.router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "AirportIQ API"}
