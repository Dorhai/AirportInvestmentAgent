from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Sequence
from typing import NewType, Any

from pydantic import BaseModel

from app.analytics.congestion import calculate_congestion_score, calculate_delay_pressure
from app.analytics.capacity import calculate_capacity_pressure
from app.analytics.demand import calculate_passenger_growth
from app.analytics.long_haul import calculate_long_haul_percentage
from app.analytics.opportunity import calculate_unmet_demand_index
from app.core.config import settings
from app.models.airport import IATA
from app.models.metrics import (
    Absent,
    AirportDossier,
    AirportMetrics,
    DatumFloat,
    Present,
    fold_origins,
)
from app.models.context import AirportContext
from app.models.score import AirportScore, PeerStats, ProviderFailure
from app.providers.base import merge_outcomes, merge_context_outcomes
from app.providers.fallback import CompositeProvider, ContextComposite
from app.scoring.expansion_score import score_dossier
from app.scoring.normalization import normalize_min_max

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


class Universe(BaseModel, frozen=True):
    snapshot_at: str
    dossiers: dict[str, AirportDossier]
    scores: dict[str, AirportScore]
    peers: PeerStats
    failures: list[ProviderFailure]
    long_haul_reports: dict[str, dict[str, Any]] = {}

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
    snapshot_at: str,
) -> AirportDossier | None:
    from app.services.airport_service import AirportCatalog

    catalog: AirportCatalog = airport_lookup  # type: ignore[assignment]
    airport = catalog.get(code)  # type: ignore[arg-type]
    if airport is None:
        logger.warning("No airport record for %s, skipping dossier", code)
        return None

    growth = calculate_passenger_growth(
        metrics.passenger_volume,
        metrics.previous_passenger_volume,
    )

    lh_pct: DatumFloat
    if isinstance(metrics.long_haul_flights, Present) and isinstance(
        metrics.total_departures, Present
    ):
        if metrics.total_departures.value > 0:
            pct = (metrics.long_haul_flights.value / metrics.total_departures.value) * 100.0
            origin = fold_origins(
                metrics.long_haul_flights.origin,
                metrics.total_departures.origin,
                method="long_haul_pct",
            )
            lh_pct = Present[float](value=pct, origin=origin)
        else:
            lh_pct = Absent(
                reason="OUT_OF_SCOPE",
                detail="total departures is zero",
                attempted=(),
            )
    else:
        attempted: list[str] = []
        if isinstance(metrics.long_haul_flights, Absent):
            attempted.extend(metrics.long_haul_flights.attempted)
        if isinstance(metrics.total_departures, Absent):
            attempted.extend(metrics.total_departures.attempted)
        lh_pct = Absent(
            reason="NOT_PUBLISHED",
            detail="long-haul or departure data absent",
            attempted=tuple(dict.fromkeys(attempted)),
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
        bts_provider: Any | None = None,
    ) -> None:
        self._composite = composite
        self._context_composite = context_composite
        self._catalog = catalog
        self._bts_provider = bts_provider
        self._lock = asyncio.Lock()
        self._cached: Universe | None = None
        self._cached_at: float = 0.0

    async def universe(self) -> Universe:
        now = time.monotonic()
        if (
            self._cached is not None
            and (now - self._cached_at) < settings.UNIVERSE_TTL_SECONDS
        ):
            return self._cached

        async with self._lock:
            now = time.monotonic()
            if (
                self._cached is not None
                and (now - self._cached_at) < settings.UNIVERSE_TTL_SECONDS
            ):
                return self._cached

            universe = await self._build()
            self._cached = universe
            self._cached_at = time.monotonic()
            return universe

    async def _build(self) -> Universe:
        from app.services.airport_service import AirportCatalog

        catalog: AirportCatalog = self._catalog  # type: ignore[assignment]
        codes: Sequence[IATA] = catalog.codes  # type: ignore[assignment]

        outcomes = await self._composite.fetch(codes)  # type: ignore[arg-type]
        metrics_map = merge_outcomes(codes, outcomes)

        context_outcomes = await self._context_composite.fetch(codes)  # type: ignore[arg-type]
        context_map = merge_context_outcomes(codes, context_outcomes)

        all_failures: list[ProviderFailure] = []
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
                
            d = _build_dossier(code, metrics, ctx, peers, self._catalog, snapshot_at)  # type: ignore[arg-type]
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
            long_haul_reports={},
        )

    def long_haul_report(
        self,
        code: str,
        threshold_miles: float = 3000.0,
        start_year: int | None = None,
        end_year: int | None = None,
        passenger_only: bool = False,
    ) -> dict[str, Any]:
        """Generate a full long-haul report directly from the BTS T-100 provider."""
        if not self._bts_provider:
            return {
                "airport": code,
                "metric": "long_haul_departure_percentage",
                "threshold_miles": threshold_miles,
                "start_year": start_year,
                "end_year": end_year,
                "total_departures": 0.0,
                "long_haul_departures": 0.0,
                "percentage": None,
                "passenger_only": passenger_only,
                "passenger_only_filter_available": False,
                "unique_destinations": 0,
                "long_haul_destinations": 0,
                "average_distance_miles": 0.0,
                "max_distance_miles": 0.0,
                "top_long_haul_routes": [],
                "source": "BTS T-100 Segment",
                "calculation": "long_haul_departures / total_departures * 100",
                "metadata": {
                    "source": "BTS T-100 Segment",
                    "latest_year": None,
                    "latest_month": None,
                    "retrieved_at": None,
                }
            }
            
        return self._bts_provider.get_report(
            airport=code,
            threshold_miles=threshold_miles,
            start_year=start_year,
            end_year=end_year,
            passenger_only=passenger_only,
        )
