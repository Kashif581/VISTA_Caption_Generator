import { useState } from "react";
import { Film, Grid3x3 } from "lucide-react";
import { cn } from "@/lib/utils";

function formatTime(seconds) {
  const s = Math.max(0, seconds || 0);
  const m = Math.floor(s / 60)
    .toString()
    .padStart(2, "0");
  const rem = Math.floor(s % 60)
    .toString()
    .padStart(2, "0");
  return `${m}:${rem}`;
}

export function KeyframeGrid({ keyframes, activeIndex, onSelect }) {
  const [showSprite, setShowSprite] = useState(false);

  if (!keyframes?.length) return null;

  const active = keyframes[activeIndex] ?? keyframes[0];
  const displaySrc = (showSprite && active.sprite) || active.image;

  return (
    <div className="rounded-xl border border-white/10 bg-black/40 p-5">
      <div className="mb-4 flex items-center justify-between">
        <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-violet-400">
          <Film className="size-3.5" />
          Keyframe Breakdown
          <span className="font-normal normal-case text-zinc-500">
            ({keyframes.length} scene{keyframes.length > 1 ? "s" : ""} sampled)
          </span>
        </p>
        {active.sprite && (
          <button
            type="button"
            onClick={() => setShowSprite((v) => !v)}
            className={cn(
              "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 transition-colors",
              showSprite
                ? "bg-violet-600/20 text-violet-300 ring-violet-500/40"
                : "bg-white/5 text-zinc-400 ring-white/10 hover:text-white"
            )}
          >
            <Grid3x3 className="size-3" />
            {showSprite ? "Showing motion grid" : "Show motion grid"}
          </button>
        )}
      </div>

      <div className="mb-4 overflow-hidden rounded-lg ring-1 ring-white/10">
        <img
          src={displaySrc}
          alt={
            showSprite
              ? `Sprite sheet for scene at ${formatTime(active.timestamp_sec)} -- frames sampled ~1/sec`
              : `Keyframe at ${formatTime(active.timestamp_sec)}`
          }
          className="aspect-video w-full bg-zinc-900 object-contain"
        />
      </div>

      {active.description && (
        <div className="mb-4 rounded-lg border border-white/5 bg-white/2 p-3">
          <p className="mb-1 text-xs font-medium uppercase tracking-wider text-zinc-500">
            Scene {activeIndex + 1} at {formatTime(active.timestamp_sec)} -- what the model saw
          </p>
          <p className="text-sm leading-relaxed text-zinc-300">{active.description}</p>
        </div>
      )}

      <div className="flex gap-2 overflow-x-auto pb-1">
        {keyframes.map((kf, i) => (
          <button
            key={`${kf.timestamp_sec}-${i}`}
            type="button"
            onClick={() => onSelect(i)}
            className={cn(
              "group relative shrink-0 overflow-hidden rounded-md ring-1 transition-all",
              i === activeIndex
                ? "ring-2 ring-violet-500"
                : "ring-white/10 hover:ring-violet-500/40"
            )}
          >
            <img
              src={kf.image}
              alt={`Keyframe thumbnail ${i + 1}`}
              className="h-14 w-24 object-cover opacity-80 transition-opacity group-hover:opacity-100"
            />
            <span className="absolute bottom-0.5 right-1 rounded bg-black/70 px-1 font-mono text-[10px] text-white">
              {formatTime(kf.timestamp_sec)}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
