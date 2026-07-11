"""
llm_client.py

Provider-agnostic chat-completions helpers shared by fireworks_client.py
(primary) and groq_client.py (fallback). Both are OpenAI-compatible APIs --
the only real difference between them is which base_url/api_key/model to
use, so the actual request-building and response-parsing logic lives here
once instead of being duplicated per provider.
"""

import base64
import logging
import re
import time

import cv2
from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError

import config
from pipeline.prompts import (
    build_caption_prompt,
    build_combine_prompt,
    build_scene_description_prompt,
    parse_caption_json,
)

logger = logging.getLogger(__name__)

RETRYABLE_ERRORS = (APIConnectionError, APITimeoutError, RateLimitError, APIError)

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

_MD_HEADER_RE = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_MD_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)([^*\n]+?)\*(?!\*)")
_MD_BOLD_UNDERSCORE_RE = re.compile(r"__(.+?)__")
_MD_BULLET_RE = re.compile(r"^\s*[-*•]\s+", re.MULTILINE)
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MULTI_SPACE_RE = re.compile(r"[ \t]+")
_MULTI_BLANK_LINE_RE = re.compile(r"\n\s*\n+")

# Vision models (kimi-k2p6 especially) reach for "typographic" Unicode
# punctuation -- non-breaking hyphens, en/em dashes, curly quotes -- instead
# of plain ASCII, even when told to write plain text. Renders fine in a
# browser, but reads as stray symbol codes in a terminal, results.json, or
# any plain-text consumer, so normalize to the ASCII equivalent.
_UNICODE_PUNCT_MAP = {
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-",
    "‘": "'", "’": "'", "‚": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "″": '"',
    "…": "...", " ": " ", "•": "-",
}
_UNICODE_PUNCT_RE = re.compile("|".join(re.escape(k) for k in _UNICODE_PUNCT_MAP))


def clean_text(text):
    """Strips markdown formatting, stray control characters, non-ASCII
    "smart" punctuation, and outer quoting from LLM output so the
    caption/description text a human (or the demo frontend) reads is plain,
    clean prose -- models often wrap answers in **bold**, bullet points, a
    leading/trailing quote, or typographic dashes/quotes even when the
    prompt asks for plain ASCII text, especially under json mode or after a
    stripped <think> block."""

    if not text:
        return ""

    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = _MD_HEADER_RE.sub("", cleaned)
    cleaned = _MD_BOLD_RE.sub(r"\1", cleaned)
    cleaned = _MD_BOLD_UNDERSCORE_RE.sub(r"\1", cleaned)
    cleaned = _MD_ITALIC_RE.sub(r"\1", cleaned)
    cleaned = _MD_BULLET_RE.sub("", cleaned)
    cleaned = cleaned.replace("`", "")
    cleaned = _UNICODE_PUNCT_RE.sub(lambda m: _UNICODE_PUNCT_MAP[m.group(0)], cleaned)
    cleaned = _CONTROL_CHARS_RE.sub("", cleaned)
    cleaned = _MULTI_SPACE_RE.sub(" ", cleaned)
    cleaned = _MULTI_BLANK_LINE_RE.sub("\n", cleaned)
    cleaned = cleaned.strip()

    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in "\"'":
        cleaned = cleaned[1:-1].strip()

    return cleaned


def strip_reasoning(text):
    """Reasoning models (e.g. Qwen3 on Groq) emit their chain-of-thought as
    a literal <think>...</think> block ahead of the actual answer in the
    same `content` field -- there's no separate API field to pull the final
    answer from, so this has to be done client-side. Also handles the case
    where max_tokens cut generation off mid-thought (no closing tag): drop
    the dangling reasoning rather than returning it as if it were content."""

    if not text:
        return text

    cleaned = _THINK_BLOCK_RE.sub("", text).strip()

    if "<think>" in cleaned.lower() and "</think>" not in cleaned.lower():
        idx = cleaned.lower().rfind("<think>")
        cleaned = cleaned[:idx].strip()

    return cleaned


def encode_frame_jpeg(frame_bgr, max_side=None):
    max_side = max_side or config.KEYFRAME_MAX_SIDE
    height, width = frame_bgr.shape[:2]
    scale = max_side / max(height, width)
    if scale < 1.0:
        frame_bgr = cv2.resize(frame_bgr, (int(width * scale), int(height * scale)))

    ok, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, config.KEYFRAME_JPEG_QUALITY])
    if not ok:
        raise RuntimeError("Failed to encode keyframe as JPEG")

    return base64.b64encode(buf.tobytes()).decode("ascii")


def chat_with_retry(client, max_retries, **kwargs):
    last_exc = None
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(**kwargs)
        except RETRYABLE_ERRORS as exc:
            last_exc = exc
            wait = min(2 ** attempt, 8)
            logger.warning(
                "Chat call failed (attempt %d/%d): %s -- retrying in %ss",
                attempt + 1, max_retries, exc, wait,
            )
            if attempt < max_retries - 1:
                time.sleep(wait)
    raise last_exc


def describe_scene(
    client, model, max_retries, hero_frame_bgr, sprite_bgr, timestamp_sec, transcript, background_sounds,
    scene_index=1, total_scenes=1, max_tokens=220,
):
    """
    Describes ONE scene. Callers run this once per detected scene (see
    captioner._describe_scenes_parallel) instead of sending every keyframe
    in a single crowded multi-image call -- each scene gets the model's
    full attention rather than competing for it with up to
    MAX_KEYFRAMES-1 other images in the same prompt, which matters more as
    videos get longer and have more distinct scenes.

    hero_frame_bgr: one clean, full-resolution frame from the scene's
    midpoint, always present -- encoded at the normal KEYFRAME_MAX_SIDE for
    fine detail.
    sprite_bgr: a grid of the scene's frames sampled ~1/sec (see
    pipeline/scene.py), or None if the scene was too short to tile. Sent as
    a second image alongside the hero frame when present, encoded larger
    (SPRITE_JPEG_MAX_SIDE) so individual tiles stay legible.

    Returns a factual, style-neutral description of just this scene (str).
    """

    content = [
        {
            "type": "text",
            "text": build_scene_description_prompt(
                transcript, background_sounds, scene_index, total_scenes, timestamp_sec,
                has_sprite=sprite_bgr is not None,
            ),
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{encode_frame_jpeg(hero_frame_bgr)}"},
        },
    ]

    if sprite_bgr is not None:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,"
                       f"{encode_frame_jpeg(sprite_bgr, max_side=config.SPRITE_JPEG_MAX_SIDE)}"
            },
        })

    response = chat_with_retry(
        client, max_retries,
        model=model,
        messages=[{"role": "user", "content": content}],
        max_tokens=max_tokens,
        temperature=0.2,
    )

    raw_content = response.choices[0].message.content.strip()
    description = clean_text(strip_reasoning(raw_content))

    usage = getattr(response, "usage", None)
    finish_reason = response.choices[0].finish_reason
    logger.info(
        "describe_scene[%s] scene=%d/%d: finish_reason=%s tokens(prompt/completion)=%s/%s "
        "raw_len=%d stripped_len=%d reasoning_stripped=%s",
        model, scene_index, total_scenes, finish_reason,
        getattr(usage, "prompt_tokens", "?"), getattr(usage, "completion_tokens", "?"),
        len(raw_content), len(description), len(raw_content) != len(description),
    )

    if finish_reason == "length" and not description:
        logger.warning(
            "describe_scene[%s] scene=%d/%d: hit max_tokens=%d with no answer yet -- raw tail: %r",
            model, scene_index, total_scenes, max_tokens, raw_content[-200:],
        )

    if not description:
        # A reasoning model whose <think> block ran past max_tokens before
        # reaching an answer strips down to "" here -- surfacing that as a
        # real failure (rather than silently handing an empty description
        # to the next stage) is what lets the caller's fallback chain
        # actually kick in, instead of generating content-free captions
        # from nothing and calling it a success.
        raise RuntimeError(
            f"Model '{model}' produced no answer for scene {scene_index}/{total_scenes} "
            f"within max_tokens={max_tokens} (reasoning likely truncated before an answer) "
            "-- treating as a failure."
        )

    return description


def combine_scene_descriptions(client, model, max_retries, scene_descriptions, max_tokens=1200):
    """
    scene_descriptions: list of {"timestamp_sec": float, "description": str},
    chronological, length >= 2 (callers skip this entirely for a single
    scene -- see captioner._combine_or_pass_through).

    Synthesizes the per-scene descriptions into one coherent video-level
    description (str), which then feeds generate_styled_captions()
    unchanged. Same retry-on-empty-content pattern as
    generate_styled_captions() below: this is a text-only synthesis call on
    the same TEXT_MODEL that's occasionally produced degenerate output for
    the styled-captions step, so a 200 OK here doesn't guarantee a usable
    body either.
    """

    prompt = build_combine_prompt(scene_descriptions)
    messages = [{"role": "user", "content": prompt}]

    combined = ""
    raw = ""

    for attempt in range(max_retries):
        response = chat_with_retry(
            client, max_retries,
            model=model, messages=messages, max_tokens=max_tokens, temperature=0.3,
        )

        raw = strip_reasoning(response.choices[0].message.content)
        combined = clean_text(raw)

        if combined:
            # A properly-tagged <think> block gets stripped above, but some
            # models narrate their reasoning as plain untagged prose instead
            # ("The user wants me to synthesize... Let me draft...") when
            # asked to satisfy several constraints at once (sentence count,
            # detail retention, single-paragraph). Nothing can reliably
            # detect that after the fact, so this is a diagnostic tripwire,
            # not a filter: 6-9 sentences of plain prose should be well
            # under this length, so anything past it is worth a look in the
            # logs even though it's still returned as-is.
            if len(combined) > 1800:
                logger.warning(
                    "combine_scene_descriptions[%s]: result is %d chars, well over the "
                    "6-9 sentence target -- possible unstripped reasoning narration, check "
                    "output quality: %r",
                    model, len(combined), combined[:300],
                )
            break

        logger.warning(
            "combine_scene_descriptions[%s]: empty result on attempt %d/%d from %d scenes -- raw tail: %r",
            model, attempt + 1, max_retries, len(scene_descriptions), raw[-200:] if raw else raw,
        )

    if not combined:
        raise RuntimeError(
            f"Model '{model}' produced no combined summary from {len(scene_descriptions)} "
            f"scene descriptions after {max_retries} attempt(s) -- treating as a failure."
        )

    return combined


def generate_styled_captions(client, model, max_retries, description, styles, max_tokens=400):
    """Returns {style: caption} for each requested style.

    A 200 OK response doesn't guarantee usable content -- models occasionally
    degenerate into repetitive garbage (e.g. gpt-oss-120b returning
    "(no extra) (no extra) ..." ad infinitum) under json_object mode instead
    of erroring, which chat_with_retry's exception-based retry can't catch
    since nothing raised. So this retries the call itself, same model, up to
    max_retries times, as long as every requested style comes back empty.
    If it's still fully empty after that, it raises -- same contract as
    describe_scene() -- so the caller's Fireworks -> Groq fallback chain
    actually engages instead of accepting an all-empty captions dict (which
    caption_task() would otherwise paper over with the same truncated
    description repeated identically across all 4 styles)."""

    prompt = build_caption_prompt(description, styles)
    messages = [{"role": "user", "content": prompt}]

    captions = {}
    raw = ""

    for attempt in range(max_retries):
        try:
            response = chat_with_retry(
                client, max_retries,
                model=model, messages=messages, max_tokens=max_tokens, temperature=0.7,
                response_format={"type": "json_object"},
            )
        except RETRYABLE_ERRORS as exc:
            # Some models/deployments reject response_format -- fall back to
            # a plain call and rely on prompt-enforced JSON + best-effort
            # parsing.
            logger.warning("json_object response_format rejected, retrying plain: %s", exc)
            response = chat_with_retry(
                client, max_retries,
                model=model, messages=messages, max_tokens=max_tokens, temperature=0.7,
            )

        raw = strip_reasoning(response.choices[0].message.content)
        captions = parse_caption_json(raw, styles)
        captions = {style: clean_text(value) for style, value in captions.items()}

        if any(captions.values()):
            break

        logger.warning(
            "generate_styled_captions[%s]: all styles empty on attempt %d/%d -- raw tail: %r",
            model, attempt + 1, max_retries, raw[-200:] if raw else raw,
        )

    missing = [s for s in styles if not captions.get(s)]
    if missing:
        logger.warning(
            "generate_styled_captions[%s]: missing/empty styles %s -- raw tail: %r",
            model, missing, raw[-200:] if raw else raw,
        )

    if not any(captions.values()):
        raise RuntimeError(
            f"Model '{model}' produced no usable captions for any style after "
            f"{max_retries} attempt(s) -- treating as a failure."
        )

    return captions
