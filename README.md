# Video Captioning Agent — AMD Hackathon Track 2

Watches a short video clip and produces a caption in four styles — formal,
sarcastic, humorous_tech, humorous_non_tech — grounded in what actually
happens in the clip: per-scene visuals, motion across time, and audio
(speech + background sound).

*Vision/text backend order:* *Gemma 4 via the Google Gemini API*
(primary, only when GEMINI_API_KEY is set) → *Fireworks AI* (fallback —
first in line specifically to absorb Gemini rate limiting, since Gemini's
free/low tiers are the tightest of the three) → *Groq* (final fallback).
Every stage — a scene description, the combine step, or the styling call —
that fails or errors out on one backend retries the whole task on the next
backend in the chain, so a single bad response never produces a broken or
empty caption. If GEMINI_API_KEY is left unset, Gemini is skipped
entirely (not attempted-then-failed-over) and Fireworks becomes primary —
see pipeline/captioner.py::_backend_chain().

---

## Table of contents

- [Architecture](#architecture)
- [Backend fallback chain](#backend-fallback-chain)
- [Pipeline stages in detail](#pipeline-stages-in-detail)
- [Why per-scene, not per-video](#why-per-scene-not-per-video)
- [Output cleanliness](#output-cleanliness)
- [Audio pipeline notes](#audio-pipeline-notes)
- [Demo frontend](#demo-frontend)
- [Setup](#setup)
- [Running it](#running-it)
- [Build and test the submission container](#build-and-test-the-submission-container)
- [Submit](#submit)
- [Secrets](#secrets)
- [Tuning knobs](#tuning-knobs)

---

## Demo



https://github.com/user-attachments/assets/836733ab-bf76-49ae-9f13-a3f1da0b5d5a


## Display
<img width="1000" height="1000" alt="view" src="https://github.com/user-attachments/assets/4ac22d32-e65a-413e-986e-eb6c5140efaf" />



## Architecture

mermaid
flowchart TD
    A["tasks.json\n(video_url, styles)"] --> B[download clip]
    B --> C["scene detection\n(OpenCV histogram diff)"]
    C --> D["per-scene image pair:\nhero frame + sprite sheet"]
    B --> E["audio pipeline\n(transcript + background sounds)"]

    D --> F
    E --> F

    subgraph F["per scene, bounded parallel (MAX_SCENE_DESCRIBE_PARALLEL)"]
        direction LR
        F1["scene 1: describe()"]
        F2["scene 2: describe()"]
        F3["scene N: describe()"]
    end

    F --> G{"more than\none scene?"}
    G -- "yes" --> H["combine():\nN scene descriptions\n-> 1 video description"]
    G -- "no, single scene" --> I["pass through\n(nothing to combine)"]
    H --> J["style():\ndescription -> 4 captions\n(formal / sarcastic /\nhumorous_tech / humorous_non_tech)"]
    I --> J
    J --> K["results.json"]

    style A fill:#1e293b,color:#fff
    style K fill:#1e293b,color:#fff


Every describe() / combine() / style() call goes through the
[backend fallback chain](#backend-fallback-chain) below — the diagram above
shows the pipeline shape, not which backend answered.
<img width="1405" height="559" alt="Workflow" src="https://github.com/user-attachments/assets/ec695398-5b74-4643-9eaf-be3cc3426cbf" />


## Backend fallback chain

mermaid
flowchart LR
    subgraph "Primary (only if GEMINI_API_KEY set)"
        GEM["Gemini API\nGemma 4\n(vision + text)"]
    end
    subgraph "Fallback 1"
        FW["Fireworks AI\n(OpenAI-compatible)"]
    end
    subgraph "Fallback 2"
        GRQ["Groq\n(OpenAI-compatible)"]
    end

    GEM -- "any call fails,\nrate-limited, or\nreturns empty content" --> FW
    FW -- "any call fails or\nreturns empty content" --> GRQ
    GRQ -- "still fails" --> FB["generic fallback caption\n(never a missing style)"]


- pipeline/captioner.py::_backend_chain() builds the ordered list of
  backends to try. Gemini is only added when gemini_client.is_configured()
  is true (i.e. GEMINI_API_KEY is set) — with no key, the chain is just
  [fireworks, groq] and Fireworks is primary, no code branch elsewhere
  has to change.
- The fallback is *all-or-nothing per task*: if any single scene's
  description call, the combine call, or the styling call fails on the
  current backend — including a 429 rate-limit response — the whole task
  retries on the next backend from scratch, rather than mixing partial
  results from two backends.
- Within a single backend, a call that returns HTTP 200 but empty/degenerate
  content (a real failure mode seen from some hosted models) is retried
  against the same backend up to its configured retry count before the
  chain moves on — a 200 status alone is never treated as success.
- If every backend in the chain fails, the task still returns a valid,
  non-empty caption for every requested style (a short generic fallback
  line) — a missing style scores zero, so the pipeline never lets that
  happen.
- Gemini is accessed through its *OpenAI-compatible endpoint*
  (GEMINI_BASE_URL, default
  https://generativelanguage.googleapis.com/v1beta/openai/), not the
  native google-genai SDK — this means pipeline/gemini_client.py reuses
  the exact same request-building, retry, and output-cleaning code in
  pipeline/llm_client.py as Fireworks and Groq, instead of a separate
  SDK-specific implementation.

## Pipeline stages in detail

| Stage | Module | What it does |
|---|---|---|
| Download | pipeline/downloader.py | Fetches the clip, enforces VIDEO_DOWNLOAD_TIMEOUT_SECONDS and MAX_VIDEO_BYTES |
| Scene detection | pipeline/scene.py | OpenCV histogram-based cut detection, capped at MAX_KEYFRAMES scene windows |
| Per-scene images | pipeline/scene.py | For each scene: one *hero frame* (full-resolution, temporal midpoint) + one *sprite sheet* (grid of ~1 frame/sec, timestamp-labeled) — see below |
| Audio | pipeline/audio.py | Best-effort, time-boxed transcript + background-sound tags |
| Describe | pipeline/*_client.py + pipeline/prompts.py | One vision call per scene: hero frame + sprite sheet + audio context → one description |
| Combine | same | N per-scene descriptions → one video-level description (skipped if only 1 scene) |
| Style | same | Description → 4 styled captions, strict JSON |
| Orchestration | pipeline/captioner.py | Wires the above together per task, owns the fallback chain and the never-empty-caption guarantee |
| Entrypoint (graded) | run_submission.py | Reads /input/tasks.json, processes tasks concurrently within the global time budget, writes /output/results.json |
| Entrypoint (demo) | app.py | FastAPI wrapper exposing /api/process with full stage-by-stage output for the frontend/ UI |

### The two images per scene

mermaid
flowchart LR
    S["scene window\n(start_frame..end_frame)"] --> SAMP["sample ~1 frame/sec\n(capped at SPRITE_MAX_TILES)"]
    SAMP --> HERO["pick middle sampled frame\n= hero frame\n(full resolution, sent as-is)"]
    SAMP --> GRID["all sampled frames\n-> letterboxed tiles\n-> timestamp-labeled\n-> arranged into a grid\n= sprite sheet"]
    HERO --> CALL["one describe() call:\nhero frame + sprite sheet\n+ audio context"]
    GRID --> CALL


- *Hero frame* gives the model a clean, full-resolution reference for fine
  detail — hair color, clothing, small text, background objects.
- *Sprite sheet* gives the model motion/progression context for the whole
  scene ("starts sitting, walks toward camera, tail raised by the last
  tile") from a single image and a single API call — not one call per
  second of footage.
- If a scene only has one usable sampled frame (very short scene), the
  sprite sheet is skipped entirely and only the hero frame is sent — no
  point building a 1-tile grid.

## Why per-scene, not per-video

The original design crammed every sampled keyframe from the whole video
into one prompt as a stack of images. That splits the model's attention
across up to MAX_KEYFRAMES images at once, and gets worse the longer and
more visually varied the video is — in testing this produced captions that
were generic, or anchored on whichever frame happened to dominate the
prompt, or (worst case) identical across all 4 styles because the
underlying description was too thin to differentiate.

The current design instead:

1. Detects scene boundaries and describes *each scene independently*, so
   the model gives its full attention to one scene (one hero frame + one
   motion-context sprite sheet) at a time.
2. *Combines* the per-scene descriptions into a single coherent
   video-level description with a dedicated text call — only when there's
   more than one scene to combine.
3. Turns that single description into the four styled captions.

This keeps the API call count bounded regardless of scene duration (a
sprite sheet encodes up to SPRITE_MAX_TILES seconds of motion in one
image/call), while still scaling call count with scene count — a 3-scene
video costs 3 describe calls + 1 combine call + 1 style call, a 1-scene
video costs 1 describe call + 1 style call.

## Output cleanliness

All caption/description text passes through llm_client.clean_text()
before being returned anywhere (results.json, the demo API, the
frontend):

- Strips markdown formatting (**bold**, *italic*, # headers, -/*
  bullets, backticks) that models add despite being told not to.
- Strips control characters.
- Strips outer quote-wrapping some models add around their answer.
- Normalizes "smart" Unicode punctuation — curly quotes, en/em dashes,
  non-breaking hyphens, ellipsis characters — to plain ASCII equivalents,
  so nothing renders as a stray symbol or box on the frontend.

llm_client.strip_reasoning() additionally strips literal <think>...</think>
blocks that reasoning-capable models sometimes emit ahead of their answer.

Every describe/combine/style call also has a *retry-on-empty-content*
guard: an HTTP 200 with degenerate or empty text (a real failure mode, not
hypothetical) is retried against the same backend before the fallback chain
gives up on it — this is what makes the "identical/truncated captions"
failure mode structurally impossible rather than just unlikely.

## Audio pipeline notes

- Every task gets an AUDIO_STAGE_BUDGET_SECONDS window (default 45s). If
  extraction, transcription, or separation+classification would blow that
  window — or the overall runtime deadline — the remaining audio stages are
  skipped and captioning proceeds vision-only. It never blocks or fails the
  task.
- Transcription: Groq-hosted whisper-large-v3 when GROQ_API_KEY is set
  (fast, no local model weight), falling back to a local faster-whisper
  model otherwise or if the API call fails.
- Vocal/background separation (Demucs) and background sound tagging (AST)
  run on top of that, each independently time-boxed.
- Model weights are pre-downloaded at *Docker build time*
  (download_models.py), not at container start, so there's no first-call
  download latency eating into the runtime budget.
- Fastest lever if audio isn't earning its runtime cost:
  ENABLE_AUDIO_PIPELINE=false (or keep transcription but drop the heavier
  stages with ENABLE_SOURCE_SEPARATION=false /
  ENABLE_BACKGROUND_CLASSIFICATION=false).

## Demo frontend

../frontend/ is a React + Vite UI (not used by the grader) that calls this
app's /api/process endpoint and renders, per clip:

- a video preview
- the pipeline stage timeline (download / scene-detect / audio / captioning)
  with real timings and which backend answered
- the keyframe breakdown — hero frame, with a toggle to view the sprite
  sheet motion grid, plus that scene's own description
- audio status (transcript, background sounds, or a clear "none detected"
  note)
- the caption in all 4 styles, grid or single-style view

bash
# terminal 1 -- backend
cd video_captioning && source .venv/bin/activate
uvicorn app:app --reload --port 8000

# terminal 2 -- frontend
cd ../frontend
cp .env.example .env   # VITE_API_BASE_URL, defaults to localhost:8000
npm install
npm run dev


## Setup

bash
cd vista/video_captioning
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env


Edit .env:

bash
# primary backend
GEMINI_API_KEY=...
GEMINI_VISION_MODEL=gemma-4-31b   # or whatever id your Gemini account exposes

# fallback backends
FIREWORKS_API_KEY=...
GROQ_API_KEY=...


Track 2 has no model allowlist and no injected credentials — all of the
above are your own account keys, and it's worth re-verifying each model ID
against your account's current catalog before submitting, since
availability changes over time.

## Running it

### Batch entrypoint against the example clips (what the grader runs)

bash
mkdir -p outputs
INPUT_TASKS_PATH=examples/tasks.json OUTPUT_RESULTS_PATH=outputs/results.json \
  python run_submission.py

cat outputs/results.json


### FastAPI demo, single clip

bash
uvicorn app:app --reload --port 8000

curl -X POST localhost:8000/caption \
  -H 'content-type: application/json' \
  -d '{"video_url": "https://storage.googleapis.com/amd-hackathon-clips/1860079-uhd_2560_1440_25fps.mp4"}'


## Build and test the submission container

Credentials are baked into .env at build time (see [Secrets](#secrets)),
so docker run needs no -e flags for the happy path — though any real env
var you do pass still wins over what's in the image.

bash
docker build -t video-captioning:latest .

mkdir -p input output
cp examples/tasks.json input/tasks.json

docker run --rm \
  -v "$(pwd)/input:/input" \
  -v "$(pwd)/output:/output" \
  video-captioning:latest

cat output/results.json


## Submit

bash
docker buildx build --platform linux/amd64 --tag <your-registry>/video-captioning:latest --push .


The linux/amd64 manifest is required even if you're building on Apple
Silicon — see the participant guide's Image Architecture section.

## Secrets

Unlike Track 1 (which gets a key injected by the harness), Track 2 has no
fixed env-var contract the grading harness fills in for you — so this
container loads its own .env at startup (config.py's load_dotenv()
call) rather than depending on docker run -e flags the grader may not
pass. Concretely: .env is *not* excluded by .dockerignore, so whatever
is in it at docker build time ships inside the image.

That means your API keys become part of a publicly pullable image. There is
no way to fully eliminate that risk while also satisfying "must load on
startup with no external configuration" — so contain the blast radius
instead:

- *Use dedicated keys for this image* (Gemini, Fireworks, Groq), not your
  main accounts. If one leaks, you're revoking a key scoped to just this
  submission.
- *Set a hard spend cap / usage limit* on each key before you push the
  image.
- *Rotate keys after the hackathon*, and immediately if you ever paste one
  into a chat, ticket, or log — treat anything pasted outside .env as
  already compromised.
- Real runtime env vars still win over the baked-in .env: load_dotenv()
  uses override=False by default, so a real environment variable set by
  docker run -e or the submission platform takes precedence.

To build with real credentials:

bash
cp .env.example .env
edit .env with your real GEMINI_API_KEY / FIREWORKS_API_KEY / GROQ_API_KEY
docker build -t video-captioning:latest .


## Tuning knobs

Env vars, see config.py / .env.example for the full list and defaults.

| Variable | Default | Purpose |
|---|---|---|
| MAX_TOTAL_RUNTIME_SECONDS | 540 | Global wall-clock budget across all tasks (hard cap is 600s) |
| MAX_PARALLEL_TASKS | 3 | Concurrent clips processed via a thread pool |
| MAX_KEYFRAMES | 6 | Max scenes sampled per clip — each gets its own describe call |
| MAX_SCENE_DESCRIBE_PARALLEL | 3 | Concurrent per-scene vision calls within one task — capped since heavy concurrent load on one backend account correlates with more malformed responses |
| SPRITE_TILE_SIZE | 220 | Pixels per tile side in a scene's sprite sheet |
| SPRITE_MAX_COLS | 4 | Grid width for the sprite sheet |
| SPRITE_MAX_TILES | 12 | Max frames (~1/sec) tiled per scene, regardless of scene duration |
| SPRITE_JPEG_MAX_SIDE | 1024 | Max side when JPEG-encoding the composite grid before sending — larger than a single frame's KEYFRAME_MAX_SIDE (512) so tiles stay legible |
| ENABLE_AUDIO_PIPELINE | true | Master switch for transcript/background-sound context |
| AUDIO_STAGE_BUDGET_SECONDS | 45 | Per-task ceiling before audio stages are skipped |
| WHISPER_MODEL_SIZE | small | faster-whisper model size (tiny/base/small/medium) |

Longer, multi-scene clips cost more than one vision call: up to
MAX_KEYFRAMES per-scene calls (bounded parallel) + 1 combine call + 1
captions call, versus a single-scene clip's 2 calls total. This trades
latency/cost for accuracy on longer videos — if the eval set turns out to
be exclusively short single-take clips, lowering MAX_KEYFRAMES trims cost
without losing coverage; if it includes longer multi-scene footage, this is
what makes captions accurate across the whole clip instead of just whichever
frame happened to dominate a single crowded prompt.





