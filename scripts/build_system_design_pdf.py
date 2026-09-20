"""Render AirportIQ-System-Design.pdf at the repository root.

Run:
    uv run --with playwright --with markdown scripts/build_system_design_pdf.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Please run this script using uv with the necessary dependencies:")
    print("uv run --with playwright scripts/build_system_design_pdf.py")
    raise SystemExit(1)

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PDF = ROOT_DIR / "AirportIQ-System-Design.pdf"
OUTPUT_PNG = ROOT_DIR / "AirportIQ-System-Flow.png"
SVG_PATH = ROOT_DIR / "docs" / "assets" / "airportiq-architecture.svg"
FLOW_SVG_PATH = ROOT_DIR / "docs" / "assets" / "airportiq-system-flow.svg"

HTML_DOCUMENT = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>AirportIQ System Design</title>
  <style>
    @page { size: A4; margin: 18mm 16mm 20mm 16mm; }
    * { box-sizing: border-box; }
    body {
      font-family: "Segoe UI", Calibri, Helvetica, Arial, sans-serif;
      font-size: 10.5pt;
      line-height: 1.5;
      color: #1e293b;
      margin: 0;
    }
    h1 { font-size: 22pt; margin: 0 0 6pt; color: #0f172a; }
    h2 {
      font-size: 14pt;
      color: #0f172a;
      border-bottom: 1.5px solid #cbd5e1;
      padding-bottom: 4pt;
      margin: 22pt 0 10pt;
      page-break-after: avoid;
    }
    h3 { font-size: 12pt; color: #0f766e; margin: 14pt 0 6pt; page-break-after: avoid; }
    h4 { font-size: 10.5pt; color: #334155; margin: 10pt 0 4pt; page-break-after: avoid; }
    p { margin: 0 0 8pt; }
    ul, ol { margin: 0 0 10pt; padding-left: 18pt; }
    li { margin-bottom: 3pt; }
    .subtitle { font-size: 12pt; color: #475569; margin-bottom: 14pt; }
    .lede { font-size: 11pt; color: #334155; }
    .meta { font-size: 9pt; color: #64748b; margin-bottom: 16pt; }
    .callout {
      background: #f0fdfa;
      border-left: 4px solid #0f766e;
      padding: 8pt 10pt;
      margin: 10pt 0 14pt;
    }
    .warn {
      background: #fff7ed;
      border-left: 4px solid #c2410c;
      padding: 8pt 10pt;
      margin: 10pt 0 14pt;
    }
    .formula {
      font-family: Consolas, "Courier New", monospace;
      font-size: 9.5pt;
      background: #f1f5f9;
      border: 1px solid #e2e8f0;
      padding: 8pt 10pt;
      margin: 6pt 0 12pt;
      white-space: pre-wrap;
      page-break-inside: avoid;
    }
    table {
      border-collapse: collapse;
      width: 100%;
      margin: 8pt 0 14pt;
      font-size: 9.5pt;
      page-break-inside: auto;
    }
    th, td {
      border: 1px solid #cbd5e1;
      padding: 5pt 7pt;
      text-align: left;
      vertical-align: top;
    }
    th { background: #f1f5f9; color: #0f172a; font-weight: 650; }
    tr { page-break-inside: avoid; }
    code {
      font-family: Consolas, "Courier New", monospace;
      font-size: 9pt;
      background: #f1f5f9;
      padding: 0 3pt;
    }
    .diagram {
      margin: 8pt 0 12pt;
      page-break-inside: avoid;
    }
    .diagram svg { width: 100%; height: auto; }
    .caption { font-size: 9pt; color: #64748b; margin: -4pt 0 12pt; }
    .tradeoff { page-break-inside: avoid; margin-bottom: 12pt; }
    .kicker { font-size: 8.5pt; letter-spacing: 0.08em; text-transform: uppercase; color: #0f766e; font-weight: 700; }
    .small { font-size: 9pt; color: #475569; }
    .flow {
      display: block;
      font-family: Consolas, "Courier New", monospace;
      font-size: 9pt;
      background: #0f172a;
      color: #e2e8f0;
      padding: 10pt 12pt;
      margin: 8pt 0 12pt;
      line-height: 1.55;
      white-space: pre-wrap;
    }
  </style>
</head>
<body>

  <p class="kicker">AirportIQ  ·  system design</p>
  <h1>Conversational analyst for US airport expansion pressure</h1>
  <p class="subtitle">Scoring methodology, data sources, AI boundaries, and architecture.</p>
  <p class="meta">Peer universe: BOS, BDL, PVD, PWM, LAX, SNA, ANC, SFO, JFK. Canonical weights live only in <code>backend/app/scoring/expansion_score.py</code>. This document describes the running system, not a proposed redesign.</p>

  <div class="callout">
    <strong>Source of truth.</strong> Python and verified aviation data produce every metric, score, ranking, simulation, and confidence label. The LLM is an interface, orchestration, and explanation layer. It must never create or modify airport statistics, KPIs, congestion values, long-haul percentages, unmet-demand indices, opportunity scores, confidence levels, or rankings.
  </div>

  <!-- ========== 1 ========== -->
  <h2>1. Introduction and product boundary</h2>
  <p class="lede">Investment and operations teams need answers about congestion, demand, and expansion pressure without trusting model-generated numbers. AirportIQ answers free-form questions about a fixed nine-airport US peer set and returns a <strong>pressure index</strong>, not a financial ROI or NPV.</p>

  <p>The product has two interfaces that share one analytical core:</p>
  <ul>
    <li><strong>Chat</strong> — <code>POST /api/chat</code> streams Server-Sent Events. An orchestrator screens input, asks an LLM to pick tools, executes those tools against a cached Universe snapshot, ships structured evidence first, then streams prose.</li>
    <li><strong>REST (no LLM)</strong> — <code>GET /api/airports/{code}</code>, <code>GET /api/airports/{code}/score</code>, <code>POST /api/airports/compare</code>, <code>GET /api/regions/{region}/ranking</code>. These routes validate and delegate to the same <code>AnalysisService.universe()</code>.</li>
  </ul>

  <p>Layer rules are strict: React does not implement business math; FastAPI routes do not contain scoring formulas; providers do not score airports; the LLM does not call aviation APIs or invent missing values. Missing data stays missing (<code>Present</code> / <code>Absent</code>), with confidence, sources, and warnings surfaced in both UI and API.</p>

  <!-- ========== 2 ========== -->
  <h2>2. System context and high-level design flow</h2>
  <p>Chat and REST share one TTL-cached Universe. Structured cards in the UI are built from Python tool results before any LLM sentence is shown. The diagram below is the high-level design flow (Client → FastAPI → Agent → Core).</p>

  <div class="diagram">{{FLOW_SVG}}</div>
  <p class="caption">Figure 1. High-level design flow. Dashed arrow is the chat SSE stream (phase, meta, delta, done). REST skips the agent and reads AnalysisService directly.</p>

  <h3>HTTP APIs (this application)</h3>
  <p>All routes are mounted under <code>/api</code>. Interactive docs: <code>http://localhost:8000/docs</code>. OpenAPI: <code>backend/openapi.json</code>.</p>
  <table>
    <thead><tr><th>Method</th><th>Path</th><th>LLM?</th><th>Returns</th></tr></thead>
    <tbody>
      <tr><td>GET</td><td><code>/api/health</code></td><td>No</td><td>Liveness <code>{"status":"ok"}</code></td></tr>
      <tr><td>GET</td><td><code>/api/airports/{code}</code></td><td>No</td><td>Traffic/delay metrics + context</td></tr>
      <tr><td>GET</td><td><code>/api/airports/{code}/score</code></td><td>No</td><td>Expansion opportunity score (0–100 components)</td></tr>
      <tr><td>GET</td><td><code>/api/airports/{code}/long-haul</code></td><td>No</td><td>BTS T-100 long-haul report (optional year, threshold, passenger_only)</td></tr>
      <tr><td>POST</td><td><code>/api/airports/compare</code></td><td>No</td><td>Body <code>{"airport_codes":["BOS","JFK"]}</code> → comparison rows</td></tr>
      <tr><td>GET</td><td><code>/api/regions/{region}/ranking</code></td><td>No</td><td>Region ranking: new_england, west_coast, alaska, northeast, california</td></tr>
      <tr><td>GET</td><td><code>/api/scoring/methodology</code></td><td>No</td><td>Canonical weights and scoring rules (no LLM)</td></tr>
      <tr><td>POST</td><td><code>/api/chat</code></td><td>Yes</td><td>SSE: phase, meta, delta, done. Body: message, conversation_id, voice_confidence</td></tr>
      <tr><td>GET</td><td><code>/api/tts/status</code></td><td>No</td><td>Whether speech synthesis is configured</td></tr>
      <tr><td>POST</td><td><code>/api/tts</code></td><td>Speech only</td><td>Body <code>{"text":"..."}</code> → <code>audio/mpeg</code></td></tr>
    </tbody>
  </table>

  <h3>Local data files (CSV / JSON / ZIP)</h3>
  <p>Providers read these files from disk. Live HTTP sources (OpenSky, FAA NAS, NOAA METAR, OpenAI) are not stored as CSVs.</p>
  <table>
    <thead><tr><th>File</th><th>Format</th><th>Used by</th><th>What it supplies</th></tr></thead>
    <tbody>
      <tr><td><code>backend/data/airport_coords.csv</code></td><td>CSV</td><td>CoordinateLookup overlay</td><td>ICAO, IATA, lat, lon for the 9 peers plus long-haul destination airports (LHR, CDG, NRT, …)</td></tr>
      <tr><td><code>backend/data/ourairports_airports.csv</code></td><td>CSV</td><td>CoordinateLookup base</td><td>Global ICAO coordinates from OurAirports. Refresh: <code>backend/scripts/refresh_ourairports.py</code></td></tr>
      <tr><td><code>backend/data/raw/bts/*.csv</code> or <code>.zip</code></td><td>CSV / ZIP</td><td>BtsT100FileProvider</td><td>T-100 Segment: origin, dest, distance, performed departures, year/month. Gitignored; drop a TranStats file here</td></tr>
      <tr><td><code>backend/data/cache/faa_acais_enplanements.json</code></td><td>JSON</td><td>FaaAcaisFileProvider</td><td>Current and previous passenger volume (enplanements). Refresh script in backend/scripts</td></tr>
      <tr><td><code>backend/data/cache/faa_atads_operations.json</code></td><td>JSON</td><td>FaaAtadsFileProvider</td><td>Annual operations. Refresh script in backend/scripts</td></tr>
      <tr><td><code>backend/data/cache/openflights_routes.json</code></td><td>JSON</td><td>OpenFlightsRoutesProvider</td><td>Distinct / international / long-haul route counts (context only)</td></tr>
      <tr><td><code>backend/data/sample_airports.json</code></td><td>JSON</td><td>SampleProvider</td><td>Labeled sample fallback for all core scoring KPIs when live/file fields are missing</td></tr>
    </tbody>
  </table>
  <p class="small">External APIs (not files): OpenSky Network departures, FAA NAS delay-program XML, NOAA Aviation Weather METAR, OpenAI Chat Completions and speech. Coordinate overlay wins over OurAirports for the same ICAO.</p>

  <div class="diagram">{{SVG}}</div>
  <p class="caption">Figure 2. System context: analyst, AirportIQ, OpenAI (orchestration only), and public aviation data via providers.</p>

  <h3>Request pipeline</h3>
  <div class="flow">User
 → React Chat UI (or REST client)
 → FastAPI  (/api/chat SSE  or  /api/airports/*)
 → Orchestrator  (chat)  |  AnalysisService  (REST)
 → Approved tools  (chat only; thin reads of Universe)
 → AnalysisService  (fetch, merge, dossier, score)
 → Analytics + Scoring  (deterministic Python)
 → Data providers  (FAA, BTS, OpenSky, NOAA, sample)
 → Structured result  (SSE meta  or  JSON)
 → LLM explanation  (SSE delta; chat only)
 → React cards + prose</div>

  <h3>Chat SSE phases</h3>
  <p>The orchestrator (<code>Orchestrator.turn_stream</code>) emits events in this order so the UI can show numbers before prose finishes:</p>
  <table>
    <thead><tr><th>Event</th><th>When</th><th>What the client receives</th></tr></thead>
    <tbody>
      <tr><td><code>phase: tool_select</code></td><td>After input screening</td><td>LLM is choosing from the fixed 12-tool registry</td></tr>
      <tr><td><code>phase: tools</code></td><td>After tool list is final</td><td>Python tools execute on the Universe snapshot</td></tr>
      <tr><td><code>phase: compose</code></td><td>After evidence is ready</td><td>Narrative generation is about to start</td></tr>
      <tr><td><code>meta</code></td><td>Before any prose</td><td>Partial <code>ChatResponse</code>: score cards, rankings, KPIs, warnings</td></tr>
      <tr><td><code>delta</code></td><td>While the LLM streams</td><td>Plain-English chunks grounded in the facts digest</td></tr>
      <tr><td><code>done</code></td><td>After output screening</td><td>Final <code>ChatResponse</code> with cleaned prose and evidence</td></tr>
      <tr><td><code>error</code></td><td>On unhandled failure</td><td>Detail string; no fabricated scores</td></tr>
    </tbody>
  </table>

  <h3>Layer responsibilities</h3>
  <table>
    <thead><tr><th>Layer</th><th>Owns</th><th>Must not own</th></tr></thead>
    <tbody>
      <tr><td>React</td><td>Chat UI, SSE consumption, cards keyed by <code>ToolResult.kind</code></td><td>Scoring, rankings, KPI formulas</td></tr>
      <tr><td>FastAPI</td><td>Validation and delegation</td><td>Aviation fetch, scoring</td></tr>
      <tr><td>Orchestrator</td><td>Turn lifecycle, parallel universe + LLM, SSE, audit log</td><td>Formulas</td></tr>
      <tr><td>Tools</td><td>12 approved projections over <code>Universe</code></td><td>Provider HTTP, weight changes</td></tr>
      <tr><td>AnalysisService</td><td>TTL-cached Universe build (fetch, merge, dossier, score)</td><td>LLM calls</td></tr>
      <tr><td>Analytics / Scoring</td><td>Deterministic KPIs and the 30/30/20/20 index</td><td>External I/O</td></tr>
      <tr><td>Providers</td><td>Fetch and normalize into Pydantic fields</td><td>Opportunity scores</td></tr>
    </tbody>
  </table>

  <!-- ========== 3 ========== -->
  <h2>3. Scoring methodology — end to end</h2>
  <p>The Expansion Opportunity Score is a 0–100 pressure index. Weights exist in one place: <code>SCORING_WEIGHTS</code> in <code>expansion_score.py</code>. Frontend and prompts must never duplicate the formula.</p>

  <h3>3.1 Universe build</h3>
  <p><code>AnalysisService.universe()</code> returns a frozen snapshot reused by every chat tool and REST call until TTL expires (default <strong>3600 seconds</strong>). Build steps:</p>
  <ol>
    <li><code>CompositeProvider.fetch(codes)</code> runs live/file providers concurrently, then sample.</li>
    <li><code>merge_outcomes</code> produces one <code>AirportMetrics</code> per IATA: first provider that supplies a field wins.</li>
    <li>Context providers (FAA NAS, optional weather, OpenFlights) merge into <code>AirportContext</code>.</li>
    <li><code>_build_peer_stats</code> computes min/max bounds across the nine airports for <code>passenger_volume</code>, <code>annual_operations</code>, and <code>pax_per_operation</code>.</li>
    <li>YoY growth is computed for every airport; those values become <code>demand_growth</code> peer bounds.</li>
    <li><code>_build_dossier</code> attaches growth, long-haul %, unmet-demand index, and context.</li>
    <li><code>score_dossier(dossier, peers)</code> writes the four component scores plus opportunity and confidence.</li>
    <li>The Universe stores <code>snapshot_at</code>, dossiers, scores, peers, and <code>ProviderFailure</code> records.</li>
  </ol>
  <p>Because rankings and comparisons read this snapshot, two users asking “rank New England” within the TTL window see the same order.</p>

  <h3>3.2 Peer normalization</h3>
  <p>Raw analytics are not the score. Each comparable quantity is scaled to 0–100 against the frozen peer set:</p>
  <div class="formula">normalize_min_max(value, lo, hi):
  if lo == hi: return 50.0          # identical peers → midpoint, not 0
  raw = (value − lo) / (hi − lo) × 100
  return clamp to [0, 100]

clamp_score(value): round to 1 decimal, clamp [0, 100]</div>
  <p>A high score means “high relative to these nine airports,” not “high versus the United States.” Adding or removing a peer would move every bound and therefore every score.</p>

  <h3>3.3 Canonical weights</h3>
  <table>
    <thead><tr><th>Component</th><th>Weight</th><th>What a high value means</th></tr></thead>
    <tbody>
      <tr><td>Demand growth</td><td>30%</td><td>Stronger YoY passenger growth than peers</td></tr>
      <tr><td>Congestion</td><td>30%</td><td>Higher ops/delay/pax pressure; extra bump if FAA NAS GDP is active</td></tr>
      <tr><td>Delay pressure</td><td>20%</td><td>Worse delayed-flight share and/or longer average delay</td></tr>
      <tr><td>Capacity pressure</td><td>20%</td><td>More passengers per operation, optionally blended with growth</td></tr>
    </tbody>
  </table>

  <h3>3.4 Missing-component policy</h3>
  <p><code>_weighted_opportunity</code> never fills gaps with zero. If a component is <code>Absent</code>, its weight is redistributed across components that are present:</p>
  <div class="formula">opportunity = Σ (wᵢ / Σ w_present) × componentᵢ
if no components present → Absent (reason NOT_PUBLISHED)</div>
  <p>Example: if capacity pressure is missing, the remaining 80% of weights are scaled to 100% (demand 37.5%, congestion 37.5%, delay 25%). The score is still defined, but confidence drops. If all four are absent, opportunity itself is absent and ranking sorts that airport last.</p>

  <h3>3.5 Confidence</h3>
  <p><code>calculate_confidence(metrics, components)</code> is programmatic — the LLM may cite it but must not upgrade or downgrade it.</p>
  <table>
    <thead><tr><th>Label</th><th>Rule</th></tr></thead>
    <tbody>
      <tr><td>HIGH</td><td>Core KPI completeness = 1.0 (all five core fields present) <em>and</em> all four score components present</td></tr>
      <tr><td>LOW</td><td>Core completeness &lt; 0.8 <em>or</em> fewer than three score components present</td></tr>
      <tr><td>MEDIUM</td><td>Everything else</td></tr>
    </tbody>
  </table>
  <p>Core scoring KPI fields: <code>passenger_volume</code>, <code>previous_passenger_volume</code>, <code>annual_operations</code>, <code>delayed_flights_pct</code>, <code>average_delay_minutes</code>. Long-haul fields are extra completeness, not this confidence gate.</p>

  <h3>3.6 Rank, compare, simulate</h3>
  <ul>
    <li><strong>Rank</strong> — descending opportunity; absent opportunity sorts last.</li>
    <li><strong>Compare</strong> — per-component delta (A − B); <code>None</code> when either side is absent.</li>
    <li><strong>Simulate</strong> — <code>Universe.simulate(code, pct)</code> adds the user growth increment to existing passenger growth, re-runs <code>score_dossier</code> against the <strong>same</strong> peer bounds (the rest of the universe does not move). Returns baseline, simulated score, and opportunity delta. This is a scenario, not a forecast.</li>
  </ul>

  <!-- ========== 4 ========== -->
  <h2>4. Scoring components — in depth</h2>
  <p>Each subsection follows the same path: inputs → formula → missing-data behavior → role in the index → limitations. Origins folded onto results carry method, proxy flag, assumption, and source lineage.</p>

  <h3>4.1 Demand growth (weight 30%)</h3>
  <p><strong>Code:</strong> <code>analytics/demand.py</code> <code>calculate_passenger_growth</code>, then peer min–max in <code>score_dossier</code>.</p>
  <p><strong>Inputs:</strong> current and previous passenger volume (typically FAA ACAIS calendar-year enplanements).</p>
  <div class="formula">raw_growth = (current − previous) / previous
demand_growth_score = normalize_min_max(raw_growth, peer_lo, peer_hi)</div>
  <ul>
    <li>If either volume is absent → growth is <code>Absent(NOT_PUBLISHED)</code>.</li>
    <li>If previous ≤ 0 → <code>Absent(OUT_OF_SCOPE)</code> (avoids division blow-ups).</li>
    <li>Raw growth is a ratio (0.05 = +5%), not a 0–100 score. Only after peer normalization does it enter the weighted sum.</li>
  </ul>
  <p><strong>Scoring role:</strong> identifies airports whose passenger demand is accelerating relative to the peer set — a reason expansion pressure may be rising even if congestion is moderate.</p>
  <p><strong>Limitations:</strong> one YoY step, not a multi-year trend; enplanements are not origin-destination demand; cargo-only activity is not in this component.</p>

  <h3>4.2 Congestion (weight 30%)</h3>
  <p><strong>Code:</strong> <code>analytics/congestion.py</code> <code>calculate_congestion_score</code>.</p>
  <p><strong>Inputs:</strong> annual operations (peer-normalized), delayed-flight percentage (already a %), passenger volume (peer-normalized), and FAA NAS ground-delay-program (GDP) activity from context.</p>
  <div class="formula">base = 0.5 × ops_norm + 0.3 × delayed_pct_norm + 0.2 × pax_norm
# absent inputs dropped; remaining weights renormalised to 1.0
congestion = clamp(base + (10 if gdp_active else 0))</div>
  <ul>
    <li>If all three inputs are absent → congestion is absent.</li>
    <li>The +10 GDP bump is applied after the blend, then the result is clamped to 0–100.</li>
    <li>Origin is labeled <code>proxy=True</code> with assumption: “Congestion proxy from operations volume, delay rates, and passenger throughput.”</li>
  </ul>
  <p><strong>Scoring role:</strong> operational crowding signal. A NAS GDP is treated as extra evidence that the NAS already considers the airport constrained that day.</p>
  <p><strong>Limitations:</strong> not gate counts, taxiway geometry, or terminal square footage; not clock-hour peaks (those questions are declined). Large airports look “congested” partly because they are large versus this nine-airport set.</p>

  <h3>4.3 Delay pressure (weight 20%)</h3>
  <p><strong>Code:</strong> <code>calculate_delay_pressure</code> in the same congestion module.</p>
  <p><strong>Inputs:</strong> delayed-flights percentage and average delay minutes.</p>
  <div class="formula">full:     0.6 × delayed_pct  +  0.4 × clamp(avg_delay_min / 60 × 100)
pct only: delayed_pct  (renormalized: avg_delay_min absent)
min only: clamp(avg_delay_min / 60 × 100)  (renormalized: delayed_pct absent)
both missing → Absent</div>
  <p>Average delay is scaled as a fraction of one hour: 30 minutes → 50 on that sub-score. Delayed % is treated as already 0–100.</p>
  <p><strong>Scoring role:</strong> isolates delay pain from sheer traffic volume, so a smaller airport with chronic delays can still score high here.</p>
  <p><strong>Limitations:</strong> depends on BTS on-time (if enabled) or sample fallback. It is not a causal FAA delay-code report and cannot answer “peak hour on Thursday.”</p>

  <h3>4.4 Capacity pressure (weight 20%)</h3>
  <p><strong>Code:</strong> <code>analytics/capacity.py</code> <code>calculate_capacity_pressure</code>.</p>
  <p><strong>Inputs:</strong> passenger volume, annual operations, and (optionally) passenger growth.</p>
  <div class="formula">require Present(pax) and Present(ops) and ops &gt; 0
pax_per_op = pax / ops
utilisation = normalize_min_max(pax_per_op, peer pax_per_operation bounds)

if growth present:
  capacity = 0.6 × utilisation + 0.4 × clamp(growth × 100)
else:
  capacity = utilisation</div>
  <p>If pax or ops is missing, or ops ≤ 0, capacity is absent (not zero). Growth is the same YoY ratio used in demand; multiplying by 100 maps 5% growth to 5 on that sub-score before blending.</p>
  <p><strong>Scoring role:</strong> proxy for “how hard the existing operation is working,” combining intensity (pax/op) with demand trajectory when known.</p>
  <p><strong>Limitations:</strong> passengers per operation is not gates, seats, or declared capacity. Two airports with similar pax/op can have very different physical headroom. The UI and prompts must label this a proxy.</p>

  <h3>4.5 Related indices — not in the opportunity sum</h3>
  <h4>Unmet demand index</h4>
  <p><code>calculate_unmet_demand_index</code> (weights 50% peer-normalized growth, 25% delay pressure, 25% congestion). Absent inputs drop and remaining weights renormalize. Exposed by <code>get_unmet_demand</code> / <code>explain_unmet_demand</code>. It is an aggregate proxy, not a per-route waitlist or leakage model.</p>
  <h4>Long-haul percentage</h4>
  <p>On the dossier: <code>long_haul_flights / total_departures × 100</code> from merged metrics. Rich reports come from BTS T-100 <code>get_report</code>: performed-departure weighted share, default threshold <strong>3,000 statute miles</strong>, optional passenger-only filter (service class F/G). Cargo is included unless that filter is on. The LLM is forbidden to recompute the percentage.</p>
  <h4>Explain tools</h4>
  <p><code>analytics/drivers.py</code> rebuilds the same proxy math as weighted driver rows (<code>explain_congestion</code>, <code>explain_capacity_pressure</code>, <code>explain_unmet_demand</code>) so narrative “why” answers stay tied to Python, not model speculation.</p>

  <!-- ========== 5 ========== -->
  <h2>5. Data sources — what each one supplies</h2>
  <p>Providers fetch and normalize. They do not score. <code>merge_outcomes</code> walks providers in registration order; for each metric field the first <code>Present</code> wins. If nobody supplies the field, it becomes <code>Absent</code> with <code>attempted</code> listing providers that failed. Zeros are never invented.</p>

  <h3>5.1 Aviation metric providers (CompositeProvider order)</h3>
  <table>
    <thead><tr><th>Order</th><th>Provider</th><th>Kind</th><th>Fields supplied</th><th>Notes</th></tr></thead>
    <tbody>
      <tr>
        <td>1 (optional)</td>
        <td><code>BtsOnTimeProvider</code></td>
        <td>Live HTTP</td>
        <td><code>delayed_flights_pct</code>, <code>average_delay_minutes</code></td>
        <td>Only if <code>BTS_ON_TIME_ENABLED</code>. Placeholder Socrata URL in MVP; failures are recorded, they do not crash the universe.</td>
      </tr>
      <tr>
        <td>2</td>
        <td><code>FaaAcaisFileProvider</code></td>
        <td>Cached JSON</td>
        <td><code>passenger_volume</code>, <code>previous_passenger_volume</code></td>
        <td>FAA ACAIS commercial-service enplanements (<code>backend/data/cache/faa_acais_enplanements.json</code>). Primary demand input.</td>
      </tr>
      <tr>
        <td>3</td>
        <td><code>FaaAtadsFileProvider</code></td>
        <td>Cached JSON</td>
        <td><code>annual_operations</code></td>
        <td>FAA ATADS tower operations. Used in congestion and capacity (pax/op).</td>
      </tr>
      <tr>
        <td>4</td>
        <td><code>BtsT100FileProvider</code></td>
        <td>CSV / ZIP on disk</td>
        <td><code>total_departures</code>, <code>long_haul_flights</code></td>
        <td>BTS T-100 Segment, filtered to supported origins. Percentage = long-haul performed departures / all performed departures. Also serves lazy destination reports for chat.</td>
      </tr>
      <tr>
        <td>5 (conditional)</td>
        <td><code>OpenSkyProvider</code></td>
        <td>Live API (OAuth)</td>
        <td>Same departure fields</td>
        <td>Registered only if T-100 did <em>not</em> load and <code>OPENSKY_TRAFFIC_ENABLED</code>. Counts resolvable-destination departures over a sliding window (default 7 days), Haversine ≥ 3,000 mi. Rate-limit aware (429 backoff).</td>
      </tr>
      <tr>
        <td>Last</td>
        <td><code>SampleProvider</code></td>
        <td>Bundled JSON</td>
        <td>All core metrics, origin kind <code>sample</code></td>
        <td><code>data/sample_airports.json</code>. Always runs after live/file so demos work when APIs fail. UI shows Sample / mixed freshness badges.</td>
      </tr>
    </tbody>
  </table>

  <h3>5.2 Context providers (ContextComposite)</h3>
  <table>
    <thead><tr><th>Provider</th><th>Supplies</th><th>Effect on scoring</th></tr></thead>
    <tbody>
      <tr><td><code>FaaNasProvider</code></td><td>Live NAS status XML → <code>nas_delay_program</code> (GDP / delay type)</td><td>If a program matches the airport, congestion gets +10 before clamp</td></tr>
      <tr><td><code>AviationWeatherProvider</code></td><td>NOAA AWC METAR → weather context</td><td>Optional (<code>WEATHER_ENABLED</code>). Context only, not a score weight</td></tr>
      <tr><td><code>OpenFlightsRoutesProvider</code></td><td>Cached distinct / international / long-haul route counts</td><td>Connectivity context; not an opportunity input</td></tr>
    </tbody>
  </table>

  <h3>5.3 Supporting assets (not providers)</h3>
  <ul>
    <li><code>CoordinateLookup</code> — OurAirports global ICAO coordinates plus a local overlay; IATA↔ICAO for OpenSky and weather.</li>
    <li><code>AirportCatalog</code> — names, cities, states for the nine supported airports.</li>
    <li>BTS <code>long_haul_report</code> — on-demand destination table for <code>get_long_haul_percentage</code>, not mixed into the opportunity formula.</li>
  </ul>

  <h3>5.4 Freshness, failures, and honesty</h3>
  <div class="warn">
    Mixed snapshots are expected: ACAIS may be last calendar year, NAS is intra-day, T-100 lags by months, OpenSky is a recent window, sample is static. Universe stores <code>ProviderFailure</code> list and per-metric warnings. The UI surfaces Sample / Cached / Mixed badges. The agent must name sources and must not paper over holes with plausible numbers.
  </div>

  <!-- ========== 6 ========== -->
  <h2>6. Where and how the LLM is used</h2>
  <p>Chat uses an OpenAI-compatible client (<code>OpenAILLMClient</code>, default model <code>gpt-4o-mini</code>) with two calls per turn. REST never calls the LLM. Optional TTS is a third, non-analytical call.</p>

  <h3>6.1 Call 1 — choose tools</h3>
  <p>The orchestrator builds a <code>TurnContext</code>:</p>
  <ul>
    <li><code>SYSTEM_PROMPT</code> — 13 rules: tool-grounded numbers, long-haul definition, proxy labels, confidence, no return guarantees, missing-data honesty, source citation, supported-set scope, no DIY scoring, plain English, follow-up discipline, capability limits, unclear-input handling.</li>
    <li>Conversation frame and thread digest (airports already in scope).</li>
    <li>Facts digest — JSON of carried tool results from prior turns.</li>
    <li>Resolution hints (referents, capability declines, injection note, “not an analytics question”).</li>
    <li>The user message.</li>
  </ul>
  <p>The model may emit function calls only from the fixed registry. Schemas are generated from Pydantic arg models. Unknown names never execute.</p>

  <h3>6.2 Deterministic repair of tool choice</h3>
  <p>The LLM’s list is not trusted blindly:</p>
  <table>
    <thead><tr><th>Step</th><th>Module</th><th>Why it exists</th></tr></thead>
    <tbody>
      <tr><td>Input screen</td><td><code>guardrails.screen_input</code></td><td>Prompt-injection note; low-confidence voice confirmation instead of auto-send</td></tr>
      <tr><td>Mentions / referents</td><td><code>resolve_mentions</code>, <code>resolve_referents</code></td><td>Maps “Logan”, “those two”, “the first one” to IATA codes</td></tr>
      <tr><td>Airport scope</td><td><code>airport_scope.resolve_airport_scope</code></td><td>Binds the turn to one coherent set so follow-ups do not mix unrelated airports</td></tr>
      <tr><td>Coalesce</td><td><code>tool_coalesce</code></td><td>Dedupes / merges redundant calls</td></tr>
      <tr><td>Reconcile</td><td><code>tool_reconcile</code></td><td>Rewrites explain-only selections when the user asked to compare</td></tr>
      <tr><td>Region inject</td><td>orchestrator</td><td>Adds <code>rank_region</code> when the message wants a regional ranking</td></tr>
      <tr><td>Empty-plan fallback</td><td><code>follow_up.plan_fallback_tools</code></td><td>If the model picks nothing, a keyword/frame planner still runs tools (or first-turn <code>intent_routing</code>)</td></tr>
      <tr><td>Non-analytical</td><td>orchestrator</td><td>Clears tool calls and asks a short clarifying question</td></tr>
    </tbody>
  </table>
  <p>Universe fetch starts in parallel with <code>choose_tools</code> so data is warm when tools run. Execution is <code>asyncio.to_thread(execute, call, universe)</code> — tools are pure reads and never raise into the HTTP layer.</p>

  <h3>6.3 Call 2 — respond_stream</h3>
  <p>After tools return, the orchestrator selects display evidence (this turn vs carried). It emits <code>meta</code> with structured cards <em>before</em> asking the LLM to speak. The compose-phase context rebuilds the facts digest from that evidence and adds hints such as “the UI already shows a ranking table — interpret, do not recap.”</p>
  <p>Prose is streamed as <code>delta</code> chunks. Then <code>screen_output</code>:</p>
  <ul>
    <li><code>verify_numbers</code> — advisory warnings when prose contains numbers not present in evidence JSON.</li>
    <li><code>scrub_guarantees</code> — appends a disclaimer if ROI / guarantee language slipped through.</li>
  </ul>
  <p>The session keeps at most <strong>six</strong> exchanges (TTL 1 hour, in-memory). <code>TurnAudit</code> logs conversation id, tools called, evidence origin (this_turn / carried / none), injection flag, and number warnings.</p>

  <h3>6.4 Approved tools (Python, not the model)</h3>
  <table>
    <thead><tr><th>Tool</th><th>Returns</th></tr></thead>
    <tbody>
      <tr><td><code>get_airport_metrics</code></td><td>Traffic and delay KPIs + context</td></tr>
      <tr><td><code>get_airport_score</code></td><td>Expansion opportunity score and components</td></tr>
      <tr><td><code>compare_airports</code></td><td>Side-by-side rows; flags highest congestion / opportunity</td></tr>
      <tr><td><code>rank_airports</code> / <code>rank_region</code></td><td>Ordered scores for named codes or a region</td></tr>
      <tr><td><code>rank_by_metric</code></td><td>Peer or region rank by one component (or growth / unmet demand)</td></tr>
      <tr><td><code>get_long_haul_percentage</code></td><td>T-100 (or OpenSky) long-haul share and destination report</td></tr>
      <tr><td><code>get_unmet_demand</code></td><td>Unmet-demand index</td></tr>
      <tr><td><code>simulate_airport_growth</code></td><td>Baseline vs simulated scores and delta</td></tr>
      <tr><td><code>explain_congestion</code> / <code>explain_capacity_pressure</code> / <code>explain_unmet_demand</code></td><td>Driver breakdowns matching proxy formulas</td></tr>
    </tbody>
  </table>

  <h3>6.5 What the LLM does not do</h3>
  <ul>
    <li>Invent data or KPIs, or fill absent fields with guesses.</li>
    <li>Calculate final scores, percentages, or independently rank airports.</li>
    <li>Call OpenSky, FAA, BTS, or any aviation API directly.</li>
    <li>Upgrade or downgrade programmatic confidence.</li>
    <li>Promise investment returns or treat the pressure index as ROI.</li>
    <li>Answer out-of-scope analyst questions (hourly peaks, airline-level long-haul, per-route unmet demand, passenger leakage, 5–10 year capacity forecasts) except to decline and offer a proxy rephrase — see the capability matrix.</li>
  </ul>
  <p>Optional <code>TTSService</code> sends already-written text to OpenAI speech. It does not compute anything.</p>

  <!-- ========== 7 ========== -->
  <h2>7. Key tradeoffs</h2>
  <p>Each tradeoff is a deliberate product choice: decision, rationale, user-visible effect, and how the system mitigates the downside.</p>

  <div class="tradeoff">
    <h3>7.1 Fixed nine-airport peer universe vs national coverage</h3>
    <p><strong>Decision.</strong> Normalize and rank only BOS, BDL, PVD, PWM, LAX, SNA, ANC, SFO, JFK.</p>
    <p><strong>Rationale.</strong> Min–max scores need a closed set. A national index would require complete data and a different product story. The nine airports span hubs, relievers, a coastal pair (LAX/SNA), and Anchorage long-haul.</p>
    <p><strong>Effect.</strong> “80 congestion” means high in this set, not versus ATL or ORD. Adding one mega-hub would compress everyone else’s scores.</p>
    <p><strong>Mitigation.</strong> Scope is documented in the UI and prompts. Unsupported airports fail at the tool, they are not hallucinated. REST regions are explicit subsets of the same set.</p>
  </div>

  <div class="tradeoff">
    <h3>7.2 Operational proxies vs physical infrastructure</h3>
    <p><strong>Decision.</strong> Congestion and capacity use ops, delay %, pax, and pax/op — not gates, terminal area, or declared runway capacity.</p>
    <p><strong>Rationale.</strong> Those physical series are not consistently public for a demo-scale product. FAA ACAIS/ATADS and delay stats are.</p>
    <p><strong>Effect.</strong> The system can say “pressure looks high relative to peers” and cannot say “the terminal is at 94% of design load.” Peak-hour questions are declined.</p>
    <p><strong>Mitigation.</strong> Origins carry <code>proxy=True</code> and an assumption string. Explain tools expose driver weights. Prompts require the model to label proxies.</p>
  </div>

  <div class="tradeoff">
    <h3>7.3 Pressure index vs financial ROI</h3>
    <p><strong>Decision.</strong> Opportunity score is expansion pressure, not NPV, IRR, or “will this concourse pay back.”</p>
    <p><strong>Rationale.</strong> Honest MVP: public ops data cannot support capital budgeting. Mixing fake finance with real FAA numbers would be more dangerous than omitting finance.</p>
    <p><strong>Effect.</strong> Users asking for route value or leakage get a one-sentence limit plus a proxy (rank by unmet demand or capacity pressure).</p>
    <p><strong>Mitigation.</strong> <code>scrub_guarantees</code>, system prompt rule 5, and the capability matrix.</p>
  </div>

  <div class="tradeoff">
    <h3>7.4 Live + file + sample merge vs a single golden source</h3>
    <p><strong>Decision.</strong> CompositeProvider: concurrent live/file, then sample. First field wins.</p>
    <p><strong>Rationale.</strong> OpenSky 429s and NAS outages should not blank the demo. File caches (ACAIS, ATADS, T-100) are more stable than live APIs for annual facts.</p>
    <p><strong>Effect.</strong> A score can mix last year’s enplanements, a sample delay rate, and a live NAS GDP. Freshness is mixed.</p>
    <p><strong>Mitigation.</strong> Failures stay on Universe; UI badges; agent must cite sources; no silent zero-fill. Sample origin is a distinct kind, not disguised as live.</p>
  </div>

  <div class="tradeoff">
    <h3>7.5 No RAG vs citing master plans and EIS PDFs</h3>
    <p><strong>Decision.</strong> Structured aviation tables only. No vector store, no PDF corpus.</p>
    <p><strong>Rationale.</strong> RAG would let the model quote planning documents that the scoring engine cannot verify, violating “Python is the source of truth.”</p>
    <p><strong>Effect.</strong> AirportIQ cannot cite a specific runway project or environmental finding unless that fact is in a provider field (it is not).</p>
    <p><strong>Mitigation.</strong> Capability declines for qualitative planning questions. Scores remain testable in <code>test_scoring.py</code>.</p>
  </div>

  <div class="tradeoff">
    <h3>7.6 In-memory sessions vs persistent multi-device chat</h3>
    <p><strong>Decision.</strong> <code>SessionStore</code> in process memory: max six exchanges, 1-hour TTL, per-conversation lock. No auth, no Redis, no database.</p>
    <p><strong>Rationale.</strong> Architecture rule: do not introduce those systems unless asked. Follow-ups (“compare those two”) only need recent evidence.</p>
    <p><strong>Effect.</strong> Restarting the backend forgets chat. Two browsers do not share history. Long investigations fall off the deque.</p>
    <p><strong>Mitigation.</strong> REST remains stateless. Conversation id is client-supplied so a single tab stays coherent for the TTL window.</p>
  </div>

  <div class="tradeoff">
    <h3>7.7 LLM tool routing plus deterministic fallback</h3>
    <p><strong>Decision.</strong> Prefer the model’s tool list, then coalesce/reconcile/inject, then <code>plan_fallback_tools</code> if empty.</p>
    <p><strong>Rationale.</strong> Natural language is messy; a small model will sometimes pick nothing or pick explain-only on a compare question. Pure LLM routing would drop follow-ups. Pure keyword routing would miss phrasing.</p>
    <p><strong>Effect.</strong> Two paths to maintain and test. Occasional double-fetch if the fallback is broader than needed.</p>
    <p><strong>Mitigation.</strong> Tools are idempotent reads of a cached Universe. Tests cover guardrails, follow-up, and tools. Audit logs show which tools actually ran.</p>
  </div>

  <div class="tradeoff">
    <h3>7.8 SSE meta-before-delta</h3>
    <p><strong>Decision.</strong> Ship structured evidence in <code>meta</code> before streaming prose.</p>
    <p><strong>Rationale.</strong> Trust: users should see Python numbers even if the model is slow or slightly off in wording.</p>
    <p><strong>Effect.</strong> The client must handle partial streams, phase labels, and a final <code>done</code> that may adjust warnings after output screening.</p>
    <p><strong>Mitigation.</strong> <code>presentResponse</code> maps <code>ToolResult.kind</code> to cards. <code>verify_numbers</code> flags prose that drifts from JSON.</p>
  </div>

  <div class="tradeoff">
    <h3>7.9 BTS T-100 historical long-haul vs OpenSky live window</h3>
    <p><strong>Decision.</strong> Prefer T-100 performed departures when the file is loaded; OpenSky only if T-100 is missing.</p>
    <p><strong>Rationale.</strong> T-100 is the statistical series for “share of departures that are long-haul.” OpenSky is a short live sample with incomplete destination resolution.</p>
    <p><strong>Effect.</strong> Long-haul % can lag real schedules by months. Live traffic spikes do not move the T-100-based KPI until the file is refreshed.</p>
    <p><strong>Mitigation.</strong> Reports include source, period, threshold, cargo inclusion, and partial-year metadata. Prompts require those caveats in prose.</p>
  </div>

  <div class="tradeoff">
    <h3>7.10 Explicit declines vs stretching the model</h3>
    <p><strong>Decision.</strong> Capability hints and the analyst matrix decline hourly peaks, airline-level long-haul, per-route unmet demand, leakage, and 5–10 year capacity as forecast.</p>
    <p><strong>Rationale.</strong> Better to refuse than to let the LLM invent a peak-hour story from an annual delay average.</p>
    <p><strong>Effect.</strong> Some investor questions get a short “cannot” plus a nearby proxy (compare delay pressure; rank capacity pressure; simulate growth).</p>
    <p><strong>Mitigation.</strong> <code>docs/capability-matrix.md</code> maps benchmark questions to tools or declines so behavior is testable, not vibes.</p>
  </div>

  <!-- ========== 8 ========== -->
  <h2>8. Appendix</h2>
  <h3>Canonical files</h3>
  <table>
    <thead><tr><th>Concern</th><th>Path</th></tr></thead>
    <tbody>
      <tr><td>Opportunity weights</td><td><code>backend/app/scoring/expansion_score.py</code></td></tr>
      <tr><td>Normalization</td><td><code>backend/app/scoring/normalization.py</code></td></tr>
      <tr><td>Demand / congestion / capacity / unmet demand</td><td><code>backend/app/analytics/*.py</code></td></tr>
      <tr><td>Universe build</td><td><code>backend/app/services/analysis_service.py</code></td></tr>
      <tr><td>Provider merge</td><td><code>backend/app/providers/base.py</code>, <code>fallback.py</code></td></tr>
      <tr><td>Provider wiring</td><td><code>backend/app/main.py</code> (lifespan)</td></tr>
      <tr><td>Orchestrator / SSE</td><td><code>backend/app/agent/orchestrator.py</code></td></tr>
      <tr><td>Tools</td><td><code>backend/app/agent/tools.py</code></td></tr>
      <tr><td>Prompts / guardrails</td><td><code>backend/app/agent/prompts.py</code>, <code>guardrails.py</code></td></tr>
      <tr><td>Architecture notes</td><td><code>docs/architecture.md</code>, <code>docs/CODEBASE_MAP.md</code></td></tr>
    </tbody>
  </table>

  <h3>Peer airports and REST regions</h3>
  <p><strong>Airports:</strong> BOS, BDL, PVD, PWM, LAX, SNA, ANC, SFO, JFK.</p>
  <table>
    <thead><tr><th>Region key</th><th>States used to filter the peer set</th></tr></thead>
    <tbody>
      <tr><td><code>new_england</code></td><td>ME, NH, VT, MA, RI, CT</td></tr>
      <tr><td><code>west_coast</code></td><td>WA, OR, CA</td></tr>
      <tr><td><code>alaska</code></td><td>AK</td></tr>
      <tr><td><code>northeast</code></td><td>NY, NJ, PA, CT, MA, RI</td></tr>
      <tr><td><code>california</code></td><td>CA</td></tr>
    </tbody>
  </table>

  <h3>Guardrails (short)</h3>
  <ul>
    <li>Data: missing stays missing; tool-grounded numbers; source transparency; deterministic scores; failures visible.</li>
    <li>Security: Pydantic validation; injection scan; read-only tools; HTTP timeouts and retries on providers.</li>
    <li>Voice: low-confidence transcripts confirm before send.</li>
    <li>Product: freshness warnings, proxy assumptions, HIGH/MEDIUM/LOW confidence, no investment guarantees, per-turn audit.</li>
  </ul>

  <p class="small">Regenerate this PDF with <code>uv run --with playwright scripts/build_system_design_pdf.py</code> after scoring or provider changes.</p>

</body>
</html>
"""


SHEET_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <style>
    body { font-family: "Segoe UI", Helvetica, Arial, sans-serif; margin: 0; padding: 28px 36px 40px; background: #fff; color: #0f172a; width: 1180px; }
    h1 { font-size: 26px; margin: 0 0 6px; }
    .sub { color: #475569; font-size: 14px; margin: 0 0 18px; }
    h2 { font-size: 16px; color: #0f766e; margin: 22px 0 8px; }
    table { border-collapse: collapse; width: 100%; font-size: 12.5px; }
    th, td { border: 1px solid #cbd5e1; padding: 7px 9px; text-align: left; vertical-align: top; }
    th { background: #f1f5f9; }
    code { font-family: Consolas, "Courier New", monospace; font-size: 11.5px; background: #f1f5f9; padding: 0 3px; }
    .diagram svg { width: 100%; height: auto; display: block; }
    .note { font-size: 12px; color: #64748b; margin-top: 8px; }
  </style>
</head>
<body>
  <div class="diagram">{{FLOW_SVG}}</div>
  <h2>HTTP APIs (this application)</h2>
  <table>
    <thead><tr><th>Method</th><th>Path</th><th>LLM?</th><th>Returns</th></tr></thead>
    <tbody>
      <tr><td>GET</td><td><code>/api/health</code></td><td>No</td><td>Liveness</td></tr>
      <tr><td>GET</td><td><code>/api/airports/{code}</code></td><td>No</td><td>Traffic and delay metrics + context</td></tr>
      <tr><td>GET</td><td><code>/api/airports/{code}/score</code></td><td>No</td><td>Expansion opportunity score</td></tr>
      <tr><td>GET</td><td><code>/api/airports/{code}/long-haul</code></td><td>No</td><td>BTS T-100 long-haul report</td></tr>
      <tr><td>POST</td><td><code>/api/airports/compare</code></td><td>No</td><td>Side-by-side comparison</td></tr>
      <tr><td>GET</td><td><code>/api/regions/{region}/ranking</code></td><td>No</td><td>Region ranking</td></tr>
      <tr><td>GET</td><td><code>/api/scoring/methodology</code></td><td>No</td><td>Canonical weights and rules</td></tr>
      <tr><td>POST</td><td><code>/api/chat</code></td><td>Yes</td><td>SSE: phase, meta, delta, done</td></tr>
      <tr><td>GET</td><td><code>/api/tts/status</code></td><td>No</td><td>TTS capability</td></tr>
      <tr><td>POST</td><td><code>/api/tts</code></td><td>Speech only</td><td>audio/mpeg</td></tr>
    </tbody>
  </table>
  <h2>Local data files (CSV / JSON / ZIP)</h2>
  <table>
    <thead><tr><th>File</th><th>Format</th><th>Used by</th><th>Supplies</th></tr></thead>
    <tbody>
      <tr><td><code>backend/data/airport_coords.csv</code></td><td>CSV</td><td>CoordinateLookup overlay</td><td>IATA/ICAO lat/lon for peers + long-haul destinations</td></tr>
      <tr><td><code>backend/data/ourairports_airports.csv</code></td><td>CSV</td><td>CoordinateLookup base</td><td>Global ICAO coordinates (OurAirports refresh script)</td></tr>
      <tr><td><code>backend/data/raw/bts/*.csv</code> or <code>.zip</code></td><td>CSV / ZIP</td><td>BtsT100FileProvider</td><td>T-100 performed departures, distance, dest</td></tr>
      <tr><td><code>backend/data/cache/faa_acais_enplanements.json</code></td><td>JSON</td><td>FaaAcaisFileProvider</td><td>Passenger volume (current + previous)</td></tr>
      <tr><td><code>backend/data/cache/faa_atads_operations.json</code></td><td>JSON</td><td>FaaAtadsFileProvider</td><td>Annual operations</td></tr>
      <tr><td><code>backend/data/cache/openflights_routes.json</code></td><td>JSON</td><td>OpenFlightsRoutesProvider</td><td>Route connectivity counts</td></tr>
      <tr><td><code>backend/data/sample_airports.json</code></td><td>JSON</td><td>SampleProvider</td><td>Labeled sample fallback metrics</td></tr>
    </tbody>
  </table>
  <p class="note">Live (not files): OpenSky, FAA NAS, NOAA METAR, OpenAI. Overlay coords win over OurAirports for the same ICAO.</p>
</body>
</html>
"""


def _inline_svg(path: Path) -> str:
    svg = path.read_text(encoding="utf-8")
    if "<svg" in svg:
        svg = svg.replace("<svg", "<svg style='max-width:100%;height:auto;display:block'", 1)
    return svg


async def build_pdf() -> None:
    if not SVG_PATH.exists():
        raise FileNotFoundError(f"System context diagram missing: {SVG_PATH}")
    if not FLOW_SVG_PATH.exists():
        raise FileNotFoundError(f"Flow diagram missing: {FLOW_SVG_PATH}")

    flow_svg = _inline_svg(FLOW_SVG_PATH)
    html = HTML_DOCUMENT.replace("{{FLOW_SVG}}", flow_svg).replace(
        "{{SVG}}", _inline_svg(SVG_PATH)
    )
    sheet = SHEET_HTML.replace("{{FLOW_SVG}}", flow_svg)

    print(f"Launching Playwright to generate PDF at {OUTPUT_PDF}...")
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html, wait_until="load")
        await page.pdf(
            path=str(OUTPUT_PDF),
            format="A4",
            print_background=True,
            display_header_footer=True,
            header_template=(
                '<div style="font-size:8px;color:#64748b;width:100%;padding:0 16mm;'
                'font-family:Segoe UI,Helvetica,sans-serif;">AirportIQ system design</div>'
            ),
            footer_template=(
                '<div style="font-size:8px;color:#64748b;width:100%;padding:0 16mm;'
                'font-family:Segoe UI,Helvetica,sans-serif;display:flex;justify-content:space-between;">'
                "<span>Confidential to the project — sourced from running code</span>"
                '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span>'
                "</div>"
            ),
            margin={"top": "18mm", "bottom": "18mm", "left": "16mm", "right": "16mm"},
        )

        img_page = await browser.new_page(viewport={"width": 1240, "height": 2200})
        await img_page.set_content(sheet, wait_until="load")
        await img_page.locator("body").screenshot(
            path=str(OUTPUT_PNG), type="png"
        )
        assets_png = ROOT_DIR / "docs" / "assets" / "airportiq-system-flow.png"
        await img_page.locator("body").screenshot(
            path=str(assets_png), type="png"
        )
        await browser.close()
    print(f"PDF generation complete.")
    print(f"Flow image written to {OUTPUT_PNG}")


if __name__ == "__main__":
    asyncio.run(build_pdf())
