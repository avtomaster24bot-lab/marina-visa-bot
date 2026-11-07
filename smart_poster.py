import json
import os
import sys
from pathlib import Path
from typing import NamedTuple

from content_generator import (
    build_offline_plan,
    contains_forbidden_claims,
    destination_for_country,
    ensure_safe_plan,
    generate_content_plan,
    plan_copy_is_safe,
)
from media_library import choose_client_image
from offline_preview import USAGE, is_offline_preview, parse_cli, run_offline_preview
from reel_builder import build_branded_reel
from social_assets import (
    build_carousel,
    build_poster,
    build_stories,
    build_typographic_background,
    save_social_assets,
)

ROOT = Path(__file__).resolve().parent
TELEGRAM_CAPTION_LIMIT = 1024
SECRET_ENV_KEYS = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHANNEL_ID",
    "AGNES_API_KEY",
    "BOT_TOKEN",
    "POLLINATIONS_API_KEY",
)


class PublishResult(NamedTuple):
    main_ok: bool
    reel_status: str  # sent | failed | skipped

    def __bool__(self) -> bool:
        return self.main_ok


def _telegram_creds() -> tuple[str, str]:
    return (
        os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
        os.environ.get("TELEGRAM_CHANNEL_ID", "").strip(),
    )


def telegram_photo_caption(text: str, limit: int = TELEGRAM_CAPTION_LIMIT) -> str:
    """Keep captions inside Telegram's photo limit without a mid-word cut when possible."""
    raw = str(text or "").strip()
    if len(raw) <= limit:
        return raw
    clipped = raw[: limit - 1]
    if "\n" in clipped:
        candidate = clipped.rsplit("\n", 1)[0].rstrip()
        if len(candidate) >= limit // 2:
            return candidate + "…"
    if " " in clipped:
        candidate = clipped.rsplit(" ", 1)[0].rstrip()
        if candidate:
            return candidate + "…"
    return clipped.rstrip() + "…"


def _send_photo(image_bytes: bytes, caption: str) -> bool:
    if not image_bytes:
        return False
    token, channel_id = _telegram_creds()
    if not token or not channel_id:
        print("[telegram] missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID")
        return False
    try:
        import requests

        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            data={"chat_id": channel_id, "caption": telegram_photo_caption(caption)},
            files={"photo": ("marina-post.jpg", image_bytes, "image/jpeg")},
            timeout=(15, 120),
        )
        if response.status_code != 200:
            print(f"[telegram] sendPhoto failed: {response.text[:1200]}")
            return False
        print("[telegram] main poster + text published")
        return True
    except Exception as exc:
        print(f"[telegram] sendPhoto error: {exc}")
        return False


def _send_video(video_bytes: bytes, caption: str = "") -> bool:
    if not video_bytes:
        return False
    token, channel_id = _telegram_creds()
    if not token or not channel_id:
        print("[telegram] missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID")
        return False
    try:
        import requests

        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendVideo",
            data={
                "chat_id": channel_id,
                "supports_streaming": "true",
                "caption": telegram_photo_caption(caption),
            },
            files={"video": ("marina-reel.mp4", video_bytes, "video/mp4")},
            timeout=(30, 240),
        )
        if response.status_code != 200:
            print(f"[telegram] sendVideo failed: {response.text[:1200]}")
            return False
        print("[telegram] branded Reel published as a second message")
        return True
    except Exception as exc:
        print(f"[telegram] sendVideo error: {exc}")
        return False


def _send_text(text: str) -> bool:
    token, channel_id = _telegram_creds()
    if not token or not channel_id:
        print("[telegram] missing credentials; cannot send text fallback")
        return False
    try:
        import requests

        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": channel_id,
                "text": str(text or "")[:4096],
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        if response.status_code != 200:
            print(f"[telegram] sendMessage failed: {response.text[:1200]}")
            return False
        print("[telegram] text fallback published")
        return True
    except Exception as exc:
        print(f"[telegram] sendMessage error: {exc}")
        return False


def _validate(plan, poster: bytes | None) -> bool:
    if not plan_copy_is_safe(plan):
        return False
    if not poster or len(poster) < 20_000:
        return False
    return True


def publication_exit_code(result) -> int:
    main_ok = result.main_ok if hasattr(result, "main_ok") else bool(result)
    return 0 if main_ok else 1


def publish_package(plan, poster, reel, *, send_photo=None, send_video=None, send_text=None) -> PublishResult:
    send_photo = send_photo or _send_photo
    send_video = send_video or _send_video
    send_text = send_text or _send_text

    main_ok = bool(poster) and send_photo(poster, plan.telegram_text)
    if not main_ok:
        main_ok = send_text(plan.telegram_text)

    if reel and plan_copy_is_safe(plan):
        reel_caption = f"🎬 {plan.reel_hook}\n{plan.reel_cta}"
        if contains_forbidden_claims(reel_caption):
            print("[telegram] Reel caption failed safety gate; skipping reel send")
            reel_status = "skipped"
        elif send_video(reel, reel_caption):
            reel_status = "sent"
        else:
            reel_status = "failed"
            print(
                "[telegram] Reel send failed; "
                f"telegram_main={'yes' if main_ok else 'no'} reel=failed"
            )
    else:
        reel_status = "skipped"
        if reel and not plan_copy_is_safe(plan):
            print("[telegram] unsafe plan after fallback; reel was not sent")
        else:
            print("[telegram] Reel unavailable; main poster status unchanged")

    print(f"[telegram] publish status: telegram_main={'yes' if main_ok else 'no'} reel={reel_status}")
    return PublishResult(main_ok=bool(main_ok), reel_status=reel_status)


def _load_hero_image(plan) -> tuple[bytes | None, str]:
    raw_image = choose_client_image()
    if raw_image:
        return raw_image, "client"
    from image_generator import create_hero_image

    raw_image, source = create_hero_image(plan.image_prompt)
    if raw_image:
        return raw_image, source
    return build_typographic_background((1080, 1350), variant=0), "typographic"


def _build_social_backgrounds(plan, hero_image: bytes | None) -> list[bytes]:
    """Generate five visually different scenes for the same campaign.

    Quality-first but failure-safe: if one social image fails, reuse the hero/last good
    scene rather than breaking Telegram or the whole workflow.
    """
    generated = ROOT / "generated" / "social_visuals"
    generated.mkdir(parents=True, exist_ok=True)
    for path in generated.glob("*.jpg"):
        path.unlink()

    backgrounds: list[bytes] = []
    prompts = list(getattr(plan, "social_visual_prompts", []) or [])[:5]
    if prompts:
        from image_generator import create_hero_image

        for i, prompt in enumerate(prompts, 1):
            print(f"[social-image] generating scene {i}/{len(prompts)}")
            raw, source = create_hero_image(prompt)
            if raw:
                backgrounds.append(raw)
                (generated / f"scene_{i}.jpg").write_bytes(raw)
                print(f"[social-image] scene {i} ready via {source}")
            else:
                fallback = backgrounds[-1] if backgrounds else hero_image
                if fallback:
                    backgrounds.append(fallback)
                    (generated / f"scene_{i}.jpg").write_bytes(fallback)
                    print(f"[social-image] scene {i} fallback used")

    while hero_image and len(backgrounds) < 5:
        backgrounds.append(hero_image)

    if len(backgrounds) < 5:
        while len(backgrounds) < 5:
            backgrounds.append(build_typographic_background((1080, 1350), variant=len(backgrounds)))

    return backgrounds[:5]


def build_visual_package(plan) -> dict:
    raw_image, image_source = _load_hero_image(plan)
    poster = build_poster(raw_image, plan.headline, plan.subheadline) if raw_image else None
    social_backgrounds = _build_social_backgrounds(plan, raw_image)
    carousel = build_carousel(plan.carousel_slides, social_backgrounds) if social_backgrounds else []
    stories = build_stories(plan.story_slides, social_backgrounds[:4]) if social_backgrounds else []
    save_social_assets(carousel, stories)
    reel_frames = stories if len(stories) >= 2 else social_backgrounds
    reel = build_branded_reel(reel_frames, source_video=None, duration=20.0) if len(reel_frames) >= 2 else None
    return {
        "raw_image": raw_image,
        "image_source": image_source,
        "poster": poster,
        "reel": reel,
        "carousel": carousel,
        "stories": stories,
        "social_backgrounds": social_backgrounds,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    parsed = parse_cli(args)
    if parsed["help"] and not parsed["preview"]:
        print(USAGE)
        return 0
    if is_offline_preview(args):
        print("[preview] offline mode: no network, no Telegram, no paid APIs, no secret reads")
        return run_offline_preview(argv=args)

    generated = ROOT / "generated"
    generated.mkdir(exist_ok=True)

    print("STEP 1/9: creative direction + content plan")
    plan = generate_content_plan()
    selected_country = plan.country
    if not plan_copy_is_safe(plan):
        print("[validate] public copy failed safety gate before render; using safe fallback")
        plan = ensure_safe_plan(plan)
    if not plan_copy_is_safe(plan):
        print("[validate] safe fallback copy is still invalid; refusing to publish")
        return 1
    print(f"[plan] {plan.country} | {plan.content_format} | {plan.headline}")
    print(f"[plan] carousel: {plan.carousel_slides}")
    print(f"[plan] stories: {plan.story_slides}")

    print("STEP 2/9: premium hero visual")
    print("STEP 3/9: generate five campaign social scenes")
    print("STEP 4/9: build carousel + Stories from different scenes")
    print("STEP 5/9: skip unused paid B-roll")
    print("[video] Agnes video is not requested; the reel is a local motion edit with music")
    print("STEP 6/9: build branded 15-25s Reel")
    package = build_visual_package(plan)
    raw_image = package["raw_image"]
    image_source = package["image_source"]
    poster = package["poster"]
    reel = package["reel"]
    carousel = package["carousel"]
    stories = package["stories"]
    social_backgrounds = package["social_backgrounds"]

    print("STEP 7/9: save full social package")
    (generated / "content_plan.json").write_text(
        json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (generated / "instagram_caption.txt").write_text(plan.instagram_caption, encoding="utf-8")
    if poster:
        (generated / "post.jpg").write_bytes(poster)
    if reel:
        (generated / "reel.mp4").write_bytes(reel)

    print("STEP 8/9: validate assembled package")
    if not _validate(plan, poster):
        print("[validate] assembled package rejected; rebuilding from safe copy")
        if not plan_copy_is_safe(plan):
            plan = build_offline_plan(destination=destination_for_country(selected_country))
            reel = None
        if not plan_copy_is_safe(plan):
            print("[validate] safe fallback is still invalid; refusing to publish")
            return 1
        package = build_visual_package(plan)
        raw_image = package["raw_image"]
        image_source = package["image_source"]
        poster = package["poster"]
        reel = package["reel"]
        carousel = package["carousel"]
        stories = package["stories"]
        social_backgrounds = package["social_backgrounds"]
        if not _validate(plan, poster):
            print("[validate] rebuilt package is still invalid; refusing to publish")
            return 1

    if reel and not plan_copy_is_safe(plan):
        print("[validate] disabling reel because public copy is unsafe")
        reel = None

    result = publish_package(plan, poster, reel)

    print("STEP 9/9: result")
    print(
        "RESULT: "
        f"telegram_main={'yes' if result.main_ok else 'no'} "
        f"image={image_source if raw_image else 'none'} "
        f"broll=skipped "
        f"reel={result.reel_status} "
        f"social_scenes={len(social_backgrounds)} "
        f"carousel={len(carousel)} stories={len(stories)}"
    )
    code = publication_exit_code(result)
    if code != 0:
        print("[result] publication failed; exiting with code 1")
    elif result.reel_status == "failed":
        print("[result] partial success: main post sent, reel send failed")
    return code


if __name__ == "__main__":
    sys.exit(main())
