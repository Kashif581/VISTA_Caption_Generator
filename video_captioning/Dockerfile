FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/model_cache/huggingface \
    TORCH_HOME=/opt/model_cache/torch \
    XDG_CACHE_HOME=/opt/model_cache

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Prefetch local model weights before copying the rest of the app: this
# layer only depends on config.py + download_models.py, so ordinary
# pipeline/app code changes below don't force a multi-minute model
# re-download on every rebuild. Bake them in at build time (not runtime) so
# the container never hits the network for weights -- keeps the 60s startup
# and 10-minute total runtime budgets free for actual video processing.
COPY config.py download_models.py .
RUN python download_models.py

COPY . .

RUN mkdir -p /input /output /tmp/video_captioning

CMD ["python", "run_submission.py"]
