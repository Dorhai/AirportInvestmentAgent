import { useCallback, useEffect, useRef, useState } from "react";
import { prepareTextForSpeech, chunkForSpeech } from "@/services/speak";
import { fetchTtsStatus, fetchTtsAudio } from "@/services/api";
import { tryAcquireSpeechLock, releaseSpeechLock } from "@/lib/speechSession";

export type SpeakResult = { ok: true } | { ok: false; error: string };

export type PlaybackPhase = "idle" | "loading" | "playing" | "paused" | "ended";

const synth =
  typeof window !== "undefined" ? window.speechSynthesis : undefined;

function pickPreferredVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  if (!voices.length) return null;
  const enVoices = voices.filter((v) => v.lang.startsWith("en"));
  const pool = enVoices.length > 0 ? enVoices : voices;

  const preferred = pool.find((v) =>
    /natural|neural|google|jenny|guy|aria|microsoft/i.test(v.name),
  );
  if (preferred) return preferred;

  const online = pool.find((v) => !v.localService);
  if (online) return online;

  return pool[0] ?? null;
}

export function useSpeechOutput() {
  const supported = !!synth;
  const [playbackPhase, setPlaybackPhase] = useState<PlaybackPhase>("idle");
  const [loading, setLoading] = useState(false);
  const [cloudAvailable, setCloudAvailable] = useState<boolean | null>(null);

  const voicesRef = useRef<SpeechSynthesisVoice[]>([]);
  const queueRef = useRef<string[]>([]);
  const activeUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const activeAudioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const lastTextRef = useRef<string | null>(null);
  const lastPreparedRef = useRef<string | null>(null);
  const sessionGenRef = useRef(0);
  const playbackPhaseRef = useRef<PlaybackPhase>("idle");

  const setPhase = useCallback((phase: PlaybackPhase) => {
    playbackPhaseRef.current = phase;
    setPlaybackPhase(phase);
  }, []);

  const speaking = playbackPhase === "playing";

  useEffect(() => {
    fetchTtsStatus().then((status) => {
      setCloudAvailable(status.available);
    });
  }, []);

  useEffect(() => {
    if (!synth) return;
    const loadVoices = () => {
      voicesRef.current = synth.getVoices();
    };
    loadVoices();
    if (synth.onvoiceschanged !== undefined) {
      synth.onvoiceschanged = loadVoices;
    }
  }, []);

  const cleanupMedia = useCallback(() => {
    synth?.cancel();
    if (activeAudioRef.current) {
      activeAudioRef.current.pause();
      activeAudioRef.current = null;
    }
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    queueRef.current = [];
    activeUtteranceRef.current = null;
  }, []);

  const finishPlayback = useCallback(() => {
    cleanupMedia();
    setLoading(false);
    setPhase("ended");
    releaseSpeechLock();
  }, [cleanupMedia, setPhase]);

  const playNextChunk = useCallback(() => {
    if (!synth) return;
    const chunk = queueRef.current.shift();
    if (!chunk) {
      finishPlayback();
      return;
    }

    const utterance = new SpeechSynthesisUtterance(chunk);
    activeUtteranceRef.current = utterance;

    const voice = pickPreferredVoice(voicesRef.current);
    if (voice) utterance.voice = voice;
    utterance.rate = 0.98;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;

    utterance.onend = () => {
      if (queueRef.current.length > 0) {
        setTimeout(playNextChunk, 10);
      } else {
        finishPlayback();
      }
    };

    utterance.onerror = (e) => {
      if (e.error !== "interrupted") {
        finishPlayback();
      }
    };

    synth.speak(utterance);
  }, [finishPlayback]);

  const speakBrowser = useCallback(
    (prepared: string) => {
      const chunks = chunkForSpeech(prepared);
      queueRef.current = chunks;
      if (chunks.length > 0) {
        setPhase("playing");
        playNextChunk();
      }
    },
    [playNextChunk, setPhase],
  );

  const speak = useCallback(
    async (text: string): Promise<SpeakResult> => {
      if (!synth) return { ok: false, error: "Speech synthesis not supported" };

      if (!tryAcquireSpeechLock()) {
        return { ok: false, error: "Audio is already playing. Wait for it to finish." };
      }

      const sessionGen = ++sessionGenRef.current;
      lastTextRef.current = text;
      cleanupMedia();

      const prepared = prepareTextForSpeech(text);
      lastPreparedRef.current = prepared;
      setLoading(true);
      setPhase("loading");

      if (cloudAvailable) {
        try {
          const blob = await fetchTtsAudio(prepared);
          if (sessionGen !== sessionGenRef.current) {
            return { ok: true };
          }

          const url = URL.createObjectURL(blob);
          objectUrlRef.current = url;

          const audio = new Audio(url);
          activeAudioRef.current = audio;

          audio.onplay = () => {
            if (sessionGen !== sessionGenRef.current) return;
            setLoading(false);
            setPhase("playing");
          };

          audio.onended = () => {
            if (sessionGen !== sessionGenRef.current) return;
            finishPlayback();
          };

          audio.onerror = () => {
            if (sessionGen !== sessionGenRef.current) return;
            setLoading(false);
            activeAudioRef.current = null;
            speakBrowser(prepared);
          };

          await audio.play();
          return { ok: true };
        } catch (e) {
          if (sessionGen !== sessionGenRef.current) {
            return { ok: true };
          }
          console.warn("Cloud TTS failed, falling back to browser.", e);
          setLoading(false);
          speakBrowser(prepared);
          return { ok: true };
        }
      }

      setLoading(false);
      speakBrowser(prepared);
      return { ok: true };
    },
    [cloudAvailable, speakBrowser, cleanupMedia, finishPlayback, setPhase],
  );

  const pause = useCallback(() => {
    if (playbackPhaseRef.current !== "playing") return;

    if (activeAudioRef.current) {
      activeAudioRef.current.pause();
    }
    if (synth?.speaking && !synth.paused) {
      synth.pause();
    }
    setPhase("paused");
  }, [setPhase]);

  const resume = useCallback(async (): Promise<void> => {
    if (playbackPhaseRef.current !== "paused") return;

    try {
      if (activeAudioRef.current) {
        await activeAudioRef.current.play();
      } else if (synth?.paused) {
        synth.resume();
      }
      setPhase("playing");
    } catch {
      finishPlayback();
    }
  }, [finishPlayback, setPhase]);

  const stop = useCallback(() => {
    sessionGenRef.current += 1;
    cleanupMedia();
    setLoading(false);
    setPhase("ended");
    releaseSpeechLock();
  }, [cleanupMedia, setPhase]);

  const restart = useCallback(async (): Promise<void> => {
    const text = lastTextRef.current;
    const prepared = lastPreparedRef.current;
    if (!text || !prepared) {
      if (text) {
        await speak(text);
      }
      return;
    }

    if (playbackPhaseRef.current === "idle" || playbackPhaseRef.current === "ended") {
      await speak(text);
      return;
    }

    sessionGenRef.current += 1;

    if (activeAudioRef.current && objectUrlRef.current) {
      activeAudioRef.current.pause();
      activeAudioRef.current.currentTime = 0;
      try {
        await activeAudioRef.current.play();
        setLoading(false);
        setPhase("playing");
        return;
      } catch {
        finishPlayback();
        return;
      }
    }

    synth?.cancel();
    queueRef.current = chunkForSpeech(prepared);
    activeUtteranceRef.current = null;
    if (queueRef.current.length > 0) {
      setLoading(false);
      setPhase("playing");
      playNextChunk();
    }
  }, [speak, finishPlayback, playNextChunk, setPhase]);

  const cancel = stop;

  return {
    supported,
    speaking,
    loading,
    playbackPhase,
    speak,
    pause,
    resume,
    restart,
    stop,
    cancel,
    cloudAvailable,
  } as const;
}
