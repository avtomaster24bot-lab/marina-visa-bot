import base64
import io
import os
import random
from typing import Optional
from urllib.parse import quote

import requests
from PIL import Image

AGNES_BASE_URL = "https://apihub.agnes-ai.com"
AGNES_IMAGE_MODEL = "agnes-image-2.1-flash"
POLLINATIONS_URL = "https://gen.pollinations.ai/image/{}"


def _agnes_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('AGNES_API_KEY', '').strip()}",
        "Content-Type": "application/json",
    }


def _validate_image(raw: bytes, min_w: int = 900, min_h: int = 900) -> bool:
    if not raw or len(raw) < 25_000:
        return False
    try:
        img = Image.open(io.BytesIO(raw))
        w, h = img.size
        img.verify()
        print(f"[image] candidate dimensions: {w}x{h}; bytes={len(raw)}")
        return w >= min_w and h >= min_h
    except Exception as exc:
        print(f"[image] invalid image bytes: {exc}")
        return False


def _quality_suffix() -> str:
    return (
        " Premium international travel advertising, high-end editorial photography, crisp fine detail, sharp focus, "
        "realistic architecture and objects, clean natural geometry, cinematic daylight, elegant color grading, "
        "professional commercial composition. Avoid prominent faces, avoid close-up hands, avoid full-body fashion portraits, "
        "avoid distorted anatomy, extra limbs, asymmetrical eyes, duplicate objects, malformed luggage, warped buildings, "
        "blur, haze, low-resolution softness, fake text, readable passport data, logos and watermarks."
    )


def create_agnes_image(prompt: str) -> Optional[bytes]:
    api_key = os.getenv("AGNES_API_KEY", "").strip()
    if not api_key:
        print("[image] AGNES_API_KEY missing; skipping Agnes image")
        return None

    final_prompt = (prompt or "").strip() + _quality_suffix()
    payload = {
        "model": AGNES_IMAGE_MODEL,
        "prompt": final_prompt,
        "size": "1024x1024",
        "extra_body": {"response_format": "url"},
    }

    try:
        print("[image] creating with Agnes Image 2.1 Flash...")
        response = requests.post(
            f"{AGNES_BASE_URL}/v1/images/generations",
            headers=_agnes_headers(),
            json=payload,
            timeout=(15, 180),
        )
        response.raise_for_status()
        data = response.json()
        item = (data.get("data") or [{}])[0]

        raw = None
        image_url = item.get("url")
        if image_url:
            download = requests.get(image_url, timeout=(15, 150))
            download.raise_for_status()
            raw = download.content
        elif item.get("b64_json"):
            raw = base64.b64decode(item["b64_json"])

        if not _validate_image(raw or b""):
            print("[image] Agnes candidate rejected by technical quality gate")
            return None
        print("[image] Agnes image accepted")
        return raw
    except requests.exceptions.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else "unknown"
        body = exc.response.text[:1200] if exc.response is not None else ""
        print(f"[image] Agnes HTTP error: {code}; {body}")
        return None
    except Exception as exc:
        print(f"[image] Agnes generation failed: {exc}")
        return None


def create_pollinations_image(prompt: str) -> Optional[bytes]:
    final_prompt = (prompt or "").strip() + _quality_suffix()
    seed = random.randint(1, 2_000_000_000)
    url = POLLINATIONS_URL.format(quote(final_prompt, safe=""))
    params = {
        "model": "flux",
        "width": 1080,
        "height": 1350,
        "seed": seed,
        "nologo": "true",
        "enhance": "true",
    }
    api_key = os.getenv("POLLINATIONS_API_KEY", "").strip()
    headers = {"Accept": "image/*"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        print(f"[image] trying Pollinations Flux 1080x1350, seed={seed}...")
        response = requests.get(url, params=params, headers=headers, timeout=(15, 180))
        response.raise_for_status()
        ct = (response.headers.get("Content-Type") or "").lower()
        if "image" not in ct:
            preview = response.text[:700] if "text" in ct or "json" in ct else ct
            raise RuntimeError(f"non-image response: {preview}")
        raw = response.content
        if not _validate_image(raw, min_w=1000, min_h=1200):
            print("[image] Pollinations candidate rejected by technical quality gate")
            return None
        print("[image] Pollinations image accepted")
        return raw
    except requests.exceptions.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else "unknown"
        body = exc.response.text[:1000] if exc.response is not None else ""
        print(f"[image] Pollinations HTTP error: {code}; {body}")
        return None
    except Exception as exc:
        print(f"[image] Pollinations failed: {exc}")
        return None


def create_hero_image(prompt: str) -> tuple[Optional[bytes], str]:
    """Same ecosystem, quality-first. Agnes first; Pollinations Flux fallback."""
    raw = create_agnes_image(prompt)
    if raw:
        return raw, "agnes-image-2.1-flash"

    raw = create_pollinations_image(prompt)
    if raw:
        return raw, "pollinations-flux"

    return None, "none"
