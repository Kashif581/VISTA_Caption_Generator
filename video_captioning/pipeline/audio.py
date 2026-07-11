"""
audio.py

Best-effort, time-boxed audio understanding: transcription, optional
vocal/background separation (Demucs), and background sound tagging (AST).
Vision is the primary signal the LLM-Judge scores caption accuracy against;
audio is a supporting hint. Every stage is wrapped so a failure or a blown
time budget degrades gracefully to "no audio context" rather than failing
the whole task.

Transcription is two-tier: Groq-hosted whisper-large-v3 (GROQ_API_KEY) when
available -- no local model weight, fast -- falling back automatically to a
local faster-whisper model if no Groq key is configured or the API call
fails. GROQ_API_KEY is read purely from the environment at runtime, same as
FIREWORKS_API_KEY: never bake API keys into the image, since Track 2 images
must be publicly pullable and anything baked in is extractable by anyone.

Local models are loaded once per process (see the `_get_*` caches) and
pre-warmed at container build time (see download_models.py) so there's no
first-call download latency eating into the runtime budget.
"""

import gc
import logging
import os
import subprocess
import time

import config

logger = logging.getLogger(__name__)

_whisper_model = None
_ast_classifier = None
_demucs_model = None


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        _whisper_model = WhisperModel(
            config.WHISPER_MODEL_SIZE,
            device="cpu",
            compute_type=config.WHISPER_COMPUTE_TYPE,
            download_root=config.HF_HOME,
        )
    return _whisper_model


def _get_ast_classifier():
    global _ast_classifier
    if _ast_classifier is None:
        from transformers import pipeline

        _ast_classifier = pipeline(
            task="audio-classification",
            model=config.AST_MODEL_ID,
            device=-1,
        )
    return _ast_classifier


def _get_demucs_model():
    global _demucs_model
    if _demucs_model is None:
        from demucs.pretrained import get_model

        _demucs_model = get_model(config.DEMUCS_MODEL)
    return _demucs_model


def _has_audio_stream(video_path, timeout):
    """Cheap ffprobe check -- silent stock footage (common in b-roll: nature,
    animals, weather) has no audio stream at all, which would otherwise make
    every extract_audio() call fail loudly for no reason."""

    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=index",
        "-of", "csv=p=0",
        video_path,
    ]

    try:
        result = subprocess.run(cmd, timeout=timeout, capture_output=True, text=True)
        return bool(result.stdout.strip())
    except (subprocess.SubprocessError, OSError):
        # If ffprobe itself fails, let extract_audio's ffmpeg call be the
        # source of truth rather than assuming silence.
        return True


def extract_audio(video_path, out_wav_path, deadline):
    if time.monotonic() > deadline:
        return None

    remaining = max(1.0, deadline - time.monotonic())

    if not _has_audio_stream(video_path, min(5.0, remaining)):
        logger.info("No audio stream in %s -- skipping transcription/classification", video_path)
        return None

    cmd = [
        "ffmpeg", "-y", "-loglevel", "quiet",
        "-i", video_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        out_wav_path,
    ]

    remaining = max(1.0, deadline - time.monotonic())

    try:
        subprocess.run(cmd, timeout=remaining, check=True)
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("Audio extraction failed: %s", exc)
        return None

    if not os.path.exists(out_wav_path) or os.path.getsize(out_wav_path) == 0:
        return None

    return out_wav_path


def _transcribe_via_groq(wav_path, deadline):
    """Returns transcript text, or None if Groq isn't configured/usable --
    None (not "") signals the caller to fall back to the local model."""

    if not config.GROQ_API_KEY:
        return None

    remaining = deadline - time.monotonic()
    if remaining <= 1.0:
        return None

    try:
        from groq import Groq

        client = Groq(api_key=config.GROQ_API_KEY, timeout=min(config.GROQ_TIMEOUT_SECONDS, remaining))

        with open(wav_path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(wav_path), f.read()),
                model=config.GROQ_MODEL,
                temperature=0,
                response_format="verbose_json",
            )

        return (transcription.text or "").strip()

    except Exception as exc:
        logger.warning("Groq transcription failed, falling back to local model: %s", exc)
        return None


def _transcribe_local(wav_path, deadline):
    try:
        model = _get_whisper_model()
        segments, _info = model.transcribe(wav_path, beam_size=1, vad_filter=True)

        parts = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                parts.append(text)
            if time.monotonic() > deadline:
                break

        return " ".join(parts)

    except Exception as exc:
        logger.warning("Local transcription failed: %s", exc)
        return ""


def transcribe(wav_path, deadline):
    if time.monotonic() > deadline:
        return ""

    groq_result = _transcribe_via_groq(wav_path, deadline)
    if groq_result is not None:
        return groq_result

    return _transcribe_local(wav_path, deadline)


def separate_and_classify(wav_path, deadline):
    """
    Returns a short list of background sound labels (e.g. ["Music", "Wind"]),
    or [] if separation/classification is disabled, fails, or the deadline
    would be blown.
    """

    if not (config.ENABLE_SOURCE_SEPARATION and config.ENABLE_BACKGROUND_CLASSIFICATION):
        return []

    if time.monotonic() > deadline:
        return []

    try:
        import torch
        import torchaudio
        from demucs.apply import apply_model

        model = _get_demucs_model()

        wav, sr = torchaudio.load(wav_path)
        if sr != model.samplerate:
            wav = torchaudio.functional.resample(wav, sr, model.samplerate)
        if wav.shape[0] == 1:
            wav = wav.repeat(2, 1)

        if time.monotonic() > deadline:
            return []

        with torch.no_grad():
            sources = apply_model(model, wav[None], progress=False)[0]

        source_names = model.sources
        if "vocals" in source_names:
            bg_idx = [i for i, name in enumerate(source_names) if name != "vocals"]
            background = sources[bg_idx].sum(dim=0).mean(dim=0)
        else:
            background = wav.mean(dim=0)

        if time.monotonic() > deadline:
            return []

        target_sr = 16000
        if model.samplerate != target_sr:
            background = torchaudio.functional.resample(background, model.samplerate, target_sr)

        classifier = _get_ast_classifier()
        predictions = classifier({"array": background.numpy(), "sampling_rate": target_sr})

        return [p["label"] for p in predictions[:2]]

    except Exception as exc:
        logger.warning("Source separation/classification failed: %s", exc)
        return []
    finally:
        gc.collect()


def build_audio_context(video_path, work_dir, deadline):
    """
    Best-effort audio understanding for one video. Never raises; returns
    {"transcript": str, "background_sounds": list[str]}, both possibly
    empty if audio processing is disabled, fails, or runs out of budget.
    """

    context = {"transcript": "", "background_sounds": []}

    if not config.ENABLE_AUDIO_PIPELINE:
        return context

    stage_deadline = min(deadline, time.monotonic() + config.AUDIO_STAGE_BUDGET_SECONDS)
    wav_path = os.path.join(work_dir, f"audio_{os.getpid()}_{int(time.time() * 1000)}.wav")

    try:
        extracted = extract_audio(video_path, wav_path, stage_deadline)
        if not extracted:
            return context

        context["transcript"] = transcribe(extracted, stage_deadline)
        context["background_sounds"] = separate_and_classify(extracted, stage_deadline)

    finally:
        if os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except OSError:
                pass

    return context
