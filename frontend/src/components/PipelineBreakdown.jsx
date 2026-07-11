import { Check, Download, Film, Mic, Sparkles, Wand2 } from "lucide-react";
import { cn } from "@/lib/utils";

const STAGE_META = [
  { key: "download_sec", label: "Download clip", icon: Download },
  { key: "scene_detect_sec", label: "Scene detect + keyframes", icon: Film },
  { key: "audio_sec", label: "Audio transcript + sounds", icon: Mic },
  { key: "captioning_sec", label: "Per-scene descriptions + combine + captions", icon: Sparkles },
];

const BACKEND_LABEL = {
  fireworks: "Fireworks AI",
  groq: "Groq (fallback)",
};

export function PipelineBreakdown({ stages, totalSec, backendUsed, description }) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/40 p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-violet-400">
          <Wand2 className="size-3.5" />
          Pipeline
        </p>
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          {backendUsed && (
            <span
              className={cn(
                "rounded-full px-2.5 py-1 font-medium ring-1",
                backendUsed === "fireworks"
                  ? "bg-orange-500/10 text-orange-300 ring-orange-500/30"
                  : "bg-teal-500/10 text-teal-300 ring-teal-500/30"
              )}
            >
              Captioned via {BACKEND_LABEL[backendUsed] || backendUsed}
            </span>
          )}
          {totalSec != null && <span className="font-mono">{totalSec.toFixed(1)}s total</span>}
        </div>
      </div>

      <ol className="space-y-2.5">
        {STAGE_META.map(({ key, label, icon: Icon }) => {
          const sec = stages?.[key];
          const ran = typeof sec === "number";
          return (
            <li
              key={key}
              className="flex items-center gap-3 rounded-lg border border-white/5 bg-white/2 px-3 py-2.5"
            >
              <div className="flex size-6 shrink-0 items-center justify-center rounded-full bg-violet-600/15 ring-1 ring-violet-500/25">
                {ran ? (
                  <Check className="size-3.5 text-violet-400" />
                ) : (
                  <Icon className="size-3.5 text-zinc-500" />
                )}
              </div>
              <span className="flex-1 text-sm text-zinc-300">{label}</span>
              <span className="font-mono text-xs text-zinc-500">
                {ran ? `${sec.toFixed(2)}s` : "—"}
              </span>
            </li>
          );
        })}
      </ol>

      {description && (
        <div className="mt-4 border-t border-white/5 pt-4">
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wider text-violet-400">
            AI Video Description
          </p>
          <p className="text-sm leading-relaxed text-zinc-300">{description}</p>
        </div>
      )}
    </div>
  );
}
