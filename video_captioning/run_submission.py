"""
run_submission.py

Docker CMD entrypoint. Implements the Track 2 I/O contract exactly:

    reads  /input/tasks.json    -> [{task_id, video_url, styles}, ...]
    writes /output/results.json -> [{task_id, captions: {style: caption}}, ...]

Exits 0 on success (even if individual tasks degraded to fallback captions --
a low-quality caption still scores better than a missing one), non-zero only
if the run could not produce a results file at all.
"""

import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import config
from pipeline.captioner import caption_task

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger("run_submission")


def load_tasks(path):
    with open(path, "r") as f:
        tasks = json.load(f)

    if not isinstance(tasks, list):
        raise ValueError("tasks.json must contain a JSON array")

    for task in tasks:
        if "task_id" not in task or "video_url" not in task:
            raise ValueError(f"Malformed task entry (needs task_id, video_url): {task}")

    return tasks


def write_results(path, results):
    out_dir = os.path.dirname(path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w") as f:
        json.dump(results, f, indent=2)

    os.replace(tmp_path, path)


def run():
    start = time.monotonic()
    deadline = start + config.MAX_TOTAL_RUNTIME_SECONDS

    try:
        tasks = load_tasks(config.INPUT_TASKS_PATH)
    except Exception as exc:
        logger.error("Failed to read tasks from %s: %s", config.INPUT_TASKS_PATH, exc)
        try:
            write_results(config.OUTPUT_RESULTS_PATH, [])
        except Exception:
            logger.exception("Also failed to write an empty results file")
        return 1

    logger.info("Loaded %d task(s) from %s", len(tasks), config.INPUT_TASKS_PATH)

    results = []
    max_workers = max(1, min(config.MAX_PARALLEL_TASKS, len(tasks) or 1))

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(caption_task, task, deadline): task for task in tasks}

        for future in as_completed(futures):
            task = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                logger.exception("Unhandled failure for task %s: %s", task.get("task_id"), exc)
                styles = task.get("styles") or config.STYLES
                result = {
                    "task_id": task.get("task_id", "unknown"),
                    "captions": {style: "A short video clip." for style in styles},
                }

            results.append(result)
            logger.info(
                "Completed %s (%d/%d) -- elapsed %.1fs",
                result["task_id"], len(results), len(tasks), time.monotonic() - start,
            )

    try:
        write_results(config.OUTPUT_RESULTS_PATH, results)
    except Exception as exc:
        logger.error("Failed to write results to %s: %s", config.OUTPUT_RESULTS_PATH, exc)
        return 1

    logger.info(
        "Wrote %d result(s) to %s in %.1fs",
        len(results), config.OUTPUT_RESULTS_PATH, time.monotonic() - start,
    )

    return 0


if __name__ == "__main__":
    sys.exit(run())
