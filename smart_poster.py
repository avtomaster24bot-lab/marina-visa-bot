import json
import os
from pathlib import Path

import requests

from content_generator import generate_content_plan
from image_generator import create_hero_image
from media_library import choose_client_image, choose_client_video
from post_generator import send_to_telegram
from reel_builder import build_branded_reel
from social_assets import build_carousel, build_poster, build_stories, save_social_assets
from video_generator import create_agnes_video

ROOT = Path(__file__).resolve().parent
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip()


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
            print(f"[telegram] sendPhoto failed: {r.text[:1200]}")
            return False
        print("[telegram] main poster + text published")
        return True
    except Exception as exc:
        print(f"[telegram] sendPhoto error: {exc}")
        return False


def _send_video(video_bytes: bytes, caption: str = "") -> bool:
    if not video_bytes:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo",
            data={
                "chat_id": CHANNEL_ID,
                "supports_streaming": "true",
                "caption": caption[:1024],
            },
            files={"video": ("marina-reel.mp4", video_bytes, "video/mp4")},
            timeout=(30, 240),
        )
        if r.status_code != 200:
            print(f"[telegram] sendVideo failed: {r.text[:1200]}")
            return False
        print("[telegram] branded Reel published as a second message")
        return True
    except Exception as exc:
        print(f"[telegram] sendVideo error: {exc}")
        return False


def _validate(plan, poster: bytes | None) -> bool:
    text = (plan.telegram_text or "").lower()
    forbidden = [
        "100%",
        "гарантия визы",
        "гарантируем визу",
        "точно получите визу",
        "без отказа",
    ]
    if not plan.telegram_text.strip() or any(x in text for x in forbidden):
        return False
    if not poster or len(poster) < 20_000:
        return False
    return True


def main():
    generated = ROOT / "generated"
    generated.mkdir(exist_ok=True)

    print("STEP 1/9: creative direction + content plan")
    plan = generate_content_plan()
    print(f"[plan] {plan.country} | {plan.content_format} | {plan.headline}")

    print("STEP 2/9: premium hero visual")
    raw_image = choose_client_image()
    image_source = "client" if raw_image else "none"
    if not raw_image:
        raw_image, image_source = create_hero_image(plan.image_prompt)
    poster = build_poster(raw_image, plan.headline, plan.subheadline) if raw_image else None

    print("STEP 3/9: build Instagram carousel + Stories first")
    carousel = build_carousel(plan.carousel_slides, raw_image) if raw_image else []
    stories = build_stories(plan.story_slides, raw_image) if raw_image else []
    save_social_assets(carousel, stories)

    print("STEP 4/9: optional Agnes cinematic B-roll")
    source_video = choose_client_video()
    video_source = "client" if source_video else "agnes"
    if not source_video:
        source_video = create_agnes_video(plan.video_prompt)
    if not source_video:
        video_source = "none"

    # Preserve raw B-roll for review, but never let a weak/raw clip replace the branded Reel.
    if source_video:
        (generated / "agnes_broll.mp4").write_bytes(source_video)
        print(f"[video] raw B-roll saved for review: {len(source_video)} bytes")

    print("STEP 5/9: build deterministic branded Reel from Story frames")
    reel = build_branded_reel(stories, source_video=source_video)

    print("STEP 6/9: save full social package")
    (generated / "content_plan.json").write_text(
        json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (generated / "instagram_caption.txt").write_text(plan.instagram_caption, encoding="utf-8")
    if poster:
        (generated / "post.jpg").write_bytes(poster)
    if reel:
        (generated / "reel.mp4").write_bytes(reel)

    print("STEP 7/9: validate main post")
    if not _validate(plan, poster):
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

    print("STEP 8/9: publish Telegram in two coherent messages")
    # IMPORTANT: the image is ALWAYS the main post. A Reel never replaces it.
    main_post_ok = _send_photo(poster, plan.telegram_text)
    if not main_post_ok:
        main_post_ok = send_to_telegram(plan.telegram_text)

    reel_ok = False
    if reel:
        reel_caption = f"🎬 {plan.reel_hook}\n{plan.reel_cta}"
        reel_ok = _send_video(reel, reel_caption)
    else:
        print("[telegram] Reel unavailable; main poster still published")

    print("STEP 9/9: result")
    print(
        "RESULT: "
        f"telegram_main={'yes' if main_post_ok else 'no'} "
        f"image={image_source if raw_image else 'none'} "
        f"broll={video_source} "
        f"reel={'yes' if reel_ok else 'no'} "
        f"carousel={len(carousel)} stories={len(stories)}"
    )


if __name__ == "__main__":
    main()
