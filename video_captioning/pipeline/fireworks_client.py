"""
fireworks_client.py

Fireworks AI OpenAI-compatible Chat Completions API -- the primary
captioning backend. Track 2 injects no API key/base-url/model allowlist --
these all come from your own Fireworks account (see config.py / .env).

If this backend is unavailable or errors out, pipeline/captioner.py falls
back to pipeline/groq_client.py automatically -- see that module.
"""

from openai import OpenAI

import config
from pipeline import llm_client

_client = None


def get_client():
    global _client
    if _client is None:
        if not config.FIREWORKS_API_KEY:
            raise RuntimeError(
                "FIREWORKS_API_KEY is not set. Add it to .env (see .env.example). "
                "Track 2 does not inject a key automatically -- this is your own "
                "Fireworks account credential."
            )
        _client = OpenAI(
            api_key=config.FIREWORKS_API_KEY,
            base_url=config.FIREWORKS_BASE_URL,
            timeout=config.FIREWORKS_TIMEOUT_SECONDS,
        )
    return _client


def describe_scene(hero_frame_bgr, sprite_bgr, timestamp_sec, transcript, background_sounds, scene_index, total_scenes):
    return llm_client.describe_scene(
        get_client(), config.FIREWORKS_VISION_MODEL, config.FIREWORKS_MAX_RETRIES,
        hero_frame_bgr, sprite_bgr, timestamp_sec, transcript, background_sounds, scene_index, total_scenes,
        max_tokens=config.FIREWORKS_DESCRIBE_MAX_TOKENS,
    )


def combine_descriptions(scene_descriptions):
    return llm_client.combine_scene_descriptions(
        get_client(), config.FIREWORKS_TEXT_MODEL, config.FIREWORKS_MAX_RETRIES,
        scene_descriptions,
        max_tokens=config.FIREWORKS_COMBINE_MAX_TOKENS,
    )


def generate_styled_captions(description, styles):
    return llm_client.generate_styled_captions(
        get_client(), config.FIREWORKS_TEXT_MODEL, config.FIREWORKS_MAX_RETRIES,
        description, styles,
        max_tokens=config.FIREWORKS_CAPTIONS_MAX_TOKENS,
    )
