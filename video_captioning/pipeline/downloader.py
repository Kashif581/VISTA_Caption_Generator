"""
downloader.py

Fetches a task's video to local disk so OpenCV/ffmpeg can read it. Streams
with a byte cap and a hard deadline so one oversized or slow URL can't eat
the whole run's time budget. Also accepts plain local paths / file:// URLs
for local testing.
"""

import logging
import os
import time
import uuid
from urllib.parse import urlparse

import requests

import config

logger = logging.getLogger(__name__)


class DownloadError(Exception):
    pass


def fetch_video(video_url: str, deadline: float) -> str:
    """
    Returns a local filesystem path to the video.

    `deadline` is an absolute time.monotonic() value this download must not
    run past.
    """

    parsed = urlparse(video_url)

    if parsed.scheme in ("", "file"):
        local_path = parsed.path if parsed.scheme == "file" else video_url
        if not os.path.exists(local_path):
            raise DownloadError(f"Local video not found: {local_path}")
        return local_path

    suffix = os.path.splitext(parsed.path)[1] or ".mp4"
    dest_path = os.path.join(config.WORK_DIR, f"video_{uuid.uuid4().hex}{suffix}")

    remaining = max(1.0, deadline - time.monotonic())
    timeout = min(config.VIDEO_DOWNLOAD_TIMEOUT_SECONDS, remaining)

    downloaded = 0

    try:
        with requests.get(video_url, stream=True, timeout=timeout) as response:
            response.raise_for_status()

            with open(dest_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1 << 20):
                    if not chunk:
                        continue

                    downloaded += len(chunk)
                    if downloaded > config.MAX_VIDEO_BYTES:
                        raise DownloadError(
                            f"Video exceeds {config.MAX_VIDEO_BYTES}-byte cap: {video_url}"
                        )

                    if time.monotonic() > deadline:
                        raise DownloadError(f"Download deadline exceeded: {video_url}")

                    f.write(chunk)

    except requests.RequestException as exc:
        raise DownloadError(f"Failed to download {video_url}: {exc}") from exc

    if downloaded == 0:
        raise DownloadError(f"Downloaded empty file: {video_url}")

    return dest_path


def cleanup(path: str) -> None:
    """Remove a downloaded temp file. No-op for local/dev paths outside WORK_DIR."""

    if path and path.startswith(str(config.WORK_DIR)) and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            logger.warning("Failed to clean up %s", path)
