import { useCallback, useState } from "react";
import { streamChat } from "@/services/api";
import type { ChatResponse, Turn } from "@/types/chat";

export function useChat(conversationId: string) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [isPending, setIsPending] = useState(false);
  const [streamingPhase, setStreamingPhase] = useState<string | null>(null);

  const send = useCallback(
    async (text: string, confidence?: number) => {
      setIsPending(true);
      setStreamingPhase("tool_select");
      setTurns((prev) => [...prev, { role: "user", text }]);

      try {
        await streamChat(text, conversationId, confidence, (event, data) => {
          if (event === "phase") {
            setStreamingPhase(data.step);
          } else if (event === "done") {
            const response = data as ChatResponse;
            setTurns((prev) => [
              ...prev,
              {
                role: "assistant",
                text: response.message,
                response,
              },
            ]);
            setIsPending(false);
            setStreamingPhase(null);
          } else if (event === "error") {
            console.error("Chat error:", data.detail);
            setIsPending(false);
            setStreamingPhase(null);
          }
        });
      } catch (err) {
        console.error("Stream failed", err);
      } finally {
        setIsPending(false);
        setStreamingPhase(null);
      }
    },
    [conversationId],
  );

  return { turns, send, isPending, streamingPhase } as const;
}
