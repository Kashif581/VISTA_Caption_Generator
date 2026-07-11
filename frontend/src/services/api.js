const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * Runs the full captioning pipeline for one clip and returns the full
 * breakdown (keyframes, audio status, description, per-style captions,
 * stage timings, backend used). Accepts either a remote video URL or a
 * File object -- exactly one should be provided.
 */
export async function processClip({ videoUrl, file, styles, signal }) {
  const form = new FormData();
  if (videoUrl) form.append("video_url", videoUrl);
  if (file) form.append("file", file);
  if (styles?.length) form.append("styles", JSON.stringify(styles));

  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/process`, {
      method: "POST",
      body: form,
      signal,
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError(
      `Could not reach the captioning API at ${API_BASE_URL}. Is the backend running?`,
      0
    );
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // response wasn't JSON -- fall back to statusText
    }
    throw new ApiError(detail, response.status);
  }

  return response.json();
}

export async function checkHealth(signal) {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, { signal });
    return response.ok;
  } catch {
    return false;
  }
}
