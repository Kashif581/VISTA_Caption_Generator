"""
app.py

FastAPI wrapper around the captioning pipeline for interactive
testing/demoing, and the API the frontend/ demo talks to. NOT used by the
hackathon grader -- the graded entrypoint is run_submission.py, which
implements the batch /input -> /output contract required by the Track 2
spec. Run this locally with:

    uvicorn app:app --reload --port 8000

Then either:

    curl -X POST localhost:8000/caption \\
      -H 'content-type: application/json' \\
      -d '{"video_url": "https://.../clip.mp4"}'

or point the frontend/ dev server at this host (see frontend/.env.example)
and use the UI, which calls POST /api/process.
"""

import json
import logging
import os
import time
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

import config
from pipeline.captioner import caption_task, process_task_full
from schemas import CaptionRequest, CaptionResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("app")

app = FastAPI(title="Video Captioning Agent", version="1.0")

# Demo only: the frontend dev server runs on a different origin (e.g.
# localhost:5173) than this API (localhost:8000). Track 2's grading harness
# never goes through this app at all -- it runs run_submission.py directly
# inside the container -- so a wide-open CORS policy here has no bearing on
# submission security.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/caption", response_model=CaptionResponse)
def caption(request: CaptionRequest):
    task = {
        "task_id": uuid.uuid4().hex,
        "video_url": request.video_url,
        "styles": request.styles or list(config.STYLES),
    }

    deadline = time.monotonic() + config.MAX_TOTAL_RUNTIME_SECONDS

    result = caption_task(task, deadline)

    if not any(result["captions"].values()):
        raise HTTPException(status_code=502, detail="Captioning failed for all styles")

    return result


@app.post("/api/process")
async def process(
    video_url: str = Form(None),
    styles: str = Form(None),
    file: UploadFile = File(None),
):
    """Runs the full pipeline for one clip and returns every intermediate
    artifact (keyframe thumbnails, audio status, description, per-style
    captions, per-stage timings, which backend answered) for the demo
    frontend to render. Accepts either a video_url or an uploaded file."""

    if not video_url and file is None:
        raise HTTPException(status_code=400, detail="Provide either video_url or file")

    requested_styles = None
    if styles:
        try:
            parsed = json.loads(styles)
            if isinstance(parsed, list):
                requested_styles = parsed
        except json.JSONDecodeError:
            pass

    task = {
        "task_id": uuid.uuid4().hex,
        "video_url": video_url or "",
        "styles": requested_styles or list(config.STYLES),
    }

    deadline = time.monotonic() + config.MAX_TOTAL_RUNTIME_SECONDS

    local_path = None
    if file is not None:
        suffix = os.path.splitext(file.filename or "")[1] or ".mp4"
        local_path = os.path.join(str(config.WORK_DIR), f"upload_{uuid.uuid4().hex}{suffix}")
        with open(local_path, "wb") as f:
            f.write(await file.read())

    try:
        return process_task_full(task, deadline, local_path=local_path)
    except Exception as exc:
        logger.exception("process_task_full failed for %s: %s", task["task_id"], exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
