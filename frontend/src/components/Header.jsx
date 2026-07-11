import { Clapperboard } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export function Header() {
  return (
    <header className="sticky top-0 z-50 border-b border-white/5 bg-black/70 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <div className="flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-xl bg-violet-600/20 ring-1 ring-violet-500/30">
            <Clapperboard className="size-5 text-violet-400" />
          </div>
          <span className="text-lg font-semibold tracking-tight text-white">
            ClipTone
          </span>
        </div>

        <div className="flex items-center gap-4">
          <Badge
            variant="outline"
            className="hidden border-violet-500/30 bg-violet-500/10 text-violet-300 sm:inline-flex"
          >
            Hackathon Track
          </Badge>
          <nav className="hidden items-center gap-6 text-sm text-zinc-400 md:flex">
            <a href="#input" className="transition-colors hover:text-white">
              Generate
            </a>
            <a href="#how-it-works" className="transition-colors hover:text-white">
              How It Works
            </a>
          </nav>
        </div>
      </div>
    </header>
  );
}
