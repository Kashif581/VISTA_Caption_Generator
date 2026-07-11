import { Film, LayoutGrid, Sparkles, Upload } from "lucide-react";
import { HOW_IT_WORKS } from "@/data/staticContent";

const ICONS = { Upload, Sparkles, LayoutGrid, Film };

export function HowItWorks() {
  return (
    <section id="how-it-works" className="py-16">
      <div className="mb-10 text-center">
        <p className="mb-2 text-xs font-medium uppercase tracking-widest text-violet-400">
          Workflow
        </p>
        <h2 className="text-2xl font-bold text-white md:text-3xl">How It Works</h2>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {HOW_IT_WORKS.map((item) => {
          const Icon = ICONS[item.icon];
          return (
            <div
              key={item.title}
              className="group rounded-2xl border border-white/8 bg-zinc-950/60 p-5 transition-all hover:border-violet-500/25 hover:shadow-[0_0_30px_-8px_rgba(124,58,237,0.4)]"
            >
              <div className="mb-4 flex size-10 items-center justify-center rounded-xl bg-violet-600/15 ring-1 ring-violet-500/20 transition-colors group-hover:bg-violet-600/25">
                <Icon className="size-5 text-violet-400" />
              </div>
              <h3 className="mb-1.5 font-semibold text-white">{item.title}</h3>
              <p className="text-sm leading-relaxed text-zinc-400">
                {item.description}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
