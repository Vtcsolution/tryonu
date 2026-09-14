"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Minimal surface of the Web Speech API's SpeechRecognition we actually
 * use — not shipped in lib.dom.d.ts for the webkit-prefixed variant, and
 * we don't want a whole @types package for four properties.
 */
interface SpeechRecognitionAlternativeLike {
  transcript: string;
}
interface SpeechRecognitionResultLike extends ArrayLike<SpeechRecognitionAlternativeLike> {
  isFinal: boolean;
}
interface SpeechRecognitionLike extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  onresult: ((event: { results: ArrayLike<SpeechRecognitionResultLike> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getSpeechRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/**
 * Voice-to-text for a prompt box. Browser-native (Chrome/Edge; not
 * Firefox/Safari as of this writing) — `isSupported` tells the caller
 * whether to even render a mic button, rather than showing one that
 * silently does nothing.
 */
export function useVoiceInput({ onFinalTranscript }: { onFinalTranscript: (text: string) => void }) {
  const [isListening, setIsListening] = useState(false);
  const [interimText, setInterimText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const isSupported = getSpeechRecognitionCtor() !== null;

  useEffect(() => {
    return () => recognitionRef.current?.stop();
  }, []);

  const start = useCallback(() => {
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) {
      setError("Voice input isn't supported in this browser — try typing instead.");
      return;
    }
    setError(null);
    setInterimText("");

    const recognition = new Ctor();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onresult = (event) => {
      let finalText = "";
      let interim = "";
      for (let i = 0; i < event.results.length; i++) {
        const result = event.results[i];
        const alt = result[0];
        if (!alt) continue;
        if (result.isFinal) finalText += alt.transcript;
        else interim += alt.transcript;
      }
      if (finalText) onFinalTranscript(finalText.trim());
      setInterimText(interim);
    };
    recognition.onerror = (event) => {
      setError(
        event.error === "not-allowed"
          ? "Microphone access was denied — allow it in your browser settings to use voice input."
          : "Couldn't hear that — try again, or type instead."
      );
      setIsListening(false);
    };
    recognition.onend = () => {
      setIsListening(false);
      setInterimText("");
    };

    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  }, [onFinalTranscript]);

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
  }, []);

  return { isSupported, isListening, interimText, error, start, stop };
}
