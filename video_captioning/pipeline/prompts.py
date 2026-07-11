"""
prompts.py

Prompt templates and response parsing for the three-call captioning flow:

1. describe_scene()            -> one factual description per keyframe/scene
2. combine_scene_descriptions() -> N per-scene descriptions -> one video
                                    description (skipped when there's only
                                    one scene -- nothing to combine)
3. generate_styled_captions()  -> that description rewritten into N styles

Each scene gets its own vision call instead of every keyframe competing for
attention in one crowded multi-image prompt, which matters more as videos
get longer and have more distinct scenes. Splitting description from
styling also means the (cheaper, text-only) styling call can be
retried/re-run independently without re-sending images.
"""

import json
import re

STYLE_PERSONAS = {
    "formal": (
        "Professional documentary narrator. Objective, factual, precise register -- "
        "the kind of caption that would run under a news broadcast or museum "
        "placard. Third person, no contractions, no opinions, no exaggeration, "
        "no jokes, no rhetorical questions. Every word should earn its place; "
        "avoid filler adjectives that don't add information."
    ),
    "sarcastic": (
        "Dry, deadpan wit -- think a jaded critic or a bored commentator "
        "narrating something painfully mundane as if it were dramatic, or "
        "vice versa. The humor comes from ironic understatement or mock "
        "seriousness, never from insults, meanness, or shock value. If it "
        "would make someone groan-smile and say 'okay, fair,' that's the tone."
    ),
    "humorous_tech": (
        "A programmer who can't resist a tech metaphor. Genuinely funny, not "
        "just 'technically has a tech word in it' -- reach for a specific, apt "
        "software/AI/gaming/hardware comparison (bugs, loops, latency, patch "
        "notes, NPCs, buffering, etc.) that a non-engineer would still find "
        "amusing because the comparison itself is clever, not just jargon-dropping."
    ),
    "humorous_non_tech": (
        "A light-hearted comedian doing observational, everyday humor -- the "
        "kind of joke you'd make to a friend watching the same clip. Playful, "
        "warm, silly is fine. Zero technical or industry vocabulary of any kind."
    ),
}


def build_scene_description_prompt(
    transcript, background_sounds, scene_index, total_scenes, timestamp_sec, has_sprite
):
    context_lines = []

    if transcript:
        context_lines.append(f'Spoken audio transcript for the full video: "{transcript.strip()}"')

    if background_sounds:
        context_lines.append(f"Background sounds detected in the full video: {', '.join(background_sounds)}")

    context_block = "\n".join(context_lines) if context_lines else "No audio context available."

    if total_scenes > 1:
        scene_ref = f"scene {scene_index} of {total_scenes} from a video, centered around approximately {timestamp_sec:.0f} seconds in"
    else:
        scene_ref = "the only scene in a short video clip"

    if has_sprite:
        image_note = (
            f"You are shown two images for {scene_ref}. The first is one clear, full-resolution "
            "frame from the middle of this scene -- use it for fine visual detail (hair color, "
            "clothing, small text or objects, textures). The second is a grid of this same scene's "
            "frames sampled roughly once per second across its whole duration, arranged left-to-right "
            "then top-to-bottom in chronological order, each tile with a small mm:ss timestamp label "
            "in its bottom-left corner -- use it to see what happens across the scene over time (any "
            "motion, change, or progression from the earliest tile to the latest), not just the single "
            "instant in the first image. Combine both into one description of the whole scene."
        )
    else:
        image_note = f"You are shown one clear frame from {scene_ref}. Describe that moment."

    return f"""{image_note}

{context_block}

Write a detailed, factual, neutral description of what this scene shows. Be specific and concrete, not generic -- name exactly what's visible rather than describing it abstractly, as if you were briefing someone who cannot see the image at all. Cover, in detail, whatever is actually visible:
- Main subject(s): who or what, how many, and specific distinguishing features -- for people: approximate age range, hair color and style, clothing color/type/style, visible accessories, facial expression, posture or gesture; for animals: species/breed, coat color and pattern, size; for objects/vehicles/products: type, color, material, condition, any legible text or branding
- Setting: indoor/outdoor, the specific type of location, time of day and lighting quality, notable background elements and objects (even ones the subject isn't interacting with)
- Action: what is actively happening, any visible motion, gesture, or pose, and how it changes across the scene if multiple tiles are shown
- Notable objects, text, signage, or events that stand out but aren't the main subject
- Overall mood or atmosphere conveyed by lighting, color palette, or composition

The audio context is for the whole video, not just this scene -- only mention it if it plausibly applies to what's visible here, and do not mention that an image, transcript, or background sounds were provided, and do not describe the grid/tile layout itself or read out the timestamp labels. Do not speculate beyond what's actually shown. 4-6 sentences, plain natural prose only -- no markdown formatting, no headers, no bullet points, no asterisks or underscores for emphasis, no emojis, no special symbols. Just clean, readable sentences a person would read comfortably.

Respond with ONLY the description itself -- no reasoning, no draft notes, no commentary about the task before or after it."""


def build_combine_prompt(scene_descriptions):
    scene_blocks = "\n\n".join(
        f"Scene {i + 1} (at ~{sd['timestamp_sec']:.0f}s): {sd['description']}"
        for i, sd in enumerate(scene_descriptions)
    )

    return f"""Below are factual descriptions of {len(scene_descriptions)} sequential scenes sampled from one continuous video, in chronological order:

{scene_blocks}

Synthesize these into ONE coherent, flowing description of the entire video -- capture what happens across the video as a whole, including how it changes or progresses from scene to scene where that's relevant. Do not just list the scenes back-to-back; write it as a single unified description a viewer would recognize as describing one video, not several. Keep concrete, specific details (colors, subjects, actions, settings) from the individual scene descriptions rather than generalizing them away. 6-9 sentences, plain natural prose only -- no markdown formatting, no headers, no bullet points, no asterisks or underscores for emphasis, no emojis, no special symbols.

Respond with ONLY the final description itself. Do not show your reasoning, do not draft or revise out loud, do not restate these instructions or count sentences, do not add any commentary about the task before or after the description -- the very first word of your response must be the first word of the description."""


def build_caption_prompt(description, styles):
    persona_block = "\n\n".join(f'"{style}": {STYLE_PERSONAS[style]}' for style in styles)
    keys = ", ".join(f'"{s}"' for s in styles)

    return f"""Video description (ground every caption in these specific details -- name the actual subjects/objects/actions, don't generalize to "a video" or "some content"):
{description}

Write one caption per style below. All {len(styles)} captions describe the exact same video, but each must sound like it was written by a genuinely different person with a distinct voice -- a reader should be able to tell them apart even with the labels removed.

{persona_block}

Requirements:
- 15-40 words per caption -- detailed enough to include at least one real, specific visual detail from the description (a color, an object, clothing, setting, or action), never a vague one-liner, but still a single punchy caption, not a paragraph.
- Every caption must be factually grounded in the video description above -- same subject, setting, and action, just told in a different voice with different specific details emphasized. Do not invent details that contradict or aren't supported by the description.
- Make the styles genuinely distinct from each other in voice and word choice, not minor rewordings of the same sentence, while each still strictly matching its assigned persona above.
- Plain text only -- no markdown, no asterisks or underscores for emphasis, no hashtags, no emojis, no special symbols, no quotation marks wrapping the caption.
- Return ONLY a JSON object with exactly these keys: {keys}
- No markdown, no code fences, no extra keys, no commentary outside the JSON."""


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_caption_json(raw, styles):
    text = (raw or "").strip()

    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]

    data = {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_BLOCK_RE.search(text)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                data = {}

    if not isinstance(data, dict):
        data = {}

    captions = {}
    for style in styles:
        value = data.get(style, "")
        captions[style] = value.strip() if isinstance(value, str) else str(value or "").strip()

    return captions
