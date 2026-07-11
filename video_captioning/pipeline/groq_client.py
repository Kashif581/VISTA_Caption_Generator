"""
groq_client.py

Groq's OpenAI-compatible endpoint, used as the captioning FALLBACK when
Fireworks is unavailable or errors out (see pipeline/captioner.py for the
fallback order: Fireworks -> Groq -> generic fallback text).

Two separate models, like the Fireworks vision/text pair:
- GROQ_VISION_MODEL handles describe_scene() -- must be vision-capable.
- GROQ_TEXT_MODEL handles combine_descriptions() and
  generate_styled_captions() -- text-only is fine, and deliberately NOT a
  reasoning model: reasoning models emit a literal <think> block ahead of
  their answer (see llm_client.strip_reasoning), which breaks strict
  JSON-mode validation on the captions step.

This is separate from pipeline/audio.py's use of Groq for transcription
(different API surface -- audio uses the `groq` SDK's audio.transcriptions
endpoint directly, this uses the OpenAI-compatible chat.completions
endpoint), though both read the same GROQ_API_KEY.
"""

from openai import OpenAI

import config
from pipeline import llm_client

_client = None


def get_client():
    global _client
    if _client is None:
        if not config.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set -- no fallback captioning backend available.")
        _client = OpenAI(
            api_key=config.GROQ_API_KEY,
            base_url=config.GROQ_BASE_URL,
            timeout=config.GROQ_CAPTION_TIMEOUT_SECONDS,
        )
    return _client


def describe_scene(hero_frame_bgr, sprite_bgr, timestamp_sec, transcript, background_sounds, scene_index, total_scenes):
    return llm_client.describe_scene(
        get_client(), config.GROQ_VISION_MODEL, config.GROQ_CAPTION_MAX_RETRIES,
        hero_frame_bgr, sprite_bgr, timestamp_sec, transcript, background_sounds, scene_index, total_scenes,
        max_tokens=config.GROQ_DESCRIBE_MAX_TOKENS,
    )


def combine_descriptions(scene_descriptions):
    return llm_client.combine_scene_descriptions(
        get_client(), config.GROQ_TEXT_MODEL, config.GROQ_CAPTION_MAX_RETRIES,
        scene_descriptions,
        max_tokens=config.GROQ_COMBINE_MAX_TOKENS,
    )


def generate_styled_captions(description, styles):
    return llm_client.generate_styled_captions(
        get_client(), config.GROQ_TEXT_MODEL, config.GROQ_CAPTION_MAX_RETRIES,
        description, styles,
        max_tokens=config.GROQ_CAPTIONS_MAX_TOKENS,
    )
