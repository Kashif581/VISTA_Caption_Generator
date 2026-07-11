import { Plus, X, Link2, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

export function ClipInput({
  clips,
  inputTab,
  onTabChange,
  onClipChange,
  onAddClip,
  onRemoveClip,
  onGenerate,
  isGenerating,
}) {
  const canGenerate = clips.some((c) => c.value?.trim?.() || c.file);

  return (
    <div className="rounded-2xl border border-white/10 bg-zinc-950/80 p-6 shadow-[0_0_60px_-12px_rgba(124,58,237,0.35)] backdrop-blur-sm">
      <Tabs value={inputTab} onValueChange={onTabChange}>
        <TabsList className="mb-5 w-full bg-white/5">
          <TabsTrigger value="url" className="flex-1 gap-2">
            <Link2 className="size-4" />
            Paste URL
          </TabsTrigger>
          <TabsTrigger value="upload" className="flex-1 gap-2">
            <Upload className="size-4" />
            Upload File
          </TabsTrigger>
        </TabsList>

        <TabsContent value="url" className="space-y-3">
          {clips.map((clip, index) => (
            <div key={clip.id} className="flex items-center gap-2">
              <input
                type="url"
                placeholder="https://example.com/video.mp4"
                value={clip.value || ""}
                onChange={(e) =>
                  onClipChange(clip.id, { value: e.target.value, type: "url" })
                }
                className={cn(
                  "h-11 flex-1 rounded-xl border border-white/10 bg-black/50 px-4 text-sm text-white",
                  "placeholder:text-zinc-500 focus:border-violet-500/50 focus:outline-none focus:ring-2 focus:ring-violet-500/20"
                )}
              />
              {clips.length > 1 && (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => onRemoveClip(clip.id)}
                  className="shrink-0 text-zinc-400 hover:text-white"
                  aria-label={`Remove clip ${index + 1}`}
                >
                  <X className="size-4" />
                </Button>
              )}
            </div>
          ))}
        </TabsContent>

        <TabsContent value="upload" className="space-y-3">
          {clips.map((clip, index) => (
            <div key={clip.id} className="flex items-center gap-2">
              <label
                className={cn(
                  "flex h-11 flex-1 cursor-pointer items-center rounded-xl border border-dashed border-white/15 bg-black/50 px-4 text-sm",
                  "transition-colors hover:border-violet-500/40 hover:bg-violet-500/5"
                )}
              >
                <Upload className="mr-2 size-4 shrink-0 text-violet-400" />
                <span className={clip.file ? "text-white" : "text-zinc-500"}>
                  {clip.file ? clip.file.name : "Choose a video file…"}
                </span>
                <input
                  type="file"
                  accept="video/*"
                  className="sr-only"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      onClipChange(clip.id, {
                        file,
                        type: "file",
                        value: file.name,
                        fileUrl: URL.createObjectURL(file),
                      });
                    }
                  }}
                />
              </label>
              {clips.length > 1 && (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => onRemoveClip(clip.id)}
                  className="shrink-0 text-zinc-400 hover:text-white"
                  aria-label={`Remove clip ${index + 1}`}
                >
                  <X className="size-4" />
                </Button>
              )}
            </div>
          ))}
        </TabsContent>
      </Tabs>

      <Button
        type="button"
        variant="ghost"
        onClick={onAddClip}
        className="mt-4 w-full border border-dashed border-white/10 text-zinc-400 hover:border-violet-500/30 hover:bg-violet-500/5 hover:text-violet-300"
      >
        <Plus className="size-4" />
        Add another clip
      </Button>

      <Button
        type="button"
        onClick={onGenerate}
        disabled={!canGenerate || isGenerating}
        className="mt-4 h-12 w-full rounded-xl bg-violet-600 text-base font-medium text-white hover:bg-violet-500 disabled:opacity-40"
      >
        {isGenerating ? "Processing…" : "Generate Captions"}
      </Button>
    </div>
  );
}
