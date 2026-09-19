import { type FormEvent, useCallback, useState } from "react";
import { Mic, MicOff } from "lucide-react";
import { useSpeechInput } from "@/hooks/useSpeechInput";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const VOICE_CONFIDENCE_THRESHOLD = 0.6;

interface ChatInputProps {
  onSend: (text: string, confidence?: number) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const [voiceError, setVoiceError] = useState<string | null>(null);

  const handleVoiceResult = useCallback(
    (transcript: string, confidence: number) => {
      const hasReliableConfidence = confidence > 0;
      if (hasReliableConfidence && confidence >= VOICE_CONFIDENCE_THRESHOLD) {
        onSend(transcript, confidence);
        setValue("");
      } else {
        setValue(transcript);
      }
    },
    [onSend],
  );

  const { supported: micSupported, listening, start, stop } = useSpeechInput({
    onResult: handleVoiceResult,
    onInterim: setValue,
    onError: setVoiceError,
  });

  function toggleRecording() {
    if (listening) {
      stop();
      return;
    }
    setVoiceError(null);
    start();
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setValue("");
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <div className="flex gap-2">
        <Input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="ENTER ANALYST QUERY..."
          disabled={disabled}
          className="flex-1 rounded-none font-mono text-sm shadow-none"
        />
        {micSupported && (
          <Button
            type="button"
            variant={listening ? "destructive" : "outline"}
            size="icon"
            onClick={toggleRecording}
            disabled={disabled}
            aria-label={listening ? "Stop recording" : "Start recording"}
            aria-pressed={listening}
            className="rounded-none shrink-0"
          >
            {listening ? <MicOff size={16} /> : <Mic size={16} />}
          </Button>
        )}
        <Button
          type="submit"
          disabled={disabled || !value.trim()}
          className="rounded-none px-6 font-bold uppercase tracking-wider"
        >
          Transmit
        </Button>
      </div>
      {voiceError && (
        <p className="text-xs font-mono text-destructive" role="alert">
          {voiceError}
        </p>
      )}
      {listening && (
        <p className="text-xs font-mono text-ink-muted">Listening… click mic to finish.</p>
      )}
    </form>
  );
}
