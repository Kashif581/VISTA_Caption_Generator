"""
captioner.py

Per-task orchestration: download -> keyframes -> (best-effort) audio ->
per-scene describe -> combine -> style captions.

Each detected scene/keyframe gets its own vision call (bounded parallel --
see _describe_scenes_parallel), rather than every keyframe sharing one
crowded multi-image prompt. When there's more than one scene, the per-scene
descriptions are synthesized into a single video-level description (see
_combine_or_pass_through) before the styled-captions step; a single-scene
clip (the common case for short stock clips) skips the combine call
entirely since there's nothing to combine.

Captioning backend order: Gemini/Gemma (primary, only if GEMINI_API_KEY is
set -- see gemini_client.is_configured()) -> Fireworks (fallback, first in
line specifically to absorb Gemini rate limiting as well as any other
Gemini failure) -> Groq (final fallback) -> generic fallback text (if every
backend fails). A backend is tried at ANY step -- a scene description, the
combine call, or the styling call -- failing sends the WHOLE task to the
next backend in the chain, never a mix of partial results from two
backends. Every stage degrades gracefully; a single task's failure never
crashes the batch, and a valid (if generic) caption is always returned for
every requested style so a partial failure never scores zero for a whole
clip ("missing styles score zero for that clip" per the rules).
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor

import config
from pipeline import audio, downloader, fireworks_client, gemini_client, groq_client, llm_client, scene

logger = logging.getLogger(__name__)


def _normalize_styles(requested):
    styles = [s for s in (requested or []) if s in config.STYLES]
    return styles or list(config.STYLES)


def _fallback_captions(styles, reason):
    text = f"A short video clip. ({reason})"
    return {style: text for style in styles}


def _describe_scenes_parallel(client_module, scenes, audio_context):
    """Runs one describe_scene() call per scene (hero frame + sprite sheet
    together, see pipeline/scene.py), bounded to MAX_SCENE_DESCRIBE_PARALLEL
    concurrent calls (see config.py for why this is deliberately capped
    rather than unbounded). Returns a list of {"timestamp_sec",
    "description"} in the same chronological order as `scenes`. Propagates
    the first exception -- any single scene failing fails the whole backend
    attempt, same all-or-nothing philosophy as the rest of the fallback
    chain."""

    total = len(scenes)
    results = [None] * total

    def _run(index, scene_data):
        description = client_module.describe_scene(
            scene_data["hero_frame"], scene_data["sprite"], scene_data["timestamp_sec"],
            audio_context["transcript"], audio_context["background_sounds"],
            index + 1, total,
        )
        return index, {"timestamp_sec": scene_data["timestamp_sec"], "description": description}

    max_workers = max(1, min(config.MAX_SCENE_DESCRIBE_PARALLEL, total))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_run, i, scene_data) for i, scene_data in enumerate(scenes)]
        for future in futures:
            index, result = future.result()
            results[index] = result

    return results


def _combine_or_pass_through(client_module, scene_descriptions):
    """A single scene has nothing to combine -- its own description IS the
    video description, so skip the extra LLM call entirely."""

    if len(scene_descriptions) == 1:
        return scene_descriptions[0]["description"]
    return client_module.combine_descriptions(scene_descriptions)


def _backend_chain():
    """Ordered list of (name, client_module) to try, primary first. Gemini
    is only included when GEMINI_API_KEY is actually set -- skipped
    entirely rather than attempted and immediately failed over, so a task
    with no Gemini key configured pays no extra latency for it."""

    chain = []
    if gemini_client.is_configured():
        chain.append(("gemini", gemini_client))
    chain.append(("fireworks", fireworks_client))
    chain.append(("groq", groq_client))
    return chain


def _describe_and_caption(scenes, audio_context, styles):
    """Tries each backend in _backend_chain() in order. Any failure at any
    step (a scene's vision call, the combine call, or the styling call) on
    one backend sends the WHOLE task to the next backend, never a mix of
    partial results. Raises only if every backend in the chain fails --
    caller's outer try/except turns that into generic fallback captions.
    Returns (description, captions, backend_name, scene_descriptions)."""

    last_exc = None

    for name, client_module in _backend_chain():
        try:
            scene_descriptions = _describe_scenes_parallel(client_module, scenes, audio_context)
            description = _combine_or_pass_through(client_module, scene_descriptions)
            captions = client_module.generate_styled_captions(description, styles)
            logger.info(
                "Backend used: %s | %d scene(s) | description: %r",
                name, len(scenes), description[:200],
            )
            return description, captions, name, scene_descriptions

        except Exception as exc:
            last_exc = exc
            logger.warning("%s captioning failed, falling back to next backend: %s", name, exc)

    raise last_exc


def _audio_status(audio_context):
    """Human-readable audio pipeline status for the demo frontend -- not
    used by the graded entrypoint, which only needs the transcript/sounds
    themselves (see _describe_and_caption)."""

    if not config.ENABLE_AUDIO_PIPELINE:
        return {
            "enabled": False,
            "transcript": "",
            "background_sounds": [],
            "note": "Audio pipeline disabled for this run.",
        }

    transcript = audio_context["transcript"]
    sounds = audio_context["background_sounds"]

    note = "" if (transcript or sounds) else "No speech or usable audio track detected in this clip."

    return {
        "enabled": True,
        "transcript": transcript,
        "background_sounds": sounds,
        "note": note,
    }


def caption_task(task, deadline):
    """
    task: {"task_id": str, "video_url": str, "styles": list[str] (optional)}
    deadline: absolute time.monotonic() value this task should finish by.

    Returns {"task_id": ..., "captions": {style: caption, ...}}
    """

    task_id = task["task_id"]
    video_url = task["video_url"]
    styles = _normalize_styles(task.get("styles"))

    local_path = None
    started = time.monotonic()

    try:
        local_path = downloader.fetch_video(video_url, deadline)

        info = scene.get_video_info(local_path)
        scenes = scene.extract_keyframes(local_path, info)

        if not scenes:
            raise RuntimeError("No keyframes could be extracted from video")

        audio_context = audio.build_audio_context(local_path, str(config.WORK_DIR), deadline)

        description, captions, _backend, _scenes = _describe_and_caption(scenes, audio_context, styles)

        # Guarantee non-empty captions for every requested style, even if the
        # styling call dropped a key or returned malformed JSON.
        for style in styles:
            if not captions.get(style):
                captions[style] = description.strip()[:150] if description else "A short video clip."

        logger.info(
            "Task %s captioned in %.1fs (%d scene(s), audio=%s)\n  captions: %s",
            task_id, time.monotonic() - started, len(scenes),
            bool(audio_context["transcript"] or audio_context["background_sounds"]),
            captions,
        )

        return {"task_id": task_id, "captions": captions}

    except Exception as exc:
        logger.exception("Task %s failed: %s", task_id, exc)
        return {"task_id": task_id, "captions": _fallback_captions(styles, "processing error")}

    finally:
        if local_path:
            downloader.cleanup(local_path)


def process_task_full(task, deadline, local_path=None):
    """
    Like caption_task(), but returns the full stage-by-stage pipeline
    breakdown (keyframe thumbnails, audio status, description, timings,
    which backend answered) for the demo frontend. Not used by the graded
    entrypoint (run_submission.py), which only needs task_id + captions.

    `local_path`: if the caller already has the video on disk (e.g. an
    uploaded file in the FastAPI demo), pass its path directly to skip the
    download step. Otherwise task["video_url"] is fetched as usual.
    """

    task_id = task["task_id"]
    styles = _normalize_styles(task.get("styles"))
    started = time.monotonic()
    stages = {}

    try:
        t0 = time.monotonic()
        if local_path is None:
            local_path = downloader.fetch_video(task["video_url"], deadline)
        stages["download_sec"] = round(time.monotonic() - t0, 2)

        t0 = time.monotonic()
        info = scene.get_video_info(local_path)
        scenes = scene.extract_keyframes(local_path, info)
        stages["scene_detect_sec"] = round(time.monotonic() - t0, 2)

        if not scenes:
            raise RuntimeError("No keyframes could be extracted from video")

        keyframes_out = [
            {
                "timestamp_sec": round(scene_data["timestamp_sec"], 2),
                "image": f"data:image/jpeg;base64,{llm_client.encode_frame_jpeg(scene_data['hero_frame'])}",
                "sprite": (
                    f"data:image/jpeg;base64,{llm_client.encode_frame_jpeg(scene_data['sprite'])}"
                    if scene_data["sprite"] is not None else None
                ),
            }
            for scene_data in scenes
        ]

        t0 = time.monotonic()
        audio_context = audio.build_audio_context(local_path, str(config.WORK_DIR), deadline)
        stages["audio_sec"] = round(time.monotonic() - t0, 2)
        audio_out = _audio_status(audio_context)

        t0 = time.monotonic()
        description, captions, backend_used, scene_descriptions = _describe_and_caption(
            scenes, audio_context, styles
        )
        stages["captioning_sec"] = round(time.monotonic() - t0, 2)

        for style in styles:
            if not captions.get(style):
                captions[style] = description.strip()[:150] if description else "A short video clip."

        # Attach each scene's own description to its keyframe thumbnail so
        # the demo frontend can show "what the model saw" per scene, not
        # just the final combined description.
        for kf, sd in zip(keyframes_out, scene_descriptions):
            kf["description"] = sd["description"]

        return {
            "task_id": task_id,
            "duration_sec": round(info["duration_sec"], 2),
            "keyframes": keyframes_out,
            "audio": audio_out,
            "description": description,
            "captions": captions,
            "backend_used": backend_used,
            "stages": stages,
            "total_sec": round(time.monotonic() - started, 2),
        }

    finally:
        if local_path:
            downloader.cleanup(local_path)
