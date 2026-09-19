import type { AirportScore } from "@/types/chat";
import type { components } from "@/types/api.generated";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function unwrapError(res: Response): Promise<never> {
  let message = `Request failed (${res.status})`;
  try {
    const body: unknown = await res.json();
    if (body && typeof body === "object" && "detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      if (typeof detail === "string") {
        message = detail;
      } else if (Array.isArray(detail)) {
        message = detail.join("; ");
      }
    }
  } catch {
    // body was not JSON, keep default message
  }
  throw new ApiError(res.status, message);
}

export async function streamChat(
  message: string,
  conversationId: string,
  speechConfidence: number | undefined,
  onEvent: (event: string, data: any) => void
): Promise<void> {
  const res = await fetch(`${BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      voice_confidence: speechConfidence ?? null,
    }),
  });
  if (!res.ok) await unwrapError(res);
  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      
      let event = "message";
      let dataStr = "";
      
      const lines = block.split("\n");
      for (const line of lines) {
        if (line.startsWith("event: ")) {
          event = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          dataStr = line.slice(6).trim();
        }
      }
      
      if (dataStr) {
        try {
          const data = JSON.parse(dataStr);
          onEvent(event, data);
        } catch (e) {
          console.error("Failed to parse SSE data", e);
        }
      }
      
      boundary = buffer.indexOf("\n\n");
    }
  }
}

export async function fetchScore(code: string): Promise<AirportScore> {
  const res = await fetch(`${BASE}/api/airports/${encodeURIComponent(code)}/score`);
  if (!res.ok) await unwrapError(res);
  return (await res.json()) as AirportScore;
}

export async function getScoringMethodology(): Promise<components["schemas"]["ScoringMethodology"]> {
  const res = await fetch(`${BASE}/api/scoring/methodology`);
  if (!res.ok) await unwrapError(res);
  return res.json();
}

export async function fetchTtsStatus(): Promise<{ available: boolean, provider: string | null, voice: string }> {
  try {
    const res = await fetch(`${BASE}/api/tts/status`);
    if (!res.ok) return { available: false, provider: null, voice: "" };
    return await res.json();
  } catch {
    return { available: false, provider: null, voice: "" };
  }
}

export async function fetchTtsAudio(text: string): Promise<Blob> {
  const res = await fetch(`${BASE}/api/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) await unwrapError(res);
  return await res.blob();
}

export { ApiError };
