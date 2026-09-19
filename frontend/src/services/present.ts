import type { Block, ChatResponse, EvidenceItem } from "@/types/chat";

function blockFromEvidence(ev: EvidenceItem): Block[] {
  const blocks: Block[] = [];
  const kind = (ev as { kind: string }).kind;
  if (
    kind === "congestion_explain" ||
    kind === "unmet_explain" ||
    kind === "capacity_explain"
  ) {
    return blocks;
  }

  switch (ev.kind) {
    case "score":
      blocks.push({ kind: "score_card", score: ev.score });
      break;

    case "comparison":
      blocks.push({
        kind: "comparison",
        rows: ev.rows,
        highestCongestion: ev.highest_congestion,
        highestOpportunity: ev.highest_opportunity_score,
      });
      break;

    case "ranking":
      blocks.push({
        kind: "ranking",
        ranked: ev.ranked,
        region: ev.region,
        peerNote: ev.peer_note,
        metric: ev.metric ?? "opportunity_score",
      });
      break;

    case "simulation":
      blocks.push({
        kind: "simulation",
        baseline: ev.baseline_score,
        simulated: ev.simulated_score,
        growthAdjustment: ev.growth_adjustment,
        deltaOpportunity: ev.delta_opportunity,
      });
      break;

    case "long_haul":
      // No dedicated UI — long-haul is explained in prose.
      break;

    case "unmet_demand":
      // No dedicated UI — unmet demand is explained in prose; use rank/compare for tables.
      break;

    case "metrics":
      blocks.push({
        kind: "metrics_inputs",
        metricsList: [ev.metrics],
      });
      break;

    case "rejection":
      break;
  }
  
  return blocks;
}

export function presentResponse(res: ChatResponse): Block[] {
  const blocks: Block[] = [];

  if (res.message) {
    blocks.push({ kind: "text", text: res.message });
  }

  if (res.needs_confirmation) {
    blocks.push({ kind: "confirmation", confirmation: res.needs_confirmation });
    return blocks;
  }

  let showMethodology = false;
  const rawBlocks: Block[] = [];
  for (const ev of res.evidence) {
    if (ev.kind === "score" || ev.kind === "simulation") {
      showMethodology = true;
    }
    rawBlocks.push(...blockFromEvidence(ev));
  }

  for (const b of rawBlocks) {
    if (b.kind === "metrics_inputs" && blocks.length > 0) {
      const last = blocks[blocks.length - 1];
      if (last.kind === "metrics_inputs") {
        last.metricsList.push(...b.metricsList);
        continue;
      }
    }
    blocks.push(b);
  }

  if (showMethodology) {
    blocks.push({ kind: "methodology" });
  }

  return blocks;
}
