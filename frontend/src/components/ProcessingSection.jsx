import { AlertTriangle } from "lucide-react";
import { ResultCard } from "@/components/ResultCard";
import { Skeleton } from "@/components/ui/skeleton";

const PIPELINE_STAGES = [
  "Downloading clip",
  "Detecting scenes & keyframes",
  "Transcribing & classifying audio",
  "Describing video (vision model)",
  "Writing styled captions",
];

function LoadingRow({ name }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-zinc-950/60 px-5 py-6">
      <div className="flex items-center gap-4">
        <div className="relative flex size-10 shrink-0 items-center justify-center">
          <span className="absolute inset-0 animate-ping rounded-full bg-violet-500/20" />
          <span className="relative size-3 rounded-full bg-violet-500" />
        </div>
        <div className="flex-1 space-y-2">
          <p className="text-sm font-medium text-white">{name}</p>
          <p className="animate-pulse text-sm text-violet-400/80">Running the pipeline…</p>
          <Skeleton className="h-1.5 w-full max-w-xs bg-violet-500/20" />
        </div>
      </div>
      <ul className="mt-5 ml-14 grid gap-1.5 text-xs text-zinc-500">
        {PIPELINE_STAGES.map((stage) => (
          <li key={stage} className="flex items-center gap-2">
            <span className="size-1 rounded-full bg-zinc-600" />
            {stage}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ErrorRow({ name, message }) {
  return (
    <div className="flex items-start gap-4 rounded-2xl border border-red-500/20 bg-red-950/20 px-5 py-6">
      <AlertTriangle className="mt-0.5 size-5 shrink-0 text-red-400" />
      <div className="flex-1">
        <p className="text-sm font-medium text-white">{name}</p>
        <p className="mt-1 text-sm text-red-300/90">{message}</p>
      </div>
    </div>
  );
}

export function ProcessingSection({ clips, statuses, results, sectionRef }) {
  const loadingCount = clips.filter((c) => statuses[c.id] === "loading").length;
  const doneCount = clips.filter((c) => statuses[c.id] === "done").length;
  const errorCount = clips.filter((c) => statuses[c.id] === "error").length;

  if (!clips.some((c) => statuses[c.id] !== "idle")) return null;

  return (
    <section ref={sectionRef} className="py-16">
      <div className="mb-8">
        <p className="mb-2 text-xs font-medium uppercase tracking-widest text-violet-400">
          Results
        </p>
        <h2 className="text-2xl font-bold text-white md:text-3xl">
          {loadingCount > 0
            ? `Processing ${loadingCount} clip${loadingCount > 1 ? "s" : ""} in parallel…`
            : `${doneCount} clip${doneCount > 1 ? "s" : ""} ready${
                errorCount ? `, ${errorCount} failed` : ""
              }`}
        </h2>
      </div>

      <div className="space-y-6">
        {clips.map((clip) => {
          const status = statuses[clip.id];
          const name = clip.name || clip.value || "Clip";
          if (!status || status === "idle") return null;

          if (status === "loading") {
            return <LoadingRow key={clip.id} name={name} />;
          }

          if (status === "error") {
            return (
              <ErrorRow key={clip.id} name={name} message={results[clip.id]?.error} />
            );
          }

          if (status === "done" && results[clip.id]) {
            return <ResultCard key={clip.id} result={results[clip.id]} />;
          }

          return null;
        })}
      </div>
    </section>
  );
}
