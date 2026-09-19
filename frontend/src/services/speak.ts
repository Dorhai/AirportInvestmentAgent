import type { Block } from "@/types/chat";
import { formatAirportLabel } from "@/lib/airportDisplay";

/**
 * Prepares raw text for better TTS reading.
 * Strips markdown, normalizes numbers, and spaces out IATA codes.
 */
export function prepareTextForSpeech(raw: string): string {
  if (!raw) return "";

  let text = raw;

  // Strip markdown bold and italic
  text = text.replace(/\*\*(.*?)\*\*/g, "$1");
  text = text.replace(/\*(.*?)\*/g, "$1");
  // Strip markdown headers
  text = text.replace(/(?:^|\s)#+\s+/g, " ");
  // Strip markdown bullets
  text = text.replace(/(?:^|\n)[-*]\s+/g, " ");
  
  // Convert 3-4 letter uppercase tokens (likely IATA/ICAO) to spaced letters
  // e.g. " BOS " -> " B O S "
  text = text.replace(/\b([A-Z]{3,4})\b/g, (match) => {
    return match.split("").join(" ");
  });

  // Normalize numbers e.g., 72.4% -> 72 point 4 percent, 75.5 -> 75 point 5
  text = text.replace(/(\d+)\.(\d+)(%?)/g, (_match, p1, p2, p3) => {
    return `${p1} point ${p2}${p3 ? " percent" : ""}`;
  });
  text = text.replace(/(\d+)%/g, "$1 percent");

  // Collapse multiple whitespaces
  text = text.replace(/\s+/g, " ").trim();

  return text;
}

/**
 * Splits text into chunks at sentence boundaries, aiming for length <= maxLen.
 * Useful for browser speech synthesis which can truncate long utterances.
 */
export function chunkForSpeech(text: string, maxLen: number = 250): string[] {
  const sentences = text.match(/[^.!?]+[.!?]+(?:\s|$)|[^.!?]+$/g) || [];
  const chunks: string[] = [];
  let currentChunk = "";

  for (const sentence of sentences) {
    if ((currentChunk.length + sentence.length) > maxLen && currentChunk.length > 0) {
      chunks.push(currentChunk.trim());
      currentChunk = "";
    }
    currentChunk += sentence;
  }
  if (currentChunk.trim().length > 0) {
    chunks.push(currentChunk.trim());
  }

  return chunks;
}

/**
 * Converts an array of chat Blocks into a single speakable script.
 */
export function blocksToSpeakableText(blocks: Block[]): string {
  const parts: string[] = [];

  for (const block of blocks) {
    switch (block.kind) {
      case "text":
        parts.push(prepareTextForSpeech(block.text));
        break;
      case "score_card": {
        let summary = `Score card for ${formatAirportLabel(block.score.airport_code, block.score.airport_name)}. `;
        const opp = block.score.opportunity_score;
        if (opp?.kind === "present") {
          summary += `Opportunity score is ${opp.value}. `;
        }
        const cong = block.score.congestion_score;
        if (cong?.kind === "present") {
          summary += `Congestion score is ${cong.value}.`;
        }
        parts.push(prepareTextForSpeech(summary));
        break;
      }
      case "comparison": {
        const rowLabel = (code: string, name?: string) =>
          formatAirportLabel(code, name);
        let summary = `Comparison between ${block.rows.map((r) => rowLabel(r.airport_code, r.score.airport_name)).join(" and ")}. `;
        if (block.highestOpportunity) {
          const top = block.rows.find((r) => r.airport_code === block.highestOpportunity);
          summary += `Highest opportunity is at ${top ? rowLabel(top.airport_code, top.score.airport_name) : block.highestOpportunity}. `;
        }
        if (block.highestCongestion) {
          const top = block.rows.find((r) => r.airport_code === block.highestCongestion);
          summary += `Highest congestion is at ${top ? rowLabel(top.airport_code, top.score.airport_name) : block.highestCongestion}.`;
        }
        parts.push(prepareTextForSpeech(summary));
        break;
      }
      case "ranking": {
        const top = block.ranked
          .slice(0, 3)
          .map((r) => formatAirportLabel(r.airport_code, r.airport_name))
          .join(", ");
        parts.push(prepareTextForSpeech(`Top airports in ${block.region.replace(/_/g, " ")} are ${top}.`));
        break;
      }
      case "simulation": {
        let summary = `Simulation: Baseline opportunity was ${block.baseline.opportunity_score.kind === "present" ? block.baseline.opportunity_score.value : "unknown"}. `;
        summary += `Simulated opportunity is ${block.simulated.opportunity_score.kind === "present" ? block.simulated.opportunity_score.value : "unknown"}.`;
        parts.push(prepareTextForSpeech(summary));
        break;
      }
      case "kpi": {
        const val = block.datum.kind === "present" ? block.datum.value : "unknown";
        parts.push(prepareTextForSpeech(`${block.label} is ${val}.`));
        break;
      }
      case "warnings": {
        parts.push(prepareTextForSpeech(`Warnings: ${block.warnings.join(". ")}`));
        break;
      }
      case "confirmation":
      case "metrics_inputs":
      case "component_breakdown":
        // skip or not relevant for short speakable summary
        break;
    }
  }

  return parts.join("\n\n");
}
