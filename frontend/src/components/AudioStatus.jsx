import { Mic, MicOff, Volume2 } from "lucide-react";
import { cn } from "@/lib/utils";

export function AudioStatus({ audio }) {
  if (!audio) return null;

  const hasContent = Boolean(audio.transcript || audio.background_sounds?.length);

  return (
    <div className="rounded-xl border border-white/10 bg-black/40 p-5">
      <div className="mb-4 flex items-center justify-between">
        <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-violet-400">
          <Volume2 className="size-3.5" />
          Audio Status
        </p>
        <span
          className={cn(
            "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1",
            !audio.enabled
              ? "bg-zinc-800 text-zinc-400 ring-white/10"
              : hasContent
                ? "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30"
                : "bg-zinc-800 text-zinc-400 ring-white/10"
          )}
        >
          {audio.enabled ? (
            hasContent ? (
              <Mic className="size-3 text-emerald-400" />
            ) : (
              <MicOff className="size-3 text-zinc-500" />
            )
          ) : (
            <MicOff className="size-3 text-zinc-500" />
          )}
          {!audio.enabled ? "Disabled" : hasContent ? "Detected" : "No audio"}
        </span>
      </div>

      {audio.note && !hasContent && (
        <p className="text-sm text-zinc-500">{audio.note}</p>
      )}

      {audio.transcript && (
        <div className="mb-3">
          <p className="mb-1 text-xs font-medium uppercase tracking-wider text-zinc-500">
            Transcript
          </p>
          <p className="text-sm leading-relaxed text-zinc-300">{audio.transcript}</p>
        </div>
      )}

      {audio.background_sounds?.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-zinc-500">
            Background Sounds
          </p>
          <div className="flex flex-wrap gap-2">
            {audio.background_sounds.map((sound) => (
              <span
                key={sound}
                className="rounded-full bg-white/5 px-2.5 py-1 text-xs text-zinc-400 ring-1 ring-white/10"
              >
                {sound}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
