"use client";

import { useVoiceInput } from "@/lib/hooks/useVoiceInput";

/**
 * Mic button for a prompt/search box — appends the transcribed text via
 * onTranscript rather than owning the input's value, so it drops into an
 * existing controlled <input> without changing who owns the state.
 * Renders nothing if the browser doesn't support speech recognition
 * (Firefox, Safari as of this writing) rather than showing a dead button.
 */
export function VoiceInputButton({
  onTranscript,
  className = "",
}: {
  onTranscript: (text: string) => void;
  className?: string;
}) {
  const { isSupported, isListening, interimText, error, start, stop } = useVoiceInput({
    onFinalTranscript: onTranscript,
  });

  if (!isSupported) return null;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => (isListening ? stop() : start())}
        aria-label={isListening ? "Stop voice input" : "Use voice input"}
        aria-pressed={isListening}
        title={isListening ? "Listening… click to stop" : "Speak your request"}
        className={`grid h-9 w-9 shrink-0 place-items-center rounded-full border text-[15px] transition-colors ${
          isListening
            ? "border-sage bg-sage text-white"
            : "border-line-strong text-ink-soft hover:border-sage hover:text-sage-deep"
        } ${className}`}
      >
        {isListening ? (
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-white/70" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-white" />
          </span>
        ) : (
          "🎤"
        )}
      </button>

      {(isListening && interimText) && (
        <div className="absolute bottom-full left-1/2 mb-2 w-max max-w-[240px] -translate-x-1/2 rounded-lg bg-ink px-2.5 py-1.5 text-[11.5px] text-white shadow-lift">
          {interimText}
        </div>
      )}
      {error && (
        <div
          role="alert"
          className="absolute bottom-full left-1/2 mb-2 w-max max-w-[220px] -translate-x-1/2 rounded-lg bg-[#a4553f] px-2.5 py-1.5 text-[11.5px] text-white shadow-lift"
        >
          {error}
        </div>
      )}
    </div>
  );
}
