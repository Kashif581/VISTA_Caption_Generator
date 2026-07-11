import { useState } from "react";
import { ChevronDown, LayoutGrid, Maximize2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CaptionGrid } from "@/components/CaptionGrid";
import { PipelineBreakdown } from "@/components/PipelineBreakdown";
import { KeyframeGrid } from "@/components/KeyframeGrid";
import { AudioStatus } from "@/components/AudioStatus";
import { cn } from "@/lib/utils";

export function ResultCard({ result }) {
  const [expanded, setExpanded] = useState(false);
  const [viewMode, setViewMode] = useState("grid");
  const [selectedTone, setSelectedTone] = useState(null);
  const [activeKeyframe, setActiveKeyframe] = useState(0);

  const toggleViewMode = () => {
    if (viewMode === "grid") {
      setViewMode("single");
      setSelectedTone("formal");
    } else {
      setViewMode("grid");
      setSelectedTone(null);
    }
  };

  return (
    <article className="overflow-hidden rounded-2xl border border-white/10 bg-zinc-950/80 shadow-[0_0_40px_-12px_rgba(124,58,237,0.2)]">
      <div className="flex items-center justify-between border-b border-white/5 px-5 py-3">
        <h3 className="font-medium text-white">{result.name}</h3>
        {result.duration_sec != null && (
          <span className="font-mono text-xs text-zinc-500">
            {result.duration_sec.toFixed(1)}s clip
          </span>
        )}
      </div>

      <div className="p-5 space-y-5">
        {result.videoUrl && (
          <div className="overflow-hidden rounded-xl ring-1 ring-white/10">
            <video
              src={result.videoUrl}
              controls
              poster={result.keyframes?.[0]?.image}
              className="aspect-video w-full bg-black object-contain"
            >
              <track kind="captions" />
            </video>
          </div>
        )}

        <div className="flex items-center justify-between">
          <p className="text-xs font-medium uppercase tracking-wider text-zinc-500">
            Caption Styles
          </p>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={toggleViewMode}
            className="gap-1.5 text-zinc-400 hover:text-violet-300"
          >
            {viewMode === "grid" ? (
              <>
                <Maximize2 className="size-3.5" />
                Single style view
              </>
            ) : (
              <>
                <LayoutGrid className="size-3.5" />
                Grid view
              </>
            )}
          </Button>
        </div>

        <CaptionGrid
          captions={result.captions}
          viewMode={viewMode}
          selectedTone={selectedTone}
          onSelectTone={(tone) => {
            setSelectedTone(tone);
            if (viewMode === "grid") {
              setViewMode("single");
            }
          }}
        />

        <Button
          type="button"
          variant="ghost"
          onClick={() => setExpanded((v) => !v)}
          className="w-full justify-between border border-white/10 bg-white/3 text-zinc-300 hover:bg-white/5 hover:text-white"
        >
          How this caption was generated
          <ChevronDown
            className={cn(
              "size-4 transition-transform",
              expanded && "rotate-180"
            )}
          />
        </Button>

        {expanded && (
          <div className="space-y-4">
            <PipelineBreakdown
              stages={result.stages}
              totalSec={result.total_sec}
              backendUsed={result.backend_used}
              description={result.description}
            />
            <KeyframeGrid
              keyframes={result.keyframes}
              activeIndex={activeKeyframe}
              onSelect={setActiveKeyframe}
            />
            <AudioStatus audio={result.audio} />
          </div>
        )}
      </div>
    </article>
  );
}
