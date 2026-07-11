"""
scene.py

Lightweight scene detection + per-scene image extraction. Pure OpenCV, no
model downloads.

Each detected scene window becomes TWO images sent together in one
describe_scene() call:
- "hero_frame": one clean, full-resolution frame near the scene's temporal
  midpoint -- for fine visual detail (hair color, clothing, small text or
  objects) that a small grid tile is too low-res to show.
- "sprite": a grid of that scene's frames sampled roughly once per second
  across its whole duration (capped at SPRITE_MAX_TILES tiles), arranged
  left-to-right/top-to-bottom in chronological order with a small timestamp
  burned into each tile -- for motion/progression context across the scene
  over time (a subject entering frame, walking closer, changing pose).
  None for a scene too short to tile meaningfully (under ~2s), where the
  hero frame alone already covers the whole scene.

This gives the vision model both a sharp reference image and temporal
coverage from a single API call per scene, rather than either (a) one
static frame that has neither, or (b) one API call per second of footage,
which would multiply cost/latency for anything longer than a couple of
seconds.
"""

import math

import cv2
import numpy as np

import config


def is_frame_black(frame, thresh=10):
    return np.mean(frame) < thresh


def _histogram_threshold(duration_sec):
    if duration_sec < 120:
        return 0.50
    if duration_sec < 1800:
        return 0.30
    return 0.45


def get_video_info(video_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    duration_sec = (total_frames / fps) if (fps and total_frames > 0) else 0.0
    sample_interval = max(1, int(fps / 2))  # ~2 fps sampling

    return {
        "fps": fps,
        "total_frames": total_frames,
        "duration_sec": duration_sec,
        "sample_interval": sample_interval,
        "hist_threshold": _histogram_threshold(duration_sec),
    }


def detect_scene_boundaries(video_path, info):
    """Frame indices where a scene change is detected, via HSV histogram
    Bhattacharyya distance between sampled frames."""

    cap = cv2.VideoCapture(video_path)

    boundaries = [0]
    prev_hist = None
    frame_idx = 0
    sample_interval = info["sample_interval"]
    hist_threshold = info["hist_threshold"]

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % sample_interval == 0 and not is_frame_black(frame):
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist(
                [hsv], [0, 1, 2], None, [8, 8, 8], [0, 180, 0, 256, 0, 256]
            )
            hist = cv2.normalize(hist, hist).flatten()

            if prev_hist is not None:
                distance = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA)
                if distance > hist_threshold:
                    boundaries.append(frame_idx)

            prev_hist = hist

        frame_idx += 1

    cap.release()

    # Metadata frame counts can be unreliable for some containers/codecs;
    # trust whatever we actually managed to read if it's larger.
    true_total = max(info["total_frames"], frame_idx)
    boundaries.append(true_total)

    return sorted(set(boundaries))


def _select_scene_windows(boundaries, max_windows):
    """Collapse scene boundaries down to at most `max_windows` (start, end)
    windows, evenly spanning the timeline, so per-scene extraction cost is
    bounded regardless of how choppy the source video is."""

    windows = [w for w in zip(boundaries[:-1], boundaries[1:]) if w[1] > w[0]]

    if len(windows) <= max_windows:
        return windows

    step = len(windows) / max_windows
    return [windows[int(i * step)] for i in range(max_windows)]


def _resize_and_pad(frame, size):
    """Resize preserving aspect ratio to fit within size x size, then
    letterbox-pad with black so every grid tile is the same shape
    regardless of the source video's aspect ratio."""

    height, width = frame.shape[:2]
    scale = size / max(height, width)
    new_w, new_h = max(1, int(width * scale)), max(1, int(height * scale))
    resized = cv2.resize(frame, (new_w, new_h))

    canvas = np.zeros((size, size, 3), dtype=np.uint8)
    y_off = (size - new_h) // 2
    x_off = (size - new_w) // 2
    canvas[y_off:y_off + new_h, x_off:x_off + new_w] = resized
    return canvas


def _label_tile(tile, timestamp_sec):
    """Burns a small mm:ss label into the bottom-left corner of a tile so
    the model can reference approximately when in the scene each tile is
    from -- a dark backing box keeps the label legible over any footage."""

    label = f"{int(timestamp_sec // 60):02d}:{int(timestamp_sec % 60):02d}"
    size = tile.shape[0]
    font_scale = max(0.35, size / 480)
    thickness = 1
    (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
    pad = 3

    cv2.rectangle(tile, (0, size - text_h - 2 * pad), (text_w + 2 * pad, size), (0, 0, 0), -1)
    cv2.putText(
        tile, label, (pad, size - pad - 1),
        cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness, cv2.LINE_AA,
    )
    return tile


def _build_sprite_sheet(tiles):
    """tiles: list of same-size square BGR images, chronological. Arranges
    them left-to-right then top-to-bottom, capped at SPRITE_MAX_COLS
    columns, padding the last row with black tiles if it's not full."""

    cols = min(config.SPRITE_MAX_COLS, len(tiles))
    rows = math.ceil(len(tiles) / cols)
    size = tiles[0].shape[0]

    blank = np.zeros((size, size, 3), dtype=np.uint8)
    padded = tiles + [blank] * (rows * cols - len(tiles))

    row_images = [np.hstack(padded[r * cols:(r + 1) * cols]) for r in range(rows)]
    return np.vstack(row_images)


def _scene_images(cap, start_frame, end_frame, fps):
    """Builds the (sprite, hero_frame, representative_timestamp_sec) triple
    for one scene window [start_frame, end_frame) -- see module docstring.
    sprite is None when the scene has only one usable frame (too short to
    tile, or all other sampled frames were black/unreadable). Returns
    (None, None, None) if no readable, non-black frame was found at all.
    """

    duration_sec = (end_frame - start_frame) / fps
    tile_count = max(1, min(config.SPRITE_MAX_TILES, round(duration_sec) or 1))
    step = max(1, (end_frame - start_frame) // tile_count)

    candidate_indices = [start_frame + i * step for i in range(tile_count)]
    candidate_indices = [i for i in candidate_indices if i < end_frame] or [start_frame]

    raw_frames = []
    timestamps = []
    for idx in candidate_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret or is_frame_black(frame):
            continue
        raw_frames.append(frame)
        timestamps.append(idx / fps)

    if not raw_frames:
        return None, None, None

    mid_i = len(raw_frames) // 2
    hero_frame = raw_frames[mid_i]
    mid_ts = timestamps[mid_i]

    if len(raw_frames) == 1:
        return None, hero_frame, mid_ts

    tiles = [
        _label_tile(_resize_and_pad(frame, config.SPRITE_TILE_SIZE), ts)
        for frame, ts in zip(raw_frames, timestamps)
    ]
    return _build_sprite_sheet(tiles), hero_frame, mid_ts


def extract_keyframes(video_path, info, max_keyframes=None):
    """
    Returns a list of scene dicts, chronologically ordered, one per
    detected scene window (capped at max_keyframes):
        {"sprite": image_bgr | None, "hero_frame": image_bgr, "timestamp_sec": float}
    See the module docstring for what each image is for. Both are sent
    together in one describe_scene() call per scene.
    """

    max_keyframes = max_keyframes or config.MAX_KEYFRAMES

    boundaries = detect_scene_boundaries(video_path, info)
    windows = _select_scene_windows(boundaries, max_keyframes)

    cap = cv2.VideoCapture(video_path)
    fps = info["fps"] or 25.0

    scenes = []
    for start, end in windows:
        sprite, hero_frame, ts = _scene_images(cap, start, end, fps)
        if hero_frame is not None:
            scenes.append({"sprite": sprite, "hero_frame": hero_frame, "timestamp_sec": ts})

    cap.release()

    if not scenes:
        # Degenerate case (e.g. a near-all-black clip): grab the first
        # readable frame so captioning still has something to work with.
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        cap.release()
        if ret:
            scenes.append({"sprite": None, "hero_frame": frame, "timestamp_sec": 0.0})

    return scenes
