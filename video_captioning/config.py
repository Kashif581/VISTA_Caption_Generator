"""
config.py

Central, environment-driven configuration.

Track 2 injects no API key or model allowlist (unlike Track 1) -- credentials
and model choice are the team's own. Everything below is overridable via
environment variables so the same code runs locally (.env) and inside the
submission container (real env vars set at `docker run` time).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name, default):
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name, default):
    val = os.environ.get(name)
    return float(val) if val else default


def _env_int(name, default):
    val = os.environ.get(name)
    return int(val) if val else default


# ---------------------------------------------------------------------
# I/O contract (hackathon harness)
# ---------------------------------------------------------------------

INPUT_TASKS_PATH = os.environ.get("INPUT_TASKS_PATH", "/input/tasks.json")
OUTPUT_RESULTS_PATH = os.environ.get("OUTPUT_RESULTS_PATH", "/output/results.json")

WORK_DIR = Path(os.environ.get("WORK_DIR", "/tmp/video_captioning"))
WORK_DIR.mkdir(parents=True, exist_ok=True)

STYLES = ["formal", "sarcastic", "humorous_tech", "humorous_non_tech"]


# ---------------------------------------------------------------------
# Gemini API (Gemma 4) -- PRIMARY captioning backend, but ONLY when
# GEMINI_API_KEY is actually set. See pipeline/captioner.py for the full
# fallback order: Gemini -> Fireworks -> Groq. If GEMINI_API_KEY is unset
# (the default -- Track 2 injects no key for this either), Gemini is
# skipped entirely rather than attempted and immediately failed over, and
# Fireworks becomes primary -- see gemini_client.is_configured().
#
# Uses Gemini's OpenAI-compatible endpoint (not the native google-genai
# SDK), so it reuses the exact same llm_client.describe_scene /
# combine_scene_descriptions / generate_styled_captions code path as
# Fireworks and Groq -- same retry-on-empty-content handling, same output
# cleaning, same prompts. Fireworks is deliberately the FIRST fallback
# specifically to absorb Gemini rate limiting (the free/low tiers on Gemini
# are the tightest of the three backends) as well as any other Gemini
# failure; Groq remains the final fallback below that.
# ---------------------------------------------------------------------

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_BASE_URL = os.environ.get(
    "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
)

# gemma-4-26b-a4b-it is the smaller/faster MoE variant; gemma-4-31b-it is
# the larger dense variant. Both are vision-capable -- verify against your
# own Gemini account before relying on either in production.
GEMINI_VISION_MODEL = os.environ.get("GEMINI_VISION_MODEL", "gemma-4-26b-a4b-it")
GEMINI_TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", GEMINI_VISION_MODEL)

GEMINI_TIMEOUT_SECONDS = _env_float("GEMINI_TIMEOUT_SECONDS", 45.0)
GEMINI_MAX_RETRIES = _env_int("GEMINI_MAX_RETRIES", 3)

GEMINI_DESCRIBE_MAX_TOKENS = _env_int("GEMINI_DESCRIBE_MAX_TOKENS", 4000)
GEMINI_CAPTIONS_MAX_TOKENS = _env_int("GEMINI_CAPTIONS_MAX_TOKENS", 10000)
GEMINI_COMBINE_MAX_TOKENS = _env_int("GEMINI_COMBINE_MAX_TOKENS", 1500)


# ---------------------------------------------------------------------
# Fireworks AI (fallback -- see the Gemini section above for why this is no
# longer the primary backend)
# ---------------------------------------------------------------------

FIREWORKS_API_KEY = os.environ.get("FIREWORKS_API_KEY", "")
FIREWORKS_BASE_URL = os.environ.get(
    "FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1"
)

# Track 2 has no model allowlist -- any Fireworks model works. Vision-capable
# model describes the sampled keyframes; text model turns that description
# into the four styled captions. Point both at the same model unless you
# want to mix in a cheaper text-only model for the second call.
#
# IMPORTANT: verify these model IDs against your Fireworks account's current
# catalog before submitting -- model availability changes over time.
FIREWORKS_VISION_MODEL = os.environ.get(
    "FIREWORKS_VISION_MODEL",
    "accounts/fireworks/models/llama4-maverick-instruct-basic",
)
FIREWORKS_TEXT_MODEL = os.environ.get(
    "FIREWORKS_TEXT_MODEL",
    FIREWORKS_VISION_MODEL,
)

FIREWORKS_TIMEOUT_SECONDS = _env_float("FIREWORKS_TIMEOUT_SECONDS", 45.0)
FIREWORKS_MAX_RETRIES = _env_int("FIREWORKS_MAX_RETRIES", 3)

# Generous headroom for reasoning models (e.g. gpt-oss-120b, if used as
# FIREWORKS_TEXT_MODEL) that spend tokens "thinking" before answering --
# see the identical rationale on the Groq constants below, where this bit
# a real run: a low ceiling truncates mid-thought and silently degrades
# output rather than erroring, so err generous. Cheap for non-reasoning
# models too, since they stop early via EOS regardless of the ceiling.
FIREWORKS_DESCRIBE_MAX_TOKENS = _env_int("FIREWORKS_DESCRIBE_MAX_TOKENS", 4000)
FIREWORKS_CAPTIONS_MAX_TOKENS = _env_int("FIREWORKS_CAPTIONS_MAX_TOKENS", 10000)

# Headroom for the combine call that synthesizes per-scene descriptions into
# one video-level description (see llm_client.combine_scene_descriptions) --
# only invoked when a video has more than one detected scene.
FIREWORKS_COMBINE_MAX_TOKENS = _env_int("FIREWORKS_COMBINE_MAX_TOKENS", 1500)


# ---------------------------------------------------------------------
# Groq (captioning FALLBACK when Fireworks is unavailable or errors out --
# see pipeline/captioner.py. Also used as the primary transcription
# backend, see GROQ_API_KEY / GROQ_MODEL above.)
# ---------------------------------------------------------------------

GROQ_BASE_URL = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

# Split like the Fireworks vision/text pair: GROQ_VISION_MODEL must be
# vision-capable for describe_video(); GROQ_TEXT_MODEL only needs to follow
# JSON instructions reliably for the styled-captions step. Kept separate
# because qwen3.6-27b is a reasoning model (emits a literal <think> block
# ahead of its answer -- see llm_client.strip_reasoning) which is fine for
# the vision description but was breaking strict JSON-mode validation on
# the captions call; llama-3.3-70b-versatile doesn't have that problem.
GROQ_VISION_MODEL = os.environ.get("GROQ_VISION_MODEL", "qwen/qwen3.6-27b")
GROQ_TEXT_MODEL = os.environ.get("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile")

GROQ_CAPTION_TIMEOUT_SECONDS = _env_float("GROQ_CAPTION_TIMEOUT_SECONDS", 30.0)
GROQ_CAPTION_MAX_RETRIES = _env_int("GROQ_CAPTION_MAX_RETRIES", 3)

# Reasoning models spend tokens "thinking" before the final answer, and how
# much varies a lot by image content -- observed one clip finish in 1034
# completion tokens and two others still not done at 1600 (finish_reason
# "length" with zero usable answer after stripping <think>). llm_client.
# describe_video treats a truncated-to-empty answer as a hard failure
# rather than silently degrading, but it's better to just give it enough
# room in the first place.
#
# BUT: don't just crank this to the moon -- Groq's free/on-demand tier rate
# limits by tokens-per-minute (TPM) *requested* (prompt + max_tokens), not
# actual usage, and rejects the call outright (413) if the request alone
# exceeds the account's TPM ceiling. Confirmed on this account: limit is
# 8000 TPM, and max_tokens=10000 got rejected before generating anything.
# Keep enough margin under that ceiling for prompt tokens (which scale with
# MAX_KEYFRAMES -- more images = more prompt tokens).
GROQ_DESCRIBE_MAX_TOKENS = _env_int("GROQ_DESCRIBE_MAX_TOKENS", 4000)
GROQ_CAPTIONS_MAX_TOKENS = _env_int("GROQ_CAPTIONS_MAX_TOKENS", 2000)
GROQ_COMBINE_MAX_TOKENS = _env_int("GROQ_COMBINE_MAX_TOKENS", 1200)


# ---------------------------------------------------------------------
# Runtime budget
# ---------------------------------------------------------------------

# Hackathon hard cap is 10 minutes; leave headroom for process start/exit.
MAX_TOTAL_RUNTIME_SECONDS = _env_float("MAX_TOTAL_RUNTIME_SECONDS", 540.0)

MAX_PARALLEL_TASKS = _env_int("MAX_PARALLEL_TASKS", 3)

VIDEO_DOWNLOAD_TIMEOUT_SECONDS = _env_float("VIDEO_DOWNLOAD_TIMEOUT_SECONDS", 60.0)
MAX_VIDEO_BYTES = _env_int("MAX_VIDEO_BYTES", 500 * 1024 * 1024)  # 500MB safety cap


# ---------------------------------------------------------------------
# Vision pipeline
# ---------------------------------------------------------------------

MAX_KEYFRAMES = _env_int("MAX_KEYFRAMES", 6)
KEYFRAME_MAX_SIDE = _env_int("KEYFRAME_MAX_SIDE", 512)
KEYFRAME_JPEG_QUALITY = _env_int("KEYFRAME_JPEG_QUALITY", 85)

# Sprite-sheet extraction (see pipeline/scene.py): each detected scene
# becomes one composite image of tiles sampled roughly once per second,
# rather than one static frame -- gives the vision model motion/progression
# context for the whole scene from a single image, single API call.
SPRITE_TILE_SIZE = _env_int("SPRITE_TILE_SIZE", 220)  # px per tile side
SPRITE_MAX_COLS = _env_int("SPRITE_MAX_COLS", 4)
SPRITE_MAX_TILES = _env_int("SPRITE_MAX_TILES", 12)  # bounds grid to 4x3 by default
# The composite grid is larger than a single frame, so it needs more room
# than KEYFRAME_MAX_SIDE (512) before JPEG encoding or tiles become unreadable.
SPRITE_JPEG_MAX_SIDE = _env_int("SPRITE_JPEG_MAX_SIDE", 1024)

# Bounds how many per-scene describe_scene() calls run concurrently within a
# single task (see captioner._describe_scenes_parallel). Deliberately capped
# rather than firing all MAX_KEYFRAMES calls at once: empirically, throwing
# many concurrent requests at the same Fireworks account correlates with a
# higher rate of degenerate/malformed responses on the text-generation
# calls, so unbounded per-task parallelism would trade latency for
# reliability in the wrong direction -- especially stacked on top of
# MAX_PARALLEL_TASKS already running multiple tasks concurrently.
MAX_SCENE_DESCRIBE_PARALLEL = _env_int("MAX_SCENE_DESCRIBE_PARALLEL", 3)


# ---------------------------------------------------------------------
# Audio pipeline (best-effort, time-boxed -- see pipeline/audio.py)
# ---------------------------------------------------------------------

ENABLE_AUDIO_PIPELINE = _env_bool("ENABLE_AUDIO_PIPELINE", True)

# Per-task audio time budget. If transcription/separation/classification
# would blow this, later audio stages are skipped and captioning proceeds
# vision-only rather than risk the overall runtime cap.
AUDIO_STAGE_BUDGET_SECONDS = _env_float("AUDIO_STAGE_BUDGET_SECONDS", 45.0)

# Transcription is Groq-hosted whisper-large-v3 when GROQ_API_KEY is set
# (fast, no local model weight), falling back to a local faster-whisper
# model otherwise or if the Groq call fails. See pipeline/audio.py.
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "whisper-large-v3")
GROQ_TIMEOUT_SECONDS = _env_float("GROQ_TIMEOUT_SECONDS", 20.0)

# Local fallback: CTranslate2-backed, CPU friendly, no GPU-oriented alignment
# model, far smaller/faster than WhisperX on CPU.
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "small")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")

ENABLE_SOURCE_SEPARATION = _env_bool("ENABLE_SOURCE_SEPARATION", True)
ENABLE_BACKGROUND_CLASSIFICATION = _env_bool("ENABLE_BACKGROUND_CLASSIFICATION", True)

DEMUCS_MODEL = os.environ.get("DEMUCS_MODEL", "htdemucs")
AST_MODEL_ID = os.environ.get("AST_MODEL_ID", "MIT/ast-finetuned-audioset-10-10-0.4593")

# All local model weights are cached here and pre-downloaded at Docker build
# time (see download_models.py) so the container never hits the network for
# weights at runtime.
HF_HOME = os.environ.get("HF_HOME", "/opt/model_cache/huggingface")
os.environ.setdefault("HF_HOME", HF_HOME)
