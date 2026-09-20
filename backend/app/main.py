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
from app.providers.faa_nas import FaaNasProvider
from app.providers.aviation_weather import AviationWeatherProvider
from app.providers.bts_t100_origin import BtsT100OriginProvider
from app.providers.bts_ontime_bulk import BtsOnTimeBulkProvider
from app.providers.bts_national import BtsNationalTrafficProvider
from app.providers.bts_t100_segment_file import BtsT100SegmentFileProvider
from app.services.bts_ontime_service import BtsOnTimeService
from app.providers.ntad import NtadFacilitiesProvider
from app.providers.composite import CompositeProvider, ContextComposite
from app.services.airport_service import AirportCatalog
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
    async with httpx.AsyncClient(headers={"User-Agent": settings.HTTP_USER_AGENT}) as http:
        ntad = NtadFacilitiesProvider(http, timeout_s=settings.BULK_HTTP_TIMEOUT_S)
        catalog = AirportCatalog(source=ntad)
        
        t100 = BtsT100OriginProvider(
            http, 
            timeout_s=settings.BULK_HTTP_TIMEOUT_S,
            app_token=settings.BTS_APP_ID, 
            trailing_months=settings.BTS_TRAILING_MONTHS
        )
        
        ontime_service = None
        on_time_bulk = None
        ontime_source = settings.BTS_ONTIME_CSV_PATH or settings.BTS_ONTIME_DATA_DIR
        if ontime_source:
            ontime_service = BtsOnTimeService(ontime_source)
            import asyncio
            await asyncio.to_thread(ontime_service.load_sync)
            on_time_bulk = BtsOnTimeBulkProvider(ontime_service, trailing_months=settings.BTS_TRAILING_MONTHS)
        
        providers = [t100]
        if on_time_bulk:
            providers.append(on_time_bulk)
            
        composite = CompositeProvider(providers=providers)
        
        context_providers = [
            FaaNasProvider(http, timeout_s=settings.HTTP_TIMEOUT_S),
            BtsNationalTrafficProvider(
                http, 
                timeout_s=settings.BULK_HTTP_TIMEOUT_S, 
                app_token=settings.BTS_APP_ID,
                trailing_months=settings.BTS_TRAILING_MONTHS
            ),
            ntad,
        ]
        
        if settings.WEATHER_ENABLED:
            context_providers.append(
                AviationWeatherProvider(http, timeout_s=settings.HTTP_TIMEOUT_S, catalog=catalog)
            )
            
        context_composite = ContextComposite(providers=context_providers)
        
        segment_file = None
        if settings.BTS_T100_SEGMENT_PATH:
            segment_file = BtsT100SegmentFileProvider(settings.BTS_T100_SEGMENT_PATH)
            import asyncio
            await asyncio.to_thread(segment_file.load_sync)
            app.state.segment_file = segment_file
        
        analysis = AnalysisService(
            composite=composite, 
            context_composite=context_composite, 
            catalog=catalog,
            segment_file=segment_file,
            ontime_service=ontime_service,
        )

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
