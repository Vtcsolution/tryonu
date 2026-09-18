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
        className={`tu-press grid h-9 w-9 shrink-0 place-items-center rounded-full transition-colors ${
          isListening ? "bg-sage text-white" : "text-ink-soft hover:bg-ink/[0.06] hover:text-ink"
        } ${className}`}
      >
        {isListening ? (
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-white/70" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-white" />
          </span>
        ) : (
          <MicIcon />
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

function MicIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="9" y="3" width="6" height="11" rx="3" stroke="currentColor" strokeWidth="1.8" />
      <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
