import os
import time
from typing import Optional

import requests


AGNES_BASE_URL = "https://apihub.agnes-ai.com"
AGNES_VIDEO_MODEL = "agnes-video-v2.0"

POLL_INTERVAL_SECONDS = 15
TOTAL_POLL_TIMEOUT_SECONDS = 420


def _headers() -> dict:
    api_key = os.getenv("AGNES_API_KEY", "").strip()

    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _extract_video_id(data: dict) -> Optional[str]:
    """
    Agnes creation response can contain several identifiers.

    IMPORTANT:
    For polling /agnesapi we need VIDEO_ID,
    not task_id.
    """

    if not isinstance(data, dict):
        return None

    # Primary value for Agnes polling
    if data.get("video_id"):
        return str(data["video_id"])

    # Some API responses may expose video ID as "id"
    if data.get("id"):
        return str(data["id"])

    nested = data.get("data")

    if isinstance(nested, dict):
        if nested.get("video_id"):
            return str(nested["video_id"])

        if nested.get("id"):
            return str(nested["id"])

    return None


def _extract_video_url(data: dict) -> Optional[str]:
    """
    Extract final generated MP4 URL
    from Agnes polling response.
    """

    if not isinstance(data, dict):
        return None

    metadata = data.get("metadata")

    if isinstance(metadata, dict):
        if metadata.get("url"):
            return str(metadata["url"])

        if metadata.get("video_url"):
            return str(metadata["video_url"])

        if metadata.get("output_url"):
            return str(metadata["output_url"])

    nested = data.get("data")

    if isinstance(nested, dict):

        nested_metadata = nested.get("metadata")

        if isinstance(nested_metadata, dict):

            if nested_metadata.get("url"):
                return str(nested_metadata["url"])

            if nested_metadata.get("video_url"):
                return str(nested_metadata["video_url"])

            if nested_metadata.get("output_url"):
                return str(nested_metadata["output_url"])

        for key in (
            "url",
            "video_url",
            "output_url",
        ):
            if nested.get(key):
                return str(nested[key])

    for key in (
        "url",
        "video_url",
        "output_url",
    ):
        if data.get(key):
            return str(data[key])

    return None


def create_agnes_video(prompt: str) -> Optional[bytes]:
    """
    Create vertical travel video using Agnes Video 2.0.

    Returns:
        bytes of MP4 video

    or:
        None if generation fails
    """

    api_key = os.getenv("AGNES_API_KEY", "").strip()

    if not api_key:
        print("[video] AGNES_API_KEY is not set; skipping video generation")
        return None

    clean_prompt = (prompt or "").strip()

    if not clean_prompt:
        print("[video] empty video prompt")
        return None

    # Add strict visual rules to reduce broken anatomy,
    # text artifacts and low-quality AI-video scenes.
    final_prompt = (
        clean_prompt
        + "\n\n"
        + (
            "Premium cinematic international travel advertisement. "
            "Natural realistic motion. "
            "High-end commercial travel cinematography. "
            "Strong visual depth and clean composition. "
            "Use architecture, airports, railway stations, streets, landmarks, "
            "luggage and destination atmosphere as primary subjects. "
            "People should preferably be shown from behind, in silhouette, "
            "or at medium-to-long distance. "
            "Avoid close-up faces. "
            "Avoid close-up hands. "
            "Avoid malformed anatomy. "
            "Avoid duplicate people or objects. "
            "No dialogue. "
            "No voice-over. "
            "No captions. "
            "No readable text inside the generated scene. "
            "No logos. "
            "No watermark. "
            "Smooth cinematic camera movement. "
            "Professional realistic lighting."
        )
    )

    # IMPORTANT:
    # Agnes requires:
    # num_frames = 8 * n + 1
    #
    # Valid examples:
    # 49, 57, 65...
    #
    # 57 is used here.
    payload = {
        "model": AGNES_VIDEO_MODEL,
        "prompt": final_prompt,
        "width": 1080,
        "height": 1920,
        "num_frames": 57,
    }

    try:

        print("[video] creating Agnes video task...")
        print(
            f"[video] model={AGNES_VIDEO_MODEL} "
            f"size=1080x1920 "
            f"frames={payload['num_frames']}"
        )

        response = requests.post(
            f"{AGNES_BASE_URL}/v1/videos",
            headers=_headers(),
            json=payload,
            timeout=(15, 120),
        )

        if response.status_code >= 400:
            print(
                f"[video] task creation HTTP "
                f"{response.status_code}: "
                f"{response.text[:2000]}"
            )
            return None

        try:
            data = response.json()

        except Exception:
            print(
                "[video] Agnes creation response is not JSON: "
                f"{response.text[:2000]}"
            )
            return None

        if isinstance(data, dict):
            print(
                "[video] creation response keys:",
                list(data.keys()),
            )

            # Useful diagnostics only
            if data.get("task_id"):
                print(
                    f"[video] task_id returned by Agnes: "
                    f"{data.get('task_id')}"
                )

            if data.get("video_id"):
                print(
                    f"[video] video_id returned by Agnes: "
                    f"{data.get('video_id')}"
                )

        video_id = _extract_video_id(data)

        if not video_id:
            print(
                "[video] response contains no usable video_id/id: "
                f"{str(data)[:2000]}"
            )
            return None

        print(f"[video] polling video_id: {video_id}")

    except requests.exceptions.Timeout:
        print("[video] timeout while creating Agnes video task")
        return None

    except requests.exceptions.ConnectionError as exc:
        print(
            f"[video] connection error while creating Agnes video: "
            f"{exc}"
        )
        return None

    except Exception as exc:
        print(f"[video] task creation failed: {exc}")
        return None

    # ---------------------------------------------------------
    # POLLING
    # ---------------------------------------------------------

    deadline = (
        time.monotonic()
        + TOTAL_POLL_TIMEOUT_SECONDS
    )

    poll_number = 0

    while time.monotonic() < deadline:

        poll_number += 1

        try:

            result = requests.get(
                f"{AGNES_BASE_URL}/agnesapi",
                params={
                    "video_id": video_id,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                },
                timeout=(15, 75),
            )

            print(
                f"[video] poll #{poll_number}: "
                f"HTTP {result.status_code}"
            )

            if result.status_code >= 400:

                print(
                    f"[video] polling HTTP "
                    f"{result.status_code}: "
                    f"{result.text[:1800]}"
                )

                # Permanent errors
                if result.status_code in {
                    400,
                    401,
                    403,
                    404,
                }:
                    return None

            else:

                try:
                    poll_data = result.json()

                except Exception:
                    print(
                        "[video] polling response is not JSON: "
                        f"{result.text[:1800]}"
                    )

                    time.sleep(
                        POLL_INTERVAL_SECONDS
                    )

                    continue

                status = str(
                    poll_data.get("status")
                    or ""
                ).strip().lower()

                progress = poll_data.get("progress")

                if progress is not None:
                    print(
                        f"[video] status="
                        f"{status or 'processing'} "
                        f"progress={progress}"
                    )
                else:
                    print(
                        f"[video] status="
                        f"{status or 'processing'}"
                    )

                # ---------------------------------------------
                # COMPLETED
                # ---------------------------------------------

                if status in {
                    "completed",
                    "complete",
                    "success",
                    "succeeded",
                    "done",
                    "finished",
                }:

                    video_url = _extract_video_url(
                        poll_data
                    )

                    if not video_url:
                        print(
                            "[video] completed but "
                            "video URL is missing:"
                        )

                        print(
                            str(poll_data)[:2000]
                        )

                        return None

                    print(
                        "[video] generated video URL received"
                    )

                    try:

                        download = requests.get(
                            video_url,
                            timeout=(15, 180),
                        )

                        download.raise_for_status()

                    except Exception as exc:

                        print(
                            "[video] video download failed: "
                            f"{exc}"
                        )

                        return None

                    video_bytes = download.content

                    if len(video_bytes) < 20_000:

                        print(
                            "[video] downloaded file is "
                            "suspiciously small: "
                            f"{len(video_bytes)} bytes"
                        )

                        return None

                    print(
                        "[video] video successfully downloaded: "
                        f"{len(video_bytes)} bytes"
                    )

                    return video_bytes

                # ---------------------------------------------
                # FAILED
                # ---------------------------------------------

                if status in {
                    "failed",
                    "failure",
                    "error",
                    "cancelled",
                    "canceled",
                    "rejected",
                }:

                    print(
                        "[video] Agnes video generation failed:"
                    )

                    print(
                        str(poll_data)[:2000]
                    )

                    return None

        except requests.exceptions.ReadTimeout:

            print(
                "[video] polling read timeout; retrying"
            )

        except requests.exceptions.ConnectionError as exc:

            print(
                "[video] temporary polling "
                f"connection error: {exc}"
            )

        except Exception as exc:

            print(
                f"[video] polling error: {exc}"
            )

        remaining = (
            deadline
            - time.monotonic()
        )

        if remaining <= 0:
            break

        time.sleep(
            min(
                POLL_INTERVAL_SECONDS,
                remaining,
            )
        )

    print(
        "[video] polling timeout after "
        f"{TOTAL_POLL_TIMEOUT_SECONDS} seconds"
    )

    return None
