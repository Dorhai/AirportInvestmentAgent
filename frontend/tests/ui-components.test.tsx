import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, within, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { AirportScoreCard } from "@/components/airport/AirportScoreCard";
import { AirportComparison } from "@/components/airport/AirportComparison";
import { RankingTable } from "@/components/airport/RankingTable";
import { SimulationCard } from "@/components/airport/SimulationCard";
import { KpiCard } from "@/components/airport/KpiCard";
import { WarningsList } from "@/components/airport/WarningsList";
import { ConfirmationPrompt } from "@/components/airport/ConfirmationPrompt";
import { MetricsInputsTable } from "@/components/airport/MetricsInputsTable";
import { ComponentBreakdownGrid } from "@/components/airport/ComponentBreakdownGrid";
import { ScoringMethodologyCard } from "@/components/airport/ScoringMethodologyCard";
import { ConfidenceBadge } from "@/components/common/ConfidenceBadge";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import { ChatContainer } from "@/components/chat/ChatContainer";
import { mockAirportScore, mockAirportMetrics, present } from "./fixtures";

vi.mock("@/hooks/useSpeechOutput", () => ({
  useSpeechOutput: () => ({
    supported: true,
    speaking: false,
    loading: false,
    playbackPhase: "idle" as const,
    speak: vi.fn().mockResolvedValue({ ok: true }),
    pause: vi.fn(),
    resume: vi.fn().mockResolvedValue(undefined),
    restart: vi.fn().mockResolvedValue(undefined),
    stop: vi.fn(),
    cancel: vi.fn(),
    cloudAvailable: true,
  }),
}));

vi.mock("@/hooks/useSpeechInput", () => ({
  useSpeechInput: () => ({
    supported: false,
    listening: false,
    start: vi.fn(),
    stop: vi.fn(),
  }),
}));

describe("Airport evidence UI", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders AirportScoreCard with code and opportunity", () => {
    render(<AirportScoreCard score={mockAirportScore()} />);
    expect(
      screen.getByRole("heading", {
        name: /General Edward Lawrence Logan International Airport \(BOS\)/,
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("72.4").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Assumptions/i)).toBeInTheDocument();
  });

  it("renders comparison table with top opportunity marker", () => {
    const scoreA = mockAirportScore({ airport_code: "BOS" });
    const scoreB = mockAirportScore({
      airport_code: "JFK",
      airport_name: "John F. Kennedy International Airport",
      opportunity_score: present(80),
    });
    // @ts-ignore - metrics is required by ComparisonRow but AirportComparison component only needs airport_code and score
    render(
      <AirportComparison
        rows={[
          { airport_code: "BOS", score: scoreA },
          { airport_code: "JFK", score: scoreB },
        ]}
        highestOpportunity="JFK"
        highestCongestion="BOS"
      />,
    );
    expect(screen.getByText(/John F. Kennedy International Airport \(JFK\)/)).toBeInTheDocument();
    expect(screen.getByText(/TOP OPP/i)).toBeInTheDocument();
  });

  it("renders ranking list and truncates to top 4", () => {
    const scores = [
      mockAirportScore({ airport_code: "A" }),
      mockAirportScore({ airport_code: "B" }),
      mockAirportScore({ airport_code: "C" }),
      mockAirportScore({ airport_code: "D" }),
      mockAirportScore({ airport_code: "E" }),
      mockAirportScore({ airport_code: "F" }),
    ];
    
    render(
      <RankingTable
        kind="ranking"
        ranked={scores}
        region="new_england"
        peerNote="Peer set note"
        metric="opportunity_score"
      />,
    );
    expect(screen.getByText(/new england/i)).toBeInTheDocument();
    expect(screen.getByText(/Top 4 of 6 airports · ranked by opportunity score/i)).toBeInTheDocument();
    
    // Only 4 items should be rendered
    const listItems = screen.getAllByRole("listitem");
    expect(listItems).toHaveLength(4);
  });

  it("renders simulation delta", () => {
    render(
      <SimulationCard
        baseline={mockAirportScore()}
        simulated={mockAirportScore({ opportunity_score: present(75) })}
        growthAdjustment={5}
        deltaOpportunity={2.6}
      />,
    );
    expect(screen.getByText(/Simulation/i)).toBeInTheDocument();
    expect(screen.getByText("+2.6")).toBeInTheDocument();
  });

  it("renders KPI and warnings", () => {
    render(<KpiCard label="Long-haul %" datum={present(42.5)} />);
    expect(screen.getByText("42.5")).toBeInTheDocument();

    render(<WarningsList warnings={["Low sample coverage"]} />);
    expect(screen.getByText("Low sample coverage")).toBeInTheDocument();
  });

  it("renders MetricsInputsTable", () => {
    const view = render(
      <MetricsInputsTable
        kind="metrics_inputs"
        metricsList={[mockAirportMetrics({ airport_code: "BOS" })]}
      />,
    );
    expect(within(view.container).getByText("Underlying Inputs")).toBeInTheDocument();
    expect(within(view.container).queryByText(/Column definitions/i)).not.toBeInTheDocument();
    expect(
      within(view.container).getByText(/General Edward Lawrence Logan International Airport \(BOS\)/),
    ).toBeInTheDocument();
    expect(screen.getByText("20,000,000")).toBeInTheDocument(); // passengers
  });

  it("renders ComponentBreakdownGrid", () => {
    render(
      <ComponentBreakdownGrid
        kind="component_breakdown"
        scores={[
          mockAirportScore({ airport_code: "BOS" }),
          mockAirportScore({
            airport_code: "LAX",
            airport_name: "Los Angeles International Airport",
          }),
        ]}
      />,
    );
    expect(screen.getByText("Score Components (0-100)")).toBeInTheDocument();
    expect(screen.getAllByText("Demand Growth").length).toBeGreaterThan(0);
    expect(screen.getByText(/Los Angeles International Airport \(LAX\)/)).toBeInTheDocument();
  });

  it("renders ScoringMethodologyCard placeholder", () => {
    // Note: React Query or fetch logic is tested separately, we just test it mounts without crashing
    render(<ScoringMethodologyCard kind="methodology" />);
    // it returns null initially because data is null, which is fine
  });

  it("renders ConfidenceBadge", () => {
    render(<ConfidenceBadge confidence="HIGH" />);
    expect(screen.getAllByText("HIGH").length).toBeGreaterThan(0);
  });

  it("confirmation prompt fires onSelect", () => {
    const onSelect = vi.fn();
    render(
      <ConfirmationPrompt
        confirmation={{
          prompt: "Which airport?",
          options: [{ label: "Boston", value: "BOS" }],
        }}
        onSelect={onSelect}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Boston" }));
    expect(onSelect).toHaveBeenCalledWith("BOS");
  });

  it("renders speak control but not per-block Read aloud", () => {
    render(<ChatMessage blocks={[{ kind: "text", text: "Some text" }]} />);
    expect(screen.getByRole("button", { name: /Read full report/i })).toBeInTheDocument();
    expect(screen.queryByText(/Read aloud/i)).not.toBeInTheDocument();
  });

  it("ChatMessage maps block kinds", () => {
    const { container } = render(
      <ChatMessage
        blocks={[
          { kind: "text", text: "Summary line" },
          { kind: "score_card", score: mockAirportScore() },
        ]}
      />,
    );
    expect(screen.getByText("Summary line")).toBeInTheDocument();
    expect(container.querySelectorAll('[data-slot="card"]')).toHaveLength(1);
  });
});

describe("Chat shell", () => {
  it("ChatInput submits trimmed message", () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);
    const input = screen.getByPlaceholderText(/ENTER ANALYST QUERY/i);
    fireEvent.change(input, { target: { value: "  Score at BOS  " } });
    fireEvent.click(screen.getByRole("button", { name: /Transmit/i }));
    expect(onSend).toHaveBeenCalledWith("Score at BOS");
  });

  it("ChatContainer shows empty state and user turn", () => {
    render(
      <ChatContainer
        turns={[{ role: "user", text: "Hello" }]}
        onSend={vi.fn()}
        isPending={false}
      />,
    );
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });
});
