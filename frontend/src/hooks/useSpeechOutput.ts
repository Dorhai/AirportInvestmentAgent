import { useCallback, useEffect, useRef, useState } from "react";
import { prepareTextForSpeech, chunkForSpeech } from "@/services/speak";
import { fetchTtsStatus, fetchTtsAudio } from "@/services/api";
import { tryAcquireSpeechLock, releaseSpeechLock } from "@/lib/speechSession";

export type SpeakResult = { ok: true } | { ok: false; error: string };

const synth =
  typeof window !== "undefined" ? window.speechSynthesis : undefined;

function pickPreferredVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  if (!voices.length) return null;
  const enVoices = voices.filter((v) => v.lang.startsWith("en"));
  const pool = enVoices.length > 0 ? enVoices : voices;
  
  const preferred = pool.find((v) =>
    /natural|neural|google|jenny|guy|aria|microsoft/i.test(v.name)
  );
  if (preferred) return preferred;
  
  const online = pool.find((v) => !v.localService);
  if (online) return online;

  return pool[0] ?? null;
}

export function useSpeechOutput() {
  const supported = !!synth;
  const [speaking, setSpeaking] = useState(false);
  const [loading, setLoading] = useState(false);
  const [cloudAvailable, setCloudAvailable] = useState<boolean | null>(null);
  
  const voicesRef = useRef<SpeechSynthesisVoice[]>([]);
  const queueRef = useRef<string[]>([]);
  const activeUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const activeAudioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  useEffect(() => {
    fetchTtsStatus().then(status => {
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

  const playNextChunk = useCallback(() => {
    if (!synth) return;
    const chunk = queueRef.current.shift();
    if (!chunk) {
      setSpeaking(false);
      activeUtteranceRef.current = null;
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
        // small timeout to avoid Chrome truncation bug
        setTimeout(playNextChunk, 10);
      } else {
        setSpeaking(false);
        activeUtteranceRef.current = null;
        releaseSpeechLock();
      }
    };
    
    utterance.onerror = (e) => {
      // "interrupted" means we cancelled it manually, ignore
      if (e.error !== "interrupted") {
        setSpeaking(false);
        queueRef.current = [];
        activeUtteranceRef.current = null;
        releaseSpeechLock();
      }
    };
    
    synth.speak(utterance);
  }, []);

  const speakBrowser = useCallback((prepared: string) => {
    const chunks = chunkForSpeech(prepared);
    queueRef.current = chunks;
    if (chunks.length > 0) {
      setSpeaking(true);
      playNextChunk();
    }
  }, [playNextChunk]);

  const speak = useCallback(async (text: string): Promise<SpeakResult> => {
    if (!synth) return { ok: false, error: "Speech synthesis not supported" };
    
    if (!tryAcquireSpeechLock()) {
      return { ok: false, error: "Audio is already playing. Wait for it to finish." };
    }
    
    // Reset previous audio
    synth.cancel();
    if (activeAudioRef.current) {
      activeAudioRef.current.pause();
      activeAudioRef.current = null;
    }
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    
    const prepared = prepareTextForSpeech(text);
    
    if (cloudAvailable) {
      setLoading(true);
      try {
        const blob = await fetchTtsAudio(prepared);
        const url = URL.createObjectURL(blob);
        objectUrlRef.current = url;
        
        const audio = new Audio(url);
        activeAudioRef.current = audio;
        
        audio.onplay = () => {
          setLoading(false);
          setSpeaking(true);
        };
        
        audio.onended = () => {
          setSpeaking(false);
          activeAudioRef.current = null;
          URL.revokeObjectURL(url);
          objectUrlRef.current = null;
          releaseSpeechLock();
        };
        
        audio.onerror = () => {
          // fallback to browser on audio error
          setLoading(false);
          activeAudioRef.current = null;
          speakBrowser(prepared);
        };
        
        await audio.play();
        return { ok: true };
      } catch (e) {
        console.warn("Cloud TTS failed, falling back to browser.", e);
        setLoading(false);
        speakBrowser(prepared);
        return { ok: true };
      }
    } else {
      speakBrowser(prepared);
      return { ok: true };
    }
  }, [cloudAvailable, speakBrowser]);

  const cancel = useCallback(() => {
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
    setSpeaking(false);
    setLoading(false);
    releaseSpeechLock();
  }, []);

  return { supported, speaking, loading, speak, cancel, cloudAvailable } as const;
}
