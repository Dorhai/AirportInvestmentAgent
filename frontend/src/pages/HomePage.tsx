import { useEffect, useState } from "react";
import { useChat } from "@/hooks/useChat";
import { ChatContainer } from "@/components/chat/ChatContainer";

function getTabConversationId(): string {
  if (typeof window === "undefined") return "default";
  let id = sessionStorage.getItem("conversation_id");
  if (!id) {
    id = "tab-" + Math.random().toString(36).slice(2, 9);
    sessionStorage.setItem("conversation_id", id);
  }
  return id;
}

export function HomePage() {
  const [conversationId, setConversationId] = useState("default");

  useEffect(() => {
    setConversationId(getTabConversationId());
  }, []);

  const { turns, send, isPending } = useChat(conversationId);
  return <ChatContainer turns={turns} onSend={send} isPending={isPending} />;
}
