# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Analyst or operator researching airport opportunity, congestion, comparisons, rankings, and simulations via chat.

## Product Purpose
Conversational analyst for US airport expansion pressure. Uses deterministic Python metrics over public aviation data (LLM orchestration/explanation only). Answers natural language queries with structured cards (scores, comparisons, rankings, KPIs).

## Positioning
Every metric, score, and ranking comes from deterministic Python over public aviation data. The LLM interprets intent and explains structured results—it never invents numbers. 

## Operating Context
Users ask plain language questions (text or voice) to a chat UI. The assistant returns a natural-language answer plus structured cards (scores, comparisons, rankings, KPIs) when relevant. Users follow up leveraging conversational context.

## Capabilities and Constraints
- Airports: any valid three-letter IATA code with BTS/NTAD coverage; universe loads on demand from chat or REST requests.
- Supported regions: new_england, west_coast, alaska, northeast, california.
- Voice input requires confirmation on low confidence (placed in text box instead of sent automatically).
- Voice output has a text fallback.
- No scoring or metric inference in React. Keep present.ts block parsing.
- REST paths explicitly documented.

## Brand Commitments
- Product name: AirportIQ
- Light, professional, readable UI. 
- Institutional analyst tool—absolutely no gamification or hype in UX copy or visuals.

## Evidence on Hand
- Data providers: BTS (live + optional bulk CSVs), NTAD, FAA NAS, NOAA Aviation Weather.
- Existing React components defining analytical evidence: `AirportScoreCard`, `AirportComparison`, `RankingTable`, `SimulationCard`, `KpiCard`, `ConfirmationPrompt`, `WarningsList`. 
- Metrics surface confidence, warnings, sources, data freshness when backend provides them.