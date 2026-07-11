import { cn } from "@/lib/utils";

const TONES = [
  { key: "formal", label: "Formal" },
  { key: "sarcastic", label: "Sarcastic" },
  { key: "humorous_tech", label: "Humorous — Tech" },
  { key: "humorous_non_tech", label: "Humorous — Everyday" },
];

export function CaptionGrid({ captions, viewMode, selectedTone, onSelectTone }) {
  if (viewMode === "single" && selectedTone) {
    const tone = TONES.find((t) => t.key === selectedTone);
    return (
      <div className="rounded-xl border border-dashed border-cyan-500/50 bg-cyan-500/5 p-5 shadow-[0_0_24px_-6px_rgba(6,182,212,0.3)]">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-cyan-400">
          {tone?.label}
        </p>
        <p className="text-sm leading-relaxed text-zinc-200">
          {captions[selectedTone]}
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {TONES.map((tone) => (
        <button
          key={tone.key}
          type="button"
          onClick={() => onSelectTone?.(tone.key)}
          className={cn(
            "rounded-xl border bg-zinc-900/80 p-4 text-left transition-all",
            "hover:border-violet-500/30 hover:bg-zinc-900",
            selectedTone === tone.key
              ? "border-dashed border-cyan-500/60 shadow-[0_0_20px_-6px_rgba(6,182,212,0.35)]"
              : "border-white/10"
          )}
        >
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-violet-400">
            {tone.label}
          </p>
          <p className="text-sm leading-relaxed text-zinc-300">
            {captions[tone.key]}
          </p>
        </button>
      ))}
    </div>
  );
}

export { TONES };
