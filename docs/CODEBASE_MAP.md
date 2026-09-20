# AirportIQ Codebase Map

## Purpose

This file is a navigation map for developers and coding agents.

Use it before multi-file changes.

For product documentation see [README.md](../README.md) and [PRODUCT.md](PRODUCT.md).

For architectural reasoning and tradeoffs see [architecture.md](architecture.md).

---

# System Flow

User
→ React Chat UI
→ SSE /api/chat
→ Agent Orchestrator (Phases: tool_select, tools, compose, done)
→ Agent Tool
→ Analysis Service
→ Analytics / Scoring
→ Data Provider
→ Structured Result (meta event)
→ LLM Explanation (delta events)
→ React

---

# Backend

## API

backend/app/api/

### chat.py

Owns:

POST /api/chat

Responsibilities:

- request validation
- invoke agent orchestrator
- return ChatResponse

Must NOT contain:

- scoring formulas
- aviation API logic

### airports.py

Owns:

GET /api/airports/{code}
GET /api/airports/{code}/score
POST /api/airports/compare
GET /api/regions/{region}/ranking

Responsibilities:

- validate airport codes and region names
- delegate to AnalysisService via request.app.state.analysis_service
- return AirportMetrics, AirportScore, ComparisonResult, RankingResult

Must NOT contain:

- scoring formulas
- provider logic

### health.py

Owns:

service health endpoint.

### tts.py

Owns:

GET /api/tts/status
POST /api/tts

Responsibilities:

- delegates text-to-speech to TTSService
- returns audio stream or capability status

Must NOT contain:

- agent or LLM logic

---

# Agent

backend/app/agent/

### orchestrator.py

Primary entry point for conversational AI.

Owns:

- Orchestrator.turn(ChatRequest) -> ChatResponse
- conversation orchestration: input screen → tool select → execute → respond → output screen
- TurnAudit log entry
- concurrent tool execution via asyncio

Does NOT own calculations.

### session.py

Conversation session state with TTL eviction.

Owns:

- Exchange (user_message, reply, evidence)
- Session (conversation_id, deque[Exchange] maxlen 6, last_seen)
  - last_evidence, recent_airports properties
  - history_messages() for LLM context
- SessionStore — in-memory TTL cache with per-conversation asyncio.Lock
  - get_or_create, append, evict, lock_for

### tools.py

Defines approved LLM tools.

Thin projections over the Universe snapshot.

Owns:

- CodeArgs, CodesArgs, RegionArgs, SimArgs — tool argument models
- @tool decorator and TOOLS registry
- execute(ToolCall, Universe) -> ToolResult — validates args, dispatches, never raises
- tool_schemas() — OpenAI-compatible function schemas
- 12 tools: get_airport_metrics, get_airport_score, compare_airports, rank_airports, rank_region, get_long_haul_percentage, get_unmet_demand, simulate_airport_growth, explain_congestion, explain_unmet_demand, explain_capacity_pressure, rank_by_metric

### airport_scope.py

Owns:

- `AirportScope` and `resolve_airport_scope`
- Deterministic resolution of which airports a conversational turn binds to (mentions, referents, last turn, ranking).
- Replaces ad-hoc frame union logic to prevent mixing unrelated airports across turns.

### follow_up.py

Deterministic fallback tool planner when the LLM selects no tools (frame-based and first-turn via intent_routing).

### intent_routing.py

First-turn tool selection from message keywords and region/airport mentions.

### capability.py

Decline hints injected into turn context for out-of-scope question patterns.

### tool_reconcile.py

Rewrites LLM tool choices when a compare question incorrectly selected explain-only tools.

### llm.py

LLM client abstraction.

Owns:

- ToolCall domain object
- TurnContext (system prompt, history, facts, hints, injection note, user message)
- LLMClient protocol (choose_tools, respond)
- OpenAILLMClient — httpx-based OpenAI chat completions with tool calling
- ScriptedLLMClient — deterministic test double

### prompts.py

System and agent prompts.

Owns:

- SYSTEM_PROMPT — enforces Guardrails 1, 2, 5, 9, 12
- render_facts_digest(evidence) — read-only text block for LLM context

### guardrails.py

Agent-specific input/output guardrails.

Owns:

- resolve_mentions(text) -> Resolved | Ambiguous — maps text to known IATAs/aliases
- screen_input(message, voice_confidence) -> Confirm | Proceed — pre-turn gate
- resolve_referents(message, recent_airports) -> list[str] | None — anaphoric resolution
- scan_injection(text) -> str — prompt-injection detection
- verify_numbers(prose, evidence) -> list[str] — hallucination check (advisory)
- scrub_guarantees(prose) -> str — appends disclaimer for ROI/guarantee language
- screen_output(prose, evidence) -> (str, list[str]) — post-LLM output gate

---

# Analytics

backend/app/analytics/

### demand.py

Passenger growth and demand calculations.

### congestion.py

Congestion calculations.

### drivers.py

Deterministic score driver breakdowns (congestion, unmet demand, capacity pressure) for explain_* tools.

### capacity.py

Capacity-pressure proxy.

### t100.py

Pure analytics functions for BTS T-100 trailing window aggregation.

### long_haul.py

Pure analytics functions for BTS T-100 Segment bulk file summarization.

### opportunity.py

Unmet-demand analytical components if applicable.

All analytics functions should be deterministic.

---

# Scoring

backend/app/scoring/

### normalization.py

Canonical normalization functions.

### expansion_score.py

Canonical Expansion Opportunity Score.

This is the ONLY authoritative implementation of final score weighting.

Current weights:

Demand Growth: 30%
Congestion: 30%
Delay Pressure: 20%
Capacity Pressure: 20%

The frontend and LLM must never duplicate this formula.

---

# Providers

backend/app/providers/

### base.py

Provider interface.

Owns:

- ProviderOutcome model (fields + failures)
- AviationProvider protocol (name, async fetch)
- ContextOutcome model (fields + failures)
- ContextProvider protocol (name, async fetch)
- MetricField literal type
- merge_outcomes() — combines multiple ProviderOutcomes into one AirportMetrics per code
- merge_context_outcomes() — combines multiple ContextOutcomes into one AirportContext per code

### aviation_weather.py

Live aviation weather provider.

Owns:

- AviationWeatherProvider — fetches METAR data from NOAA AWC, batched by ICAO.

### composite.py

Live-API-only data merge.

Owns:

- CompositeProvider — runs live providers concurrently, returns ordered outcomes for merge
- ContextComposite — runs context providers concurrently, returns ordered outcomes for merge

### bts_t100_origin.py

BTS T-100 Segment by Origin provider.

Owns:

- BtsT100OriginProvider — fetches live aggregated monthly data via Socrata API.

### bts_t100_segment_file.py

BTS T-100 Segment bulk file provider.

Owns:

- BtsT100SegmentFileProvider — parses and indexes the bulk CSV/ZIP file for accurate long-haul metrics.

### bts_ontime_bulk.py

BTS On-Time Performance bulk CSV provider.

Owns:

- BtsOnTimeBulkProvider — adapts the BtsOnTimeService to provide delay percentages and average delay minutes for scoring.

### bts_national.py

BTS National Traffic provider.

Owns:

- BtsNationalTrafficProvider — fetches live national totals from Socrata (jqx4-4iha).

### ntad.py

NTAD Aviation Facilities provider.

Owns:

- NtadFacilitiesProvider — fetches airport catalog and facility context from ArcGIS.

### faa_nas.py

FAA NAS delay status provider.

Owns:

- FaaNasProvider — fetches FAA NAS delay status XML, returns DelayProgram data (as ContextProvider)
- DelayProgram model

Providers retrieve and normalize data.

They do NOT score airports.

---

# Services

backend/app/services/

### airport_service.py

Coordinates airport data retrieval.

Owns:

- AirportCatalog — refreshed from NTAD, returns full Airport model by IATA code

### analysis_service.py

Coordinates analytics and scoring.

Owns:

- Universe (frozen) — snapshot_at, dossiers, scores, peers, failures; simulate(code, pct)
- SimulationResult model
- GrowthPct type alias
- AnalysisService — TTL-cached universe builder using CompositeProvider + merge_outcomes + score_dossier

### tts_service.py

Coordinates text-to-speech generation.

Owns:

- TTSService — contacts OpenAI audio/speech API, returns audio bytes

Services bridge providers with deterministic analysis.

---

# Models

backend/app/models/

Canonical Pydantic domain and API models.

Do not create duplicate models in unrelated modules.

### chat.py

Owns:

- ResultBase, MetricsResult, ScoreResult, ComparisonResult, RankingResult, LongHaulResult, UnmetDemandResult, SimulationResult, ToolRejection — tagged result variants
- ToolResult — discriminated union of all result variants
- ComparisonRow
- ConfirmOption, Confirmation
- ChatResponse — final agent response model with assemble() factory

### request.py

Owns:

- ChatRequest — inbound chat model (message, conversation_id, voice_confidence)

### core/exceptions.py

Owns:

AirportIQError, UnknownAirportError, ProviderError

Custom exception hierarchy and FastAPI exception handlers.

Pydantic ValidationError formatter for friendly IATA validation messages.

---

# Frontend

frontend/src/

## chat/

Conversation UI.

Important files:

ChatContainer.tsx — renders turn list, delegates each turn to ChatMessage via presentResponse.

ChatInput.tsx — text input and submit button.

ChatMessage.tsx — maps Block discriminated union to airport components.

VoiceButton.tsx

## common/

Reusable presentational building blocks used by airport components.

MetricBar.tsx — horizontal percentage bar with label.
ConfidenceBadge.tsx — HIGH/MEDIUM/LOW color-coded badge.
SourceBadge.tsx — small pill for a single data source.
DataFreshnessBadge.tsx — shows "Sample Data" / "Cached / Mixed Data" when freshness is not live.
Collapsible.tsx — accessible expand/collapse section (uses lucide ChevronDown).

## airport/

Structured analytical UI for chat evidence blocks.

AirportScoreCard.tsx — full score card with MetricBars, badges, and collapsible metadata.
AirportComparison.tsx — comparison table highlighting top opportunity and congestion.
RankingTable.tsx — numbered ranked list of AirportScores.
SimulationCard.tsx — side-by-side baseline vs simulated scores with delta.
KpiCard.tsx — single KPI display for long-haul % or unmet demand.
ConfirmationPrompt.tsx — disambiguation prompt with candidate buttons.
WarningsList.tsx — warning list with AlertTriangle icons.

## layout/

AppLayout.tsx — header and main content shell.

## pages/

HomePage.tsx — wires useChat to ChatContainer with a fixed conversation ID.

## hooks/

useChat.ts

Owns chat interaction state. Uses TanStack useMutation with optimistic local turns.

useSpeechInput.ts

Owns browser speech-to-text via SpeechRecognition API. Returns supported, listening, start, stop.

useSpeechOutput.ts

Owns browser text-to-speech via SpeechSynthesis API. Returns supported, speaking, speak, cancel.

## services/api.ts

The ONLY frontend module that should directly communicate with the backend.

Owns postChat, fetchScore, ApiError, and error unwrapping from backend validation format.

## services/present.ts

Pure function presentResponse(ChatResponse) -> Block[].

Owns the mapping from evidence items to Block discriminated union for the UI.

## services/speak.ts

Pure functions for text-to-speech.

Owns preparing text, chunking, and converting blocks to a speakable string.

## types/

Frontend representations of backend response contracts.

chat.ts — re-exports generated API types and defines the Block discriminated union and Turn interface.

api.generated.ts — auto-generated from backend/openapi.json via openapi-typescript.

Do not put calculations here.

---

# Primary Execution Paths

## Airport Question

User
→ ChatInput
→ api.ts
→ /api/chat
→ orchestrator
→ tool
→ analysis_service
→ provider + analytics
→ structured result
→ LLM
→ ChatResponse
→ UI

## Direct Score API

GET airport score
→ airports.py
→ analysis_service
→ scoring
→ response

## Voice

VoiceButton
→ useSpeechRecognition
→ transcript
→ ChatInput
→ normal chat flow

Voice does not bypass standard chat validation.

---

# Source of Truth

Airport data:
providers

Domain models:
backend/app/models

Analytics:
backend/app/analytics

Final scoring:
backend/app/scoring/expansion_score.py

Agent tools:
backend/app/agent/tools.py

Agent policy:
backend/app/agent/prompts.py
backend/app/agent/guardrails.py

Backend communication:
frontend/src/services/api.ts

---

# Cross-Layer Rules

Never implement scoring in React.

Never implement scoring inside prompts.

Never implement provider logic inside routes.

Never call aviation APIs directly from React.

Never let the LLM perform authoritative calculations.

Never silently replace missing data with zero.

---

# Testing Map

Scoring:
backend/tests/test_scoring.py

Long haul:
backend/tests/test_long_haul.py

Guardrails:
backend/tests/test_guardrails.py

Providers and services:
backend/tests/test_providers.py

API routes:
backend/tests/test_api.py

Agent tools and ChatResponse:
backend/tests/test_tools.py

Add tests near the responsibility being changed.

---

# Agent Navigation Guidance

Before changing code:

1. Identify the responsibility.
2. Find it in this map.
3. Open the listed canonical files.
4. Inspect directly related dependencies.
5. Modify the smallest reasonable surface.

Do not scan or rewrite unrelated areas.

---

# When To Update This File

Update docs/CODEBASE_MAP.md when:

- modules move
- responsibility moves between layers
- important execution flows change
- canonical files change
- a major subsystem is added or removed

Do NOT update it for:

- styling changes
- small bug fixes
- internal function changes
- test additions that do not change architecture