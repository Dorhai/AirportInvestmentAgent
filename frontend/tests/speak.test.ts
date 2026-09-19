import { describe, it, expect } from "vitest";
import { prepareTextForSpeech, chunkForSpeech, blocksToSpeakableText } from "@/services/speak";
import type { Block } from "@/types/chat";
import { mockAirportScore, present } from "./fixtures";

describe("speak service", () => {
  describe("prepareTextForSpeech", () => {
    it("strips markdown formatting", () => {
      const input = "**Bold** and *italic* and # Header\n- Bullet";
      expect(prepareTextForSpeech(input)).toBe("Bold and italic and Header Bullet");
    });

    it("expands IATA codes", () => {
      const input = "Flights from BOS to LAX are delayed. Also ABCD code.";
      expect(prepareTextForSpeech(input)).toBe("Flights from B O S to L A X are delayed. Also A B C D code.");
    });

    it("normalizes percentages", () => {
      const input = "Growth is 72.4% but could be 50%.";
      expect(prepareTextForSpeech(input)).toBe("Growth is 72 point 4 percent but could be 50 percent.");
    });
  });

  describe("chunkForSpeech", () => {
    it("chunks text by sentences", () => {
      const text = "This is sentence one. This is sentence two! And three?";
      const chunks = chunkForSpeech(text, 25);
      expect(chunks).toEqual([
        "This is sentence one.",
        "This is sentence two!",
        "And three?"
      ]);
    });
    
    it("keeps chunks under max length if possible", () => {
      const text = "Short. Short. Short. Short.";
      const chunks = chunkForSpeech(text, 15);
      expect(chunks).toEqual([
        "Short. Short.",
        "Short. Short."
      ]);
    });
  });

  describe("blocksToSpeakableText", () => {
    it("converts mixed blocks to speakable text", () => {
      const blocks: Block[] = [
        { kind: "text", text: "Here is the **summary**." },
        {
          kind: "score_card",
          score: mockAirportScore({
            opportunity_score: present(75.5),
            congestion_score: present(80),
          }),
        },
        {
          kind: "confirmation",
          confirmation: { prompt: "Confirm?", options: [] }
        },
        {
          kind: "warnings",
          warnings: ["Data is old"]
        }
      ];

      const script = blocksToSpeakableText(blocks);
      expect(script).toContain("Here is the summary.");
      expect(script).toContain(
        "Score card for General Edward Lawrence Logan International Airport (B O S). Opportunity score is 75 point 5. Congestion score is 80.",
      );
      expect(script).toContain("Warnings: Data is old");
      expect(script).not.toContain("Confirm?");
    });
  });
});
