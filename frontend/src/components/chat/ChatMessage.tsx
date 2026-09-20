import { Pause, Play, RotateCcw, Square } from "lucide-react";
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
import { cn } from "cn";
import { useState, useEffect } from "react";

interface BlockViewProps {
  block: Block;
  onSend?: (text: string) => void;
  isFirst?: boolean;
}

function BlockView({ block, onSend, isFirst }: BlockViewProps) {
  switch (block.kind) {
    case "text":
      return (
        <div className={cn("text-foreground", !isFirst && "mt-2")}>
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
  const {
    supported: ttsSupported,
    loading,
    playbackPhase,
    speak,
    pause,
    resume,
    restart,
    stop,
    cloudAvailable,
  } = useSpeechOutput();
  const [ttsError, setTtsError] = useState<string | null>(null);

  useEffect(() => {
    if (playbackPhase === "idle" || playbackPhase === "ended") {
      setTtsError(null);
    }
  }, [playbackPhase]);

  const fullReportText = blocksToSpeakableText(blocks);

  const handlePlayPause = async () => {
    if (playbackPhase === "playing") {
      pause();
      return;
    }
    if (playbackPhase === "paused") {
      await resume();
      return;
    }
    const result = await speak(fullReportText);
    if (!result.ok) {
      setTtsError(result.error);
    }
  };

  const handleRestart = () => {
    void restart();
  };

  const handleStop = () => {
    stop();
  };

  const hasSpeakableContent = blocks.length > 0 && blocks.some((b) => b.kind !== "confirmation");
  const showPlaybackControls =
    playbackPhase === "loading" || playbackPhase === "playing" || playbackPhase === "paused";

  const mainControlLabel =
    loading
      ? "Loading audio"
      : playbackPhase === "playing"
        ? "Pause report"
        : playbackPhase === "paused"
          ? "Resume report"
          : playbackPhase === "ended"
            ? "Play report again"
            : "Read full report";

  const showSpeakControl = ttsSupported && hasSpeakableContent;

  return (
    <div className={cn("relative flex flex-col gap-4", showSpeakControl && "pr-[7.5rem]")}>
      {showSpeakControl && (
        <div className="absolute right-0 top-0 z-10 flex flex-col items-end gap-1">
          {cloudAvailable === false && (
            <span className="text-[10px] text-ink-muted font-mono uppercase">Using browser voice</span>
          )}
          <div className="flex items-center gap-0.5">
            {showPlaybackControls && (
              <>
                <Button
                  type="button"
                  variant="outline"
                  size="icon-sm"
                  onClick={handleRestart}
                  disabled={loading}
                  aria-label="Restart report"
                  className="rounded-none"
                >
                  <RotateCcw size={14} />
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="icon-sm"
                  onClick={handleStop}
                  aria-label="Stop report"
                  className="rounded-none"
                >
                  <Square size={14} />
                </Button>
              </>
            )}
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              onClick={handlePlayPause}
              disabled={loading}
              aria-label={mainControlLabel}
              className="rounded-none"
            >
              {playbackPhase === "playing" ? <Pause size={14} /> : <Play size={14} />}
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
          isFirst={i === 0}
        />
      ))}
    </div>
  );
}
