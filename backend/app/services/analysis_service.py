from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Sequence
from typing import NewType, Any

from pydantic import BaseModel, Field

from app.analytics.congestion import calculate_congestion_score, calculate_delay_pressure
from app.analytics.capacity import calculate_capacity_pressure
from app.analytics.demand import calculate_passenger_growth
from app.analytics.opportunity import calculate_unmet_demand_index
from app.core.config import settings
from app.models.airport import IATA, Airport, normalize_iata
from app.models.metrics import (
    Absent,
    AirportDossier,
    AirportMetrics,
    DatumFloat,
    Live,
    Present,
    fold_origins,
)
from app.models.context import AirportContext
from app.models.score import AirportScore, PeerStats, ProviderFailure
from app.providers.base import merge_outcomes, merge_context_outcomes
from app.providers.composite import CompositeProvider, ContextComposite
from app.scoring.expansion_score import score_dossier
from app.scoring.normalization import normalize_min_max
from app.services.bts_ontime_service import BtsOnTimeService

logger = logging.getLogger(__name__)

GrowthPct = NewType("GrowthPct", float)

_PEER_BOUND_FIELDS: tuple[str, ...] = (
    "passenger_volume",
    "annual_operations",
    "demand_growth",
    "pax_per_operation",
)


class SimulationResult(BaseModel, frozen=True):
    airport_code: str
    baseline_score: AirportScore
    simulated_score: AirportScore
    growth_adjustment: float
    delta_opportunity: float | None


class Universe(BaseModel, frozen=True, arbitrary_types_allowed=True):
    snapshot_at: str
    dossiers: dict[str, AirportDossier]
    scores: dict[str, AirportScore]
    peers: PeerStats
    failures: list[ProviderFailure]
    ontime_service: BtsOnTimeService | None = Field(default=None, exclude=True)
    catalog: Any | None = Field(default=None, exclude=True)

    def simulate(self, code: IATA, pct: GrowthPct) -> SimulationResult:
        dossier = self.dossiers.get(code)
        if dossier is None:
            raise ValueError(f"Airport {code} not in universe")

        baseline = self.scores[code]

        if isinstance(dossier.passenger_growth, Present):
            adjusted_growth = dossier.passenger_growth.value + pct
            new_origin = fold_origins(
                dossier.passenger_growth.origin,
                method=f"simulated_growth(+{pct})",
            )
            new_growth: DatumFloat = Present[float](value=adjusted_growth, origin=new_origin)
        else:
            new_growth = dossier.passenger_growth

        adjusted = AirportDossier(
            airport=dossier.airport,
            metrics=dossier.metrics,
            passenger_growth=new_growth,
            long_haul_pct=dossier.long_haul_pct,
            unmet_demand_index=dossier.unmet_demand_index,
            context=dossier.context,
            snapshot_at=dossier.snapshot_at,
        )
        simulated = score_dossier(adjusted, self.peers)

        delta: float | None = None
        if isinstance(baseline.opportunity_score, Present) and isinstance(
            simulated.opportunity_score, Present
        ):
            delta = round(
                simulated.opportunity_score.value - baseline.opportunity_score.value, 1
            )

        return SimulationResult(
            airport_code=code,
            baseline_score=baseline,
            simulated_score=simulated,
            growth_adjustment=pct,
            delta_opportunity=delta,
        )


def _build_peer_stats(
    metrics_map: dict[str, AirportMetrics],
) -> PeerStats:
    bounds: dict[str, tuple[float, float]] = {}

    pax_vals = [
        float(m.passenger_volume.value)
        for m in metrics_map.values()
        if isinstance(m.passenger_volume, Present)
    ]
    if pax_vals:
        bounds["passenger_volume"] = (min(pax_vals), max(pax_vals))

    ops_vals = [
        float(m.annual_operations.value)
        for m in metrics_map.values()
        if isinstance(m.annual_operations, Present)
    ]
    if ops_vals:
        bounds["annual_operations"] = (min(ops_vals), max(ops_vals))

    pax_per_op_vals: list[float] = []
    for m in metrics_map.values():
        if isinstance(m.passenger_volume, Present) and isinstance(
            m.annual_operations, Present
        ):
            if m.annual_operations.value > 0:
                pax_per_op_vals.append(
                    m.passenger_volume.value / m.annual_operations.value
                )
    if pax_per_op_vals:
        bounds["pax_per_operation"] = (min(pax_per_op_vals), max(pax_per_op_vals))

    return PeerStats(
        bounds=bounds,
        universe_codes=tuple(metrics_map.keys()),
    )


def _build_dossier(
    code: str,
    metrics: AirportMetrics,
    context: AirportContext,
    peers: PeerStats,
    airport_lookup: dict[str, object],
    segment_file: object | None,
    snapshot_at: str,
) -> AirportDossier | None:
    from app.services.airport_service import AirportCatalog
    from app.providers.bts_t100_segment_file import BtsT100SegmentFileProvider
    from app.analytics.long_haul import summarize_long_haul, LongHaulSummary

    catalog: AirportCatalog = airport_lookup  # type: ignore[assignment]
    airport = catalog.get(code)  # type: ignore[arg-type]
    if airport is None:
        try:
            iata = normalize_iata(code)
        except ValueError:
            logger.warning("Invalid airport code %s, skipping dossier", code)
            return None
        airport = Airport(
            iata_code=iata,
            icao_code="",
            name=iata,
            city="",
            state="",
            latitude=0.0,
            longitude=0.0,
        )

    growth = calculate_passenger_growth(
        metrics.passenger_volume,
        metrics.previous_passenger_volume,
    )

    lh_pct: DatumFloat
    lh_summary: LongHaulSummary | None = None
    
    if segment_file is not None:
        seg_provider: BtsT100SegmentFileProvider = segment_file  # type: ignore[assignment]
        if seg_provider.is_loaded:
            rows = seg_provider.rows_for(code)
            if rows:
                lh_summary = summarize_long_haul(rows)
                if lh_summary is not None:
                    origin = Live(
                        source="BTS T-100 Segment (bulk file)",
                        period=seg_provider.period_label or "unknown",
                        fetched_at=seg_provider.retrieved_at or snapshot_at,
                    )
                    lh_pct = Present[float](value=lh_summary.pct, origin=origin)
                else:
                    lh_pct = Absent(
                        reason="NO_DEPARTURES",
                        detail="airport present in segment file but no valid departures found",
                        attempted=("BTS T-100 Segment (bulk file)",),
                    )
            else:
                lh_pct = Absent(
                    reason="NOT_PUBLISHED",
                    detail="airport not present in segment file",
                    attempted=("BTS T-100 Segment (bulk file)",),
                )
        else:
            lh_pct = Absent(
                reason="NOT_PUBLISHED",
                detail="BTS T-100 Segment file not configured or failed to load",
                attempted=("BTS T-100 Segment (bulk file)",),
            )
    else:
        lh_pct = Absent(
            reason="NOT_PUBLISHED",
            detail="BTS T-100 Segment file not configured",
            attempted=("BTS T-100 Segment (bulk file)",),
        )

    delay = calculate_delay_pressure(
        metrics.delayed_flights_pct,
        metrics.average_delay_minutes,
    )
    congestion = calculate_congestion_score(metrics, peers)
    unmet = calculate_unmet_demand_index(growth, delay, congestion, peers)

    enriched_metrics = metrics.model_copy(update={"airport_name": airport.name})

    return AirportDossier(
        airport=airport,
        metrics=enriched_metrics,
        passenger_growth=growth,
        long_haul_pct=lh_pct,
        long_haul_summary=lh_summary,
        unmet_demand_index=unmet,
        context=context,
        snapshot_at=snapshot_at,
    )


class AnalysisService:
    def __init__(
        self,
        composite: CompositeProvider,
        context_composite: ContextComposite,
        catalog: object,
        segment_file: object | None = None,
        ontime_service: BtsOnTimeService | None = None,
    ) -> None:
        self._composite = composite
        self._context_composite = context_composite
        self._catalog = catalog
        self._segment_file = segment_file
        self._ontime_service = ontime_service
        self._lock = asyncio.Lock()
        self._cached: Universe | None = None
        self._cached_at: float = 0.0

    async def universe(self, codes: Sequence[str] | None = None, regions: Sequence[str] | None = None) -> Universe:
        requested: list[str] = []
        if codes:
            for raw in codes:
                try:
                    requested.append(normalize_iata(raw))
                except ValueError:
                    logger.warning("Skipping invalid IATA in universe request: %s", raw)

        region_failures: list[ProviderFailure] = []
        if regions:
            from app.services.airport_service import AirportCatalog
            catalog: AirportCatalog = self._catalog  # type: ignore[assignment]
            for region in regions:
                region_codes, failures = await catalog.region_codes(region)
                requested.extend(region_codes)
                region_failures.extend(failures)
        
        # Deduplicate requested codes
        requested = list(dict.fromkeys(requested))

        now = time.monotonic()
        ttl_ok = (
            self._cached is not None
            and (now - self._cached_at) < settings.UNIVERSE_TTL_SECONDS
        )

        if not requested:
            if ttl_ok and self._cached is not None:
                if region_failures:
                    return self._cached.model_copy(update={"failures": self._cached.failures + region_failures})
                return self._cached
            
            empty = self._empty_universe()
            if region_failures:
                empty = empty.model_copy(update={"failures": region_failures})
            return empty

        async with self._lock:
            now = time.monotonic()
            ttl_ok = (
                self._cached is not None
                and (now - self._cached_at) < settings.UNIVERSE_TTL_SECONDS
            )
            existing = set(self._cached.dossiers.keys()) if self._cached else set()
            merged = list(dict.fromkeys([*existing, *requested]))

            if ttl_ok and self._cached is not None and set(merged) == existing:
                if region_failures:
                    return self._cached.model_copy(update={"failures": self._cached.failures + region_failures})
                return self._cached

            universe = await self._build(merged)
            if region_failures:
                universe = universe.model_copy(update={"failures": universe.failures + region_failures})

            if universe.dossiers:
                self._cached = universe
                self._cached_at = time.monotonic()
            return universe

    @staticmethod
    def _empty_universe() -> Universe:
        return Universe(
            snapshot_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            dossiers={},
            scores={},
            peers=PeerStats(bounds={}, universe_codes=()),
            failures=[],
            catalog=None,
        )

    async def _build(self, codes: Sequence[str]) -> Universe:
        from app.services.airport_service import AirportCatalog

        catalog: AirportCatalog = self._catalog  # type: ignore[assignment]

        catalog_failures = await catalog.refresh(codes)  # type: ignore[arg-type]

        outcomes = await self._composite.fetch(codes)  # type: ignore[arg-type]
        metrics_map = merge_outcomes(codes, outcomes)

        context_outcomes = await self._context_composite.fetch(codes)  # type: ignore[arg-type]
        context_map = merge_context_outcomes(codes, context_outcomes)

        all_failures: list[ProviderFailure] = list(catalog_failures)
        for o in outcomes:
            all_failures.extend(o.failures)
        for o in context_outcomes:
            all_failures.extend(o.failures)

        peers = _build_peer_stats(metrics_map)

        growth_vals: list[float] = []
        for m in metrics_map.values():
            g = calculate_passenger_growth(m.passenger_volume, m.previous_passenger_volume)
            if isinstance(g, Present):
                growth_vals.append(g.value)
        if growth_vals:
            peers = PeerStats(
                bounds={**peers.bounds, "demand_growth": (min(growth_vals), max(growth_vals))},
                universe_codes=peers.universe_codes,
            )

        snapshot_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        dossiers: dict[str, AirportDossier] = {}
        for code, metrics in metrics_map.items():
            ctx = context_map.get(code, AirportContext())
            
            # Merge metrics warnings into context warnings
            if metrics.warnings:
                ctx = ctx.model_copy(update={"warnings": ctx.warnings + metrics.warnings})
                
            # Set long_haul_departures live status
            if isinstance(metrics.long_haul_flights, Present) and isinstance(metrics.total_departures, Present):
                ctx = ctx.model_copy(update={"long_haul_departures": "live"})
            else:
                ctx = ctx.model_copy(update={"long_haul_departures": "unavailable"})
                
            d = _build_dossier(code, metrics, ctx, peers, self._catalog, self._segment_file, snapshot_at)  # type: ignore[arg-type]
            if d is not None:
                dossiers[code] = d

        scores: dict[str, AirportScore] = {}
        for code, dossier in dossiers.items():
            scores[code] = score_dossier(dossier, peers)

        return Universe(
            snapshot_at=snapshot_at,
            dossiers=dossiers,
            scores=scores,
            peers=peers,
            failures=all_failures,
            ontime_service=self._ontime_service,
            catalog=catalog,
        )
