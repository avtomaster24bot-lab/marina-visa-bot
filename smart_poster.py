import io
import json
import os
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image

from content_generator import generate_content_plan
from media_library import choose_client_image, choose_client_video
from post_generator import add_text_overlay, send_to_telegram
from social_assets import build_carousel, build_stories, save_social_assets
from video_generator import create_agnes_video

ROOT = Path(__file__).resolve().parent
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip()


def _pollinations_image(prompt: str):
    try:
        url = f"https://image.pollinations.ai/prompt/{quote(prompt)}"
        print("[image] requesting Pollinations image...")
        response = requests.get(url, timeout=(15, 120))
        response.raise_for_status()
        content_type = (response.headers.get("content-type") or "").lower()
        if "image" not in content_type or not response.content:
            raise RuntimeError(f"unexpected content type: {content_type}")
        Image.open(io.BytesIO(response.content)).verify()
        print(f"[image] Pollinations image downloaded: {len(response.content)} bytes")
        return response.content
    except Exception as exc:
        print(f"[image] Pollinations failed: {exc}")
        return None


def _send_photo(image_bytes: bytes, caption: str = "") -> bool:
    if not image_bytes:
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    files = {"photo": ("visa-post.jpg", image_bytes, "image/jpeg")}
    data = {"chat_id": CHANNEL_ID}
    if caption:
        data["caption"] = caption[:1024]
    try:
        response = requests.post(url, data=data, files=files, timeout=(15, 90))
        if response.status_code != 200:
            print(f"[telegram] sendPhoto failed: {response.text[:800]}")
            return False
        return True
    except Exception as exc:
        print(f"[telegram] sendPhoto error: {exc}")
        return False


def _send_video(video_bytes: bytes, caption: str = "") -> bool:
    if not video_bytes:
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
    files = {"video": ("visa-reel.mp4", video_bytes, "video/mp4")}
    data = {"chat_id": CHANNEL_ID, "supports_streaming": "true"}
    if caption:
        data["caption"] = caption[:1024]
    try:
        response = requests.post(url, data=data, files=files, timeout=(30, 180))
        if response.status_code != 200:
            print(f"[telegram] sendVideo failed: {response.text[:800]}")
            return False
        return True
    except Exception as exc:
        print(f"[telegram] sendVideo error: {exc}")
        return False


def _send_album(image_bytes: bytes, video_bytes: bytes, caption: str) -> bool:
    """Send photo + video as one Telegram media group when both exist."""
    if not image_bytes or not video_bytes:
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMediaGroup"
    album_caption = caption if len(caption) <= 1024 else ""
    media = [
        {"type": "photo", "media": "attach://photo", "caption": album_caption},
        {"type": "video", "media": "attach://video", "supports_streaming": True},
    ]
    files = {
        "photo": ("visa-post.jpg", image_bytes, "image/jpeg"),
        "video": ("visa-reel.mp4", video_bytes, "video/mp4"),
    }
    data = {"chat_id": CHANNEL_ID, "media": json.dumps(media, ensure_ascii=False)}
    try:
        if not album_caption:
            # Telegram captions are limited. Preserve the full text in a separate message.
            if not send_to_telegram(caption):
                return False
        response = requests.post(url, data=data, files=files, timeout=(30, 180))
        if response.status_code != 200:
            print(f"[telegram] sendMediaGroup failed: {response.text[:800]}")
            return False
        print("[telegram] photo + video published as media group")
        return True
    except Exception as exc:
        print(f"[telegram] media group error: {exc}")
        return False


def _validate(plan, image_bytes, video_bytes) -> bool:
    if not plan.telegram_text.strip():
        print("[validate] empty Telegram text")
        return False
    if not image_bytes:
        print("[validate] no image; text fallback remains allowed")
    if video_bytes is not None and len(video_bytes) < 1024:
        print("[validate] video too small; dropping it")
        return False
    forbidden = ("100% успех", "100% результат", "гарантируем визу", "гарантия визы")
    normalized = plan.telegram_text.lower()
    if any(x in normalized for x in forbidden):
        print("[validate] forbidden guarantee detected; aborting generated package")
        return False
    return True


def main() -> None:
    print("STEP 1/8: building content plan")
    plan = generate_content_plan()
    print(f"[plan] {plan.country} | {plan.service} | {plan.angle}")

    print("STEP 2/8: selecting/generating image")
    raw_image = choose_client_image()
    image_source = "client" if raw_image else "pollinations"
    if raw_image is None:
        raw_image = _pollinations_image(plan.image_prompt)
    final_image = None
    if raw_image:
        final_image = add_text_overlay(raw_image, plan.headline) or raw_image

    print("STEP 3/8: selecting/generating video")
    video_bytes = choose_client_video()
    video_source = "client" if video_bytes else "agnes"
    if video_bytes is None:
        video_bytes = create_agnes_video(plan.video_prompt)
    if video_bytes is None:
        video_source = "none"

    print("STEP 4/8: building Instagram-ready carousel/stories")
    carousel = build_carousel(plan.carousel_slides, raw_image)
    stories = build_stories(plan.story_slides, raw_image)
    save_social_assets(carousel, stories)
    (ROOT / "generated").mkdir(exist_ok=True)
    (ROOT / "generated" / "instagram_caption.txt").write_text(plan.instagram_caption, encoding="utf-8")
    (ROOT / "generated" / "content_plan.json").write_text(
        json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if final_image:
        (ROOT / "generated" / "post.jpg").write_bytes(final_image)
    if video_bytes:
        (ROOT / "generated" / "reel.mp4").write_bytes(video_bytes)

    print("STEP 5/8: validating package")
    if not _validate(plan, final_image, video_bytes):
        print("[validate] generated package rejected; using legacy poster fallback")
        # Import only on failure to preserve the original proven behavior.
        import post_generator
        legacy_text = post_generator.generate_post()
        prompt = post_generator.generate_image_prompt(legacy_text)
        legacy_image = post_generator.fetch_pollinations_image(prompt)
        if legacy_image:
            title = post_generator.extract_image_title(legacy_text)
            decorated = post_generator.add_text_overlay(legacy_image, title) or legacy_image
            if post_generator.send_photo_to_telegram(decorated, legacy_text):
                return
        post_generator.send_to_telegram(legacy_text)
        return

    print("STEP 6/8: publishing Telegram")
    published = False
    if final_image and video_bytes:
        published = _send_album(final_image, video_bytes, plan.telegram_text)
    elif video_bytes:
        published = _send_video(video_bytes, plan.telegram_text)
    elif final_image:
        published = _send_photo(final_image, plan.telegram_text)
    if not published:
        published = send_to_telegram(plan.telegram_text)

    print("STEP 7/8: Instagram package prepared")
    print("[instagram] assets saved under generated/; API publishing remains disabled until public-media delivery is configured")

    print("STEP 8/8: result")
    print(
        "RESULT: "
        f"text=yes image={'yes' if final_image else 'no'} image_source={image_source} "
        f"video={'yes' if video_bytes else 'no'} video_source={video_source} "
        f"telegram={'yes' if published else 'no'} carousel={len(carousel)} stories={len(stories)}"
    )


if __name__ == "__main__":
    main()
