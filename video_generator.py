import os
import time
from typing import Optional

import requests

AGNES_BASE_URL = "https://apihub.agnes-ai.com"
AGNES_VIDEO_MODEL = "agnes-video-v2.0"
POLL_INTERVAL_SECONDS = 15
TOTAL_POLL_TIMEOUT_SECONDS = 420


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('AGNES_API_KEY', '').strip()}",
        "Content-Type": "application/json",
    }


def _extract_video_id(data: dict) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    for key in ("id", "video_id", "task_id"):
        if data.get(key):
            return str(data[key])
    nested = data.get("data")
    if isinstance(nested, dict):
        for key in ("id", "video_id", "task_id"):
            if nested.get(key):
                return str(nested[key])
    return None


def _extract_video_url(data: dict) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    meta = data.get("metadata")
    if isinstance(meta, dict) and meta.get("url"):
        return str(meta["url"])
    nested = data.get("data")
    if isinstance(nested, dict):
        nmeta = nested.get("metadata")
        if isinstance(nmeta, dict) and nmeta.get("url"):
            return str(nmeta["url"])
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
        print("[video] AGNES_API_KEY is not set; skipping")
        return None

    final_prompt = (
        (prompt or "").strip()
        + " No dialogue, no voice-over, no captions, no readable text, no logos, no watermark. "
          "Avoid close-up faces and hands. Prefer architecture, destination atmosphere, luggage, departure boards with unreadable details, "
          "wide or medium travel shots and people shown from behind or at a distance. Natural motion, stable anatomy, premium commercial look."
    )

    # IMPORTANT: this is deliberately the minimal payload already proven in the user's working Agnes setup.
    payload = {
        "model": AGNES_VIDEO_MODEL,
        "prompt": final_prompt,
        "width": 1080,
        "height": 1920,
        "num_frames": 60,
    }

    try:
        print("[video] creating Agnes video task with proven 60-frame payload...")
        response = requests.post(
            f"{AGNES_BASE_URL}/v1/videos",
            headers=_headers(),
            json=payload,
            timeout=(15, 120),
        )
        if response.status_code >= 400:
            print(f"[video] task creation HTTP {response.status_code}: {response.text[:1800]}")
            return None
        data = response.json()
        print(f"[video] creation response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
        video_id = _extract_video_id(data)
        if not video_id:
            print(f"[video] no video id in creation response: {str(data)[:1800]}")
            return None
        print(f"[video] task created: {video_id}")
    except Exception as exc:
        print(f"[video] task creation failed: {exc}")
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
            if result.status_code >= 400:
                print(f"[video] polling HTTP {result.status_code}: {result.text[:1200]}")
                if result.status_code in {400, 401, 403, 404}:
                    return None
            else:
                data = result.json()
                status = str(data.get("status") or "").strip().lower()
                print(f"[video] status: {status or 'processing'}")

                if status in {"completed", "complete", "success", "succeeded", "done", "finished"}:
                    video_url = _extract_video_url(data)
                    if not video_url:
                        print(f"[video] completed but URL missing: {str(data)[:1800]}")
                        return None
                    download = requests.get(video_url, timeout=(15, 180))
                    download.raise_for_status()
                    if len(download.content) < 20_000:
                        print(f"[video] downloaded file suspiciously small: {len(download.content)} bytes")
                        return None
                    print(f"[video] video downloaded: {len(download.content)} bytes")
                    return download.content

                if status in {"failed", "failure", "error", "cancelled", "canceled", "rejected"}:
                    print(f"[video] task failed: {str(data)[:1800]}")
                    return None
        except requests.exceptions.ReadTimeout:
            print("[video] polling read timeout; retrying")
        except requests.exceptions.ConnectionError as exc:
            print(f"[video] temporary connection error: {exc}; retrying")
        except Exception as exc:
            print(f"[video] polling error: {exc}; retrying")

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(POLL_INTERVAL_SECONDS, remaining))

    print(f"[video] polling timeout after {TOTAL_POLL_TIMEOUT_SECONDS}s")
    return None
