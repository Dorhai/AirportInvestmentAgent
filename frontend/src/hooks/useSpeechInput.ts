import { useCallback, useEffect, useRef, useState } from "react";

interface SpeechInputOptions {
  onResult: (transcript: string, confidence: number) => void;
  onInterim?: (transcript: string) => void;
  onError?: (message: string) => void;
}

const SpeechRecognition =
  typeof window !== "undefined"
    ? window.SpeechRecognition ?? window.webkitSpeechRecognition
    : undefined;

const ERROR_MESSAGES: Record<string, string> = {
  "not-allowed": "Microphone access denied. Allow microphone use in your browser settings.",
  "no-speech": "No speech detected. Try speaking again.",
  network: "Speech recognition could not reach the network service.",
  "audio-capture": "No microphone found or it is in use by another app.",
};

export function useSpeechInput({ onResult, onInterim, onError }: SpeechInputOptions) {
  const supported = !!SpeechRecognition;
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<InstanceType<typeof SpeechRecognition> | null>(
    null,
  );
  const isListeningRef = useRef(false);
  const accumulatedRef = useRef("");
  const onResultRef = useRef(onResult);
  const onInterimRef = useRef(onInterim);
  const onErrorRef = useRef(onError);
  onResultRef.current = onResult;
  onInterimRef.current = onInterim;
  onErrorRef.current = onError;

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
      isListeningRef.current = false;
    };
  }, []);

  const start = useCallback(() => {
    if (!SpeechRecognition || isListeningRef.current) return;

    accumulatedRef.current = "";

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = "en-US";
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;

      recognition.onresult = (event: SpeechRecognitionEvent) => {
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const chunk = event.results[i];
          const text = chunk[0]?.transcript ?? "";
          if (chunk.isFinal) {
            accumulatedRef.current += text;
          } else {
            interim += text;
          }
        }
        const preview = (accumulatedRef.current + interim).trim();
        if (preview) {
          onInterimRef.current?.(preview);
        }
      };

      recognition.onend = () => {
        isListeningRef.current = false;
        setListening(false);
        recognitionRef.current = null;

        const transcript = accumulatedRef.current.trim();
        if (transcript) {
          onResultRef.current(transcript, 0);
        }
      };

      recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
        if (event.error === "aborted") return;

        isListeningRef.current = false;
        setListening(false);
        recognitionRef.current = null;

        const message =
          ERROR_MESSAGES[event.error] ?? "Speech recognition failed. Try again.";
        onErrorRef.current?.(message);
      };

      recognitionRef.current = recognition;
      recognition.start();
      isListeningRef.current = true;
      setListening(true);
    } catch {
      isListeningRef.current = false;
      setListening(false);
      onErrorRef.current?.("Could not start speech recognition.");
    }
  }, []);

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
  }, []);

  return { supported, listening, start, stop } as const;
}
