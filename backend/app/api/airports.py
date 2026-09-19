"""Airport metric, scoring, comparison, and ranking HTTP endpoints."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Request

from app.core.exceptions import UnknownAirportError
from app.models.airport import IATA, REGIONS, SUPPORTED
from app.models.chat import ComparisonResult, ComparisonRow, RankingResult, LongHaulResult
from app.models.context import AirportContext
from app.models.metrics import AirportMetrics, Present
from app.models.score import AirportScore, ScoringMethodology
from app.scoring.expansion_score import rank
from app.services.analysis_service import AnalysisService

router = APIRouter()


def _get_analysis(request: Request) -> AnalysisService:
    return request.app.state.analysis_service


def _validate_code(code: str) -> IATA:
    upper = code.upper()
    if upper not in SUPPORTED:
        raise UnknownAirportError(upper)
    return upper  # type: ignore[return-value]


# ------------------------------------------------------------------
# GET /api/airports/{code}
# ------------------------------------------------------------------


class AirportMetricsResponse(BaseModel):
    metrics: AirportMetrics
    context: AirportContext | None = None

@router.get("/airports/{code}", response_model=AirportMetricsResponse)
async def get_airport_metrics(code: str, request: Request) -> AirportMetricsResponse:
    iata = _validate_code(code)
    analysis = _get_analysis(request)
    universe = await analysis.universe()

    dossier = universe.dossiers.get(iata)
    if dossier is None:
        raise UnknownAirportError(iata)
    return AirportMetricsResponse(metrics=dossier.metrics, context=dossier.context)


# ------------------------------------------------------------------
# GET /api/airports/{code}/score
# ------------------------------------------------------------------


@router.get("/airports/{code}/score", response_model=AirportScore)
async def get_airport_score(code: str, request: Request) -> AirportScore:
    iata = _validate_code(code)
    analysis = _get_analysis(request)
    universe = await analysis.universe()

    score = universe.scores.get(iata)
    if score is None:
        raise UnknownAirportError(iata)
    return score


# ------------------------------------------------------------------
# GET /api/airports/{code}/long-haul
# ------------------------------------------------------------------

@router.get("/airports/{code}/long-haul")
async def get_airport_long_haul(
    code: str, 
    request: Request,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    threshold_miles: float = 3000.0,
    passenger_only: bool = False,
) -> dict:
    iata = _validate_code(code)
    analysis = _get_analysis(request)
    
    if year is not None:
        start_year = year
        end_year = year
        
    return analysis.long_haul_report(
        code=iata,
        threshold_miles=threshold_miles,
        start_year=start_year,
        end_year=end_year,
        passenger_only=passenger_only,
    )


# ------------------------------------------------------------------
# POST /api/airports/compare
# ------------------------------------------------------------------


class CompareRequest(BaseModel):
    airport_codes: list[IATA]


def _highest_by_component(
    rows: list[ComparisonRow], field: str,
) -> str | None:
    best_code: str | None = None
    best_val: float = -1.0
    for row in rows:
        datum = getattr(row.score, field)
        if isinstance(datum, Present) and datum.value > best_val:
            best_val = datum.value
            best_code = row.airport_code
    return best_code


def _period_warning(rows: list[ComparisonRow]) -> str | None:
    periods: set[str] = set()
    for row in rows:
        dp = row.metrics.data_period
        if dp:
            periods.add(dp)
    if len(periods) > 1:
        return "Airports cover different data periods — compare with caution."
    return None


@router.post("/airports/compare", response_model=ComparisonResult)
async def compare_airports(
    body: CompareRequest, request: Request,
) -> ComparisonResult:
    analysis = _get_analysis(request)
    universe = await analysis.universe()

    rows: list[ComparisonRow] = []
    for code in body.airport_codes:
        iata = _validate_code(code)
        dossier = universe.dossiers.get(iata)
        score = universe.scores.get(iata)
        if dossier is None or score is None:
            raise UnknownAirportError(iata)
        rows.append(
            ComparisonRow(
                airport_code=iata,
                score=score,
                metrics=dossier.metrics,
            )
        )

    return ComparisonResult(
        airports=[r.airport_code for r in rows],
        snapshot_at=universe.snapshot_at,
        rows=rows,
        highest_congestion=_highest_by_component(rows, "congestion_score"),
        highest_opportunity_score=_highest_by_component(rows, "opportunity_score"),
        period_warning=_period_warning(rows),
    )


# ------------------------------------------------------------------
# GET /api/scoring/methodology
# ------------------------------------------------------------------

@router.get("/scoring/methodology", response_model=ScoringMethodology)
async def get_scoring_methodology() -> ScoringMethodology:
    from app.scoring.expansion_score import SCORING_WEIGHTS
    return ScoringMethodology(
        weights=SCORING_WEIGHTS,
        component_labels={
            "demand_growth": "Demand growth",
            "congestion": "Congestion",
            "delay_pressure": "Delay pressure",
            "capacity_pressure": "Capacity pressure",
        },
        rules=[
            "Scores are normalized against peer bounds (0–100).",
            "Missing components redistribute their weight proportionally.",
            "Long-haul flights are >3,000 statute miles.",
            "Opportunity is a weighted sum of demand, congestion, delay, and capacity."
        ]
    )

# ------------------------------------------------------------------
# GET /api/regions/{region}/ranking
# ------------------------------------------------------------------


@router.get("/regions/{region}/ranking", response_model=RankingResult)
async def get_region_ranking(region: str, request: Request) -> RankingResult:
    region_lower = region.lower()
    states = REGIONS.get(region_lower)
    if states is None:
        valid = ", ".join(sorted(REGIONS))
        raise UnknownAirportError(
            f"{region} is not a recognized region. Valid: {valid}"
        )

    analysis = _get_analysis(request)
    universe = await analysis.universe()

    region_scores: list[AirportScore] = []
    for code, dossier in universe.dossiers.items():
        if dossier.airport.state in states:
            score = universe.scores.get(code)
            if score is not None:
                region_scores.append(score)

    ranked = rank(region_scores)
    codes = [s.airport_code for s in ranked]

    return RankingResult(
        airports=codes,
        snapshot_at=universe.snapshot_at,
        ranked=ranked,
        region=region_lower,
        peer_note=f"Ranked {len(ranked)} airports in {region_lower}: {', '.join(codes)}"
        if ranked
        else f"No airports found in {region_lower}.",
    )
