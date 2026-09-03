import io
import json
import os
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image

from content_generator import generate_content_plan
from media_library import choose_client_image, choose_client_video
from post_generator import send_to_telegram
from reel_builder import build_branded_reel
from social_assets import build_carousel, build_poster, build_stories, save_social_assets
from video_generator import create_agnes_video

ROOT = Path(__file__).resolve().parent
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip()


def _pollinations_image(prompt: str):
    """Existing primary image provider, but with a much stronger art-directed prompt."""
    try:
        final_prompt = (
            prompt.strip()
            + ", premium travel advertising campaign, sophisticated editorial photography, visual storytelling, "
              "cinematic natural light, refined composition, realistic anatomy, elegant color grading, high-end tourism brand aesthetic, "
              "no readable text, no watermark, no generated logo, no fake visa stamp, no readable personal data"
        )
        url = f"https://image.pollinations.ai/prompt/{quote(final_prompt)}"
        print("[image] requesting art-directed Pollinations image...")
        r = requests.get(url, timeout=(15, 150))
        r.raise_for_status()
        ct = (r.headers.get("content-type") or "").lower()
        if "image" not in ct or len(r.content) < 5000:
            raise RuntimeError(f"bad image response: {ct}, {len(r.content)} bytes")
        im = Image.open(io.BytesIO(r.content))
        im.verify()
        print(f"[image] image ready: {len(r.content)} bytes")
        return r.content
    except Exception as exc:
        print(f"[image] Pollinations failed: {exc}")
        return None


def _send_video(video_bytes: bytes, caption: str, thumbnail: bytes | None = None) -> bool:
    """One coherent Telegram post: Reel + branded cover + caption."""
    if not video_bytes:
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
    files = {"video": ("marina-reel.mp4", video_bytes, "video/mp4")}
    if thumbnail:
        files["thumbnail"] = ("cover.jpg", thumbnail, "image/jpeg")
    data = {
        "chat_id": CHANNEL_ID,
        "supports_streaming": "true",
        "caption": caption[:1024],
    }
    try:
        r = requests.post(url, data=data, files=files, timeout=(30, 210))
        if r.status_code != 200:
            print(f"[telegram] sendVideo failed: {r.text[:1000]}")
            return False
        print("[telegram] coherent Reel post published")
        return True
    except Exception as exc:
        print(f"[telegram] sendVideo error: {exc}")
        return False


def _send_photo(image_bytes: bytes, caption: str) -> bool:
    if not image_bytes:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={"chat_id": CHANNEL_ID, "caption": caption[:1024]},
            files={"photo": ("marina-post.jpg", image_bytes, "image/jpeg")},
            timeout=(15, 120),
        )
        if r.status_code != 200:
            print(f"[telegram] sendPhoto failed: {r.text[:1000]}")
            return False
        return True
    except Exception as exc:
        print(f"[telegram] sendPhoto error: {exc}")
        return False


def _validate(plan, image_bytes, video_bytes):
    text = plan.telegram_text.lower()
    forbidden = ["100%", "гарантия визы", "гарантируем визу", "точно получите визу", "без отказа"]
    if not plan.telegram_text.strip() or any(x in text for x in forbidden):
        return False
    if image_bytes and len(image_bytes) < 5000:
        return False
    if video_bytes and len(video_bytes) < 20000:
        return False
    return True


def main():
    generated = ROOT / "generated"
    generated.mkdir(exist_ok=True)

    print("STEP 1/9: creative direction + content plan")
    plan = generate_content_plan()
    print(f"[plan] {plan.country} | {plan.content_format} | {plan.headline}")

    print("STEP 2/9: hero visual")
    raw_image = choose_client_image()
    image_source = "client" if raw_image else "pollinations"
    if not raw_image:
        raw_image = _pollinations_image(plan.image_prompt)
    poster = build_poster(raw_image, plan.headline, plan.subheadline) if raw_image else None

    print("STEP 3/9: cinematic source video")
    source_video = choose_client_video()
    video_source = "client" if source_video else "agnes"
    if not source_video:
        source_video = create_agnes_video(plan.video_prompt)
    if not source_video:
        video_source = "none"

    print("STEP 4/9: brand the Reel with timed captions")
    reel = build_branded_reel(source_video, plan.reel_hook, plan.reel_middle, plan.reel_cta) if source_video else None

    print("STEP 5/9: build Instagram carousel + Stories")
    carousel = build_carousel(plan.carousel_slides, raw_image) if raw_image else []
    stories = build_stories(plan.story_slides, raw_image) if raw_image else []
    save_social_assets(carousel, stories)

    print("STEP 6/9: save full social package")
    (generated / "content_plan.json").write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (generated / "instagram_caption.txt").write_text(plan.instagram_caption, encoding="utf-8")
    if poster: (generated / "post.jpg").write_bytes(poster)
    if reel: (generated / "reel.mp4").write_bytes(reel)

    print("STEP 7/9: validate")
    if not _validate(plan, poster, reel):
        print("[validate] smart package rejected; safe legacy fallback")
        import post_generator
        legacy_text = post_generator.generate_post()
        prompt = post_generator.generate_image_prompt(legacy_text)
        img = post_generator.fetch_pollinations_image(prompt)
        if img:
            title = post_generator.extract_image_title(legacy_text)
            decorated = post_generator.add_text_overlay(img, title) or img
            if post_generator.send_photo_to_telegram(decorated, legacy_text):
                return
        send_to_telegram(legacy_text)
        return

    print("STEP 8/9: publish Telegram as ONE coherent content unit")
    published = False
    if reel:
        published = _send_video(reel, plan.telegram_text, poster)
    if not published and poster:
        published = _send_photo(poster, plan.telegram_text)
    if not published:
        published = send_to_telegram(plan.telegram_text)

    print("STEP 9/9: result")
    print(
        "RESULT: "
        f"telegram={'yes' if published else 'no'} image={image_source if raw_image else 'none'} "
        f"video={video_source} reel={'yes' if reel else 'no'} "
        f"carousel={len(carousel)} stories={len(stories)}"
    )


if __name__ == "__main__":
    main()
