import { Volume2 } from "lucide-react";
import type { Block } from "@/types/chat";
import { AirportScoreCard } from "@/components/airport/AirportScoreCard";
import { AirportComparison } from "@/components/airport/AirportComparison";
import { RankingTable } from "@/components/airport/RankingTable";
import { SimulationCard } from "@/components/airport/SimulationCard";
import { KpiCard } from "@/components/airport/KpiCard";
import { ConfirmationPrompt } from "@/components/airport/ConfirmationPrompt";
import { WarningsList } from "@/components/airport/WarningsList";
import { MetricsInputsTable } from "@/components/airport/MetricsInputsTable";
import { ComponentBreakdownGrid } from "@/components/airport/ComponentBreakdownGrid";
import { ScoringMethodologyCard } from "@/components/airport/ScoringMethodologyCard";
import { useSpeechOutput } from "@/hooks/useSpeechOutput";
import { blocksToSpeakableText } from "@/services/speak";
import { Button } from "@/components/ui/button";
import { useState, useEffect } from "react";

interface BlockViewProps {
  block: Block;
  onSend?: (text: string) => void;
}

function BlockView({ block, onSend }: BlockViewProps) {
  switch (block.kind) {
    case "text":
      return (
        <div className="mt-2 text-foreground">
          <p className="whitespace-pre-wrap">{block.text}</p>
        </div>
      );
    case "score_card":
      return <AirportScoreCard {...block} />;
    case "comparison":
      return <AirportComparison {...block} />;
    case "ranking":
      return <RankingTable {...block} />;
    case "simulation":
      return <SimulationCard {...block} />;
    case "kpi":
      return <KpiCard {...block} />;
    case "metrics_inputs":
      return <MetricsInputsTable {...block} />;
    case "component_breakdown":
      return <ComponentBreakdownGrid {...block} />;
    case "methodology":
      return <ScoringMethodologyCard {...block} />;
    case "confirmation":
      return <ConfirmationPrompt {...block} onSelect={onSend} />;
    case "warnings":
      return <WarningsList {...block} />;
  }
}

interface ChatMessageProps {
  blocks: Block[];
  onSend?: (text: string) => void;
}

export function ChatMessage({ blocks, onSend }: ChatMessageProps) {
  const { supported: ttsSupported, speaking, loading, speak, cloudAvailable } = useSpeechOutput();
  const [ttsError, setTtsError] = useState<string | null>(null);

  useEffect(() => {
    if (!speaking && !loading) {
      setTtsError(null);
    }
  }, [speaking, loading]);

  const handleSpeak = async () => {
    const fullReportText = blocksToSpeakableText(blocks);
    const result = await speak(fullReportText);
    if (!result.ok) {
      setTtsError(result.error);
    }
  };

  const hasSpeakableContent = blocks.length > 0 && blocks.some(b => b.kind !== "confirmation");

  return (
    <div className="flex flex-col gap-4 pt-1">
      {ttsSupported && hasSpeakableContent && (
        <div className="flex flex-col items-end gap-1">
          <div className="flex items-center gap-2">
            {cloudAvailable === false && (
              <span className="text-[10px] text-ink-muted font-mono uppercase">Using browser voice</span>
            )}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleSpeak}
              disabled={speaking || loading}
              aria-label="Read full report"
              className="rounded-none font-mono text-xs uppercase"
            >
              <Volume2 size={14} />
              {loading ? "Loading audio..." : speaking ? "Reading..." : "Read full report"}
            </Button>
          </div>
          {ttsError && (
            <span className="text-[10px] text-red font-mono uppercase">{ttsError}</span>
          )}
        </div>
      )}
      
      {blocks.map((block, i) => (
        <BlockView 
          key={i} 
          block={block} 
          onSend={onSend}
        />
      ))}
    </div>
  );
}
