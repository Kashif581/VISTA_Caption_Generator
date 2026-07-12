import { Clapperboard } from "lucide-react";

export function Footer() {
  return (
    <footer className="relative mt-8 border-t border-violet-500/20 bg-gradient-to-b from-black to-violet-950/30">
      <div className="mx-auto max-w-6xl px-6 py-12">
        <div className="flex flex-col items-center justify-between gap-6 md:flex-row">
          <div className="flex items-center gap-3">
            <div className="flex size-8 items-center justify-center rounded-lg bg-violet-600/20">
              <Clapperboard className="size-4 text-violet-400" />
            </div>
            <span className="font-semibold text-white">VISTA</span>
          </div>

          <p className="text-center text-sm text-zinc-500">
            Built with{" "}
            <span className="text-violet-400">Fireworks AI</span>
            {" • "}
            <span className="text-violet-400">Groq</span>
            {" • "}
            <span className="text-violet-400">faster-whisper</span>
          </p>
        </div>
      </div>
    </footer>
  );
}
