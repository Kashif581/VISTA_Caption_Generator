"""
gemini_client.py

Google Gemini API hosting Gemma 4, used as the PRIMARY captioning backend
when GEMINI_API_KEY is set (see pipeline/captioner.py for the fallback
order: Gemini -> Fireworks -> Groq -- Fireworks is the first fallback
specifically to absorb Gemini rate limiting, Groq is the final one).

Goes through Gemini's OpenAI-compatible endpoint rather than the native
google-genai SDK, so describe_scene() / combine_descriptions() /
generate_styled_captions() below call the exact same llm_client helpers as
fireworks_client.py and groq_client.py -- same retry-on-empty-content
handling, same output cleaning, same prompts. Only the api_key/base_url/
model differ per backend.

is_configured() is what lets captioner.py skip this backend entirely (not
attempt-then-fail-over) when no GEMINI_API_KEY is present -- Track 2
injects no key for this any more than it does for Fireworks/Groq.
"""

from openai import OpenAI

import config
from pipeline import llm_client

_client = None


def is_configured():
    return bool(config.GEMINI_API_KEY)


def get_client():
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set -- Gemini/Gemma backend unavailable.")
        _client = OpenAI(
            api_key=config.GEMINI_API_KEY,
            base_url=config.GEMINI_BASE_URL,
            timeout=config.GEMINI_TIMEOUT_SECONDS,
        )
    return _client


def describe_scene(hero_frame_bgr, sprite_bgr, timestamp_sec, transcript, background_sounds, scene_index, total_scenes):
    return llm_client.describe_scene(
        get_client(), config.GEMINI_VISION_MODEL, config.GEMINI_MAX_RETRIES,
        hero_frame_bgr, sprite_bgr, timestamp_sec, transcript, background_sounds, scene_index, total_scenes,
        max_tokens=config.GEMINI_DESCRIBE_MAX_TOKENS,
    )


def combine_descriptions(scene_descriptions):
    return llm_client.combine_scene_descriptions(
        get_client(), config.GEMINI_TEXT_MODEL, config.GEMINI_MAX_RETRIES,
        scene_descriptions,
        max_tokens=config.GEMINI_COMBINE_MAX_TOKENS,
    )


def generate_styled_captions(description, styles):
    return llm_client.generate_styled_captions(
        get_client(), config.GEMINI_TEXT_MODEL, config.GEMINI_MAX_RETRIES,
        description, styles,
        max_tokens=config.GEMINI_CAPTIONS_MAX_TOKENS,
    )
