import os
import time
from typing import Optional

import requests

AGNES_BASE_URL = "https://apihub.agnes-ai.com"
AGNES_VIDEO_MODEL = "agnes-video-v2.0"
POLL_INTERVAL_SECONDS = 15
TOTAL_POLL_TIMEOUT_SECONDS = 360


def _headers() -> dict:
    api_key = os.getenv("AGNES_API_KEY", "").strip()
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _extract_video_id(data: dict) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    for value in (data.get("video_id"), data.get("id"), data.get("task_id")):
        if value:
            return str(value)
    nested = data.get("data")
    if isinstance(nested, dict):
        for value in (nested.get("video_id"), nested.get("id"), nested.get("task_id")):
            if value:
                return str(value)
    return None


def _extract_video_url(data: dict) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    metadata = data.get("metadata")
    if isinstance(metadata, dict) and metadata.get("url"):
        return str(metadata["url"])
    nested = data.get("data")
    if isinstance(nested, dict):
        meta = nested.get("metadata")
        if isinstance(meta, dict) and meta.get("url"):
            return str(meta["url"])
        for key in ("url", "video_url", "output_url"):
            if nested.get(key):
                return str(nested[key])
    for key in ("url", "video_url", "output_url"):
        if data.get(key):
            return str(data[key])
    return None


def create_agnes_video(prompt: str) -> Optional[bytes]:
    api_key = os.getenv("AGNES_API_KEY", "").strip()
    if not api_key:
        print("[video] AGNES_API_KEY is not set; skipping AI video")
        return None

    final_prompt = (
        (prompt or "").strip()
        + " No dialogue, no voice-over, no narration, no captions, no readable text, no generated logos, no watermark. "
          "Do not show forged visas, fake stamps, altered passports, or readable personal data."
    )
    payload = {
        "model": AGNES_VIDEO_MODEL,
        "prompt": final_prompt,
        "width": 1080,
        "height": 1920,
        "num_frames": 121,
        "frame_rate": 24,
        "negative_prompt": (
            "readable passport data, fake visa, forged document, fake stamp, altered document, readable personal data, "
            "distorted hands, extra fingers, captions, letters, watermark, generated logo, dialogue, voice-over, narration"
        ),
    }

    try:
        print("[video] creating Agnes task...")
        response = requests.post(
            f"{AGNES_BASE_URL}/v1/videos",
            headers=_headers(),
            json=payload,
            timeout=(15, 120),
        )
        response.raise_for_status()
        video_id = _extract_video_id(response.json())
        if not video_id:
            raise RuntimeError(f"Agnes response has no video id: {response.json()}")
        print(f"[video] Agnes task created: {video_id}")
    except Exception as exc:
        print(f"[video] Agnes task creation failed: {exc}")
        return None

    deadline = time.monotonic() + TOTAL_POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            result = requests.get(
                f"{AGNES_BASE_URL}/agnesapi",
                params={"video_id": video_id},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=(15, 75),
            )
            result.raise_for_status()
            data = result.json()
            status = str(data.get("status") or "").strip().lower()
            print(f"[video] Agnes status: {status or 'processing'}")

            if status in {"completed", "complete", "success", "succeeded", "done", "finished"}:
                video_url = _extract_video_url(data)
                if not video_url:
                    print(f"[video] completed task has no URL: {data}")
                    return None
                download = requests.get(video_url, timeout=(15, 180))
                download.raise_for_status()
                if not download.content:
                    print("[video] downloaded video is empty")
                    return None
                print(f"[video] Agnes video downloaded: {len(download.content)} bytes")
                return download.content

            if status in {"failed", "failure", "error", "cancelled", "canceled", "rejected"}:
                print(f"[video] Agnes task failed: {data}")
                return None

        except requests.exceptions.ReadTimeout:
            print("[video] status request timed out; retrying")
        except requests.exceptions.ConnectionError as exc:
            print(f"[video] temporary connection error: {exc}; retrying")
        except requests.exceptions.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else None
            print(f"[video] polling HTTP error: {code}")
            if code in {400, 401, 403, 404}:
                return None
        except Exception as exc:
            print(f"[video] polling error: {exc}; retrying")

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(POLL_INTERVAL_SECONDS, remaining))

    print(f"[video] polling timeout after {TOTAL_POLL_TIMEOUT_SECONDS} seconds")
    return None
