import { useEffect, useRef } from "react";
import type { Turn } from "@/types/chat";
import { presentResponse } from "@/services/present";
import { ChatMessage } from "./ChatMessage";
import { ChatInput } from "./ChatInput";

interface ChatContainerProps {
  turns: Turn[];
  onSend: (text: string, confidence?: number) => void;
  isPending: boolean;
}

export function ChatContainer({ turns, onSend, isPending }: ChatContainerProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const top = container.scrollHeight;
    if (typeof container.scrollTo === "function") {
      container.scrollTo({ top, behavior: "smooth" });
    } else {
      container.scrollTop = top;
    }
  }, [turns, isPending]);

  return (
    <div className="flex h-full flex-col">
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto p-4 md:p-6 bg-paper"
      >
        <div className="mx-auto flex max-w-4xl flex-col gap-8">
          {turns.length === 0 && (
            <div className="text-center py-12 text-ink-muted font-mono text-sm">
              <p>AWAITING INPUT</p>
              <p className="mt-2 text-xs">Query intelligence system for airport pressure and expansion opportunity.</p>
            </div>
          )}
          
          {turns.map((turn, i) => (
            <div key={i} className="flex flex-col gap-2">
              {turn.role === "user" ? (
                <div className="border-l-2 border-ink pl-4 py-1">
                  <p className="text-ink font-mono text-sm whitespace-pre-wrap">{turn.text}</p>
                </div>
              ) : (
                <div className="border border-hairline bg-white p-4 shadow-sm">
                  {turn.response ? (
                    <ChatMessage
                      blocks={presentResponse(turn.response)}
                      onSend={onSend}
                    />
                  ) : (
                    <p className="text-ink whitespace-pre-wrap mt-2">{turn.text}</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
      
      <div className="border-t border-hairline bg-white p-4 md:px-6 md:py-4 shadow-[0_-4px_6px_-2px_rgba(0,0,0,0.02)]">
        <div className="mx-auto max-w-4xl">
          <ChatInput onSend={onSend} disabled={isPending} />
        </div>
      </div>
    </div>
  );
}
