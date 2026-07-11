import { ClipInput } from "@/components/ClipInput";

export function Hero({
  clips,
  inputTab,
  onTabChange,
  onClipChange,
  onAddClip,
  onRemoveClip,
  onGenerate,
  isGenerating,
}) {
  return (
    <section id="input" className="relative overflow-hidden pt-12 pb-8">
      <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 -z-20 h-[420px] overflow-hidden">
        <video
          src="/heroBg.mp4"
          autoPlay
          muted
          loop
          playsInline
          className="h-full w-full object-cover opacity-25"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-black/40 via-black/70 to-black" />
      </div>

      <div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-0 -z-10 h-72 w-[600px] -translate-x-1/2 rounded-full bg-violet-600/25 blur-[100px]"
      />

      <div className="mx-auto max-w-3xl text-center">
        <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-violet-400">
          AI Caption Studio
        </p>
        <h1 className="mb-3 text-4xl font-bold tracking-tight text-white md:text-5xl">
          ClipTone
        </h1>
        <p className="mb-8 text-base text-zinc-400 md:text-lg">
          Compare four caption tones across multiple clips — formal, sarcastic,
          tech humor, and non-tech humor — all in one view.
        </p>
      </div>

      <div className="mx-auto max-w-2xl">
        <ClipInput
          clips={clips}
          inputTab={inputTab}
          onTabChange={onTabChange}
          onClipChange={onClipChange}
          onAddClip={onAddClip}
          onRemoveClip={onRemoveClip}
          onGenerate={onGenerate}
          isGenerating={isGenerating}
        />
      </div>
    </section>
  );
}
