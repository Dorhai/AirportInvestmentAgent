import { useCallback, useState } from "react";
import { streamChat } from "@/services/api";
import type { ChatResponse, Turn } from "@/types/chat";

export function useChat(conversationId: string) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [isPending, setIsPending] = useState(false);

  const send = useCallback(
    async (text: string, confidence?: number) => {
      setIsPending(true);
      setTurns((prev) => [...prev, { role: "user", text }]);

      try {
        await streamChat(text, conversationId, confidence, (event, data) => {
          if (event === "done") {
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
          } else if (event === "error") {
            console.error("Chat error:", data.detail);
            setIsPending(false);
          }
        });
      } catch (err) {
        console.error("Stream failed", err);
      } finally {
        setIsPending(false);
      }
    },
    [conversationId],
  );

  return { turns, send, isPending } as const;
}
