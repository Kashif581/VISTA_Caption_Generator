import { useCallback, useRef, useState } from "react";
import { Header } from "@/components/Header";
import { Hero } from "@/components/Hero";
import { HowItWorks } from "@/components/HowItWorks";
import { ProcessingSection } from "@/components/ProcessingSection";
import { Footer } from "@/components/Footer";
import { processClip } from "@/services/api";

let clipCounter = 0;

function createClip(overrides = {}) {
  clipCounter += 1;
  return {
    id: `clip-${clipCounter}`,
    type: "url",
    value: "",
    name: "",
    ...overrides,
  };
}

export default function App() {
  const [clips, setClips] = useState([createClip()]);
  const [inputTab, setInputTab] = useState("url");
  const [statuses, setStatuses] = useState({});
  const [results, setResults] = useState({});
  const [isGenerating, setIsGenerating] = useState(false);
  const resultsRef = useRef(null);

  const handleClipChange = useCallback((id, updates) => {
    setClips((prev) =>
      prev.map((c) =>
        c.id === id
          ? {
              ...c,
              ...updates,
              name: updates.value || updates.file?.name || c.name,
            }
          : c
      )
    );
  }, []);

  const handleAddClip = useCallback(() => {
    setClips((prev) => [...prev, createClip({ type: inputTab === "upload" ? "file" : "url" })]);
  }, [inputTab]);

  const handleRemoveClip = useCallback((id) => {
    setClips((prev) => prev.filter((c) => c.id !== id));
  }, []);

  const handleGenerate = useCallback(async () => {
    const validClips = clips.filter((c) => c.value?.trim?.() || c.file);
    if (!validClips.length) return;

    setIsGenerating(true);
    const nextStatuses = {};
    validClips.forEach((c) => {
      nextStatuses[c.id] = "loading";
    });
    setStatuses(nextStatuses);
    setResults({});

    requestAnimationFrame(() => {
      resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });

    await Promise.allSettled(
      validClips.map(async (clip) => {
        try {
          const data = await processClip({
            videoUrl: clip.type === "url" ? clip.value : undefined,
            file: clip.type === "file" ? clip.file : undefined,
          });

          setResults((prev) => ({
            ...prev,
            [clip.id]: {
              ...data,
              name: clip.name || clip.value || "Clip",
              videoUrl: clip.fileUrl || clip.value,
            },
          }));
          setStatuses((prev) => ({ ...prev, [clip.id]: "done" }));
        } catch (err) {
          setResults((prev) => ({
            ...prev,
            [clip.id]: { error: err.message || "Processing failed" },
          }));
          setStatuses((prev) => ({ ...prev, [clip.id]: "error" }));
        }
      })
    );

    setIsGenerating(false);
  }, [clips]);

  const activeClips = clips.filter((c) => c.value?.trim?.() || c.file);

  return (
    <div className="min-h-screen bg-black text-foreground">
      <Header />

      <main className="mx-auto max-w-6xl px-6">
        <Hero
          clips={clips}
          inputTab={inputTab}
          onTabChange={setInputTab}
          onClipChange={handleClipChange}
          onAddClip={handleAddClip}
          onRemoveClip={handleRemoveClip}
          onGenerate={handleGenerate}
          isGenerating={isGenerating}
        />

        <HowItWorks />

        <ProcessingSection
          clips={activeClips.length ? activeClips : clips}
          statuses={statuses}
          results={results}
          sectionRef={resultsRef}
        />
      </main>

      <Footer />
    </div>
  );
}
