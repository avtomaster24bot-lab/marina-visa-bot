"""Offline preview package: no network, no Telegram, no paid APIs."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from content_generator import (
    build_offline_plan,
    contains_forbidden_claims,
    default_reel_scenes,
    germany_destination,
)
from reel_builder import build_branded_reel
from social_assets import (
    build_carousel,
    build_poster,
    build_stories,
    build_typographic_background,
    build_typographic_frames,
    save_social_assets,
)

ROOT = Path(__file__).resolve().parent
USAGE = """Usage:
  python smart_poster.py --preview [--output DIR]
  OFFLINE_PREVIEW=1 python smart_poster.py

Preview writes a local poster, captions and a 15-25s motion reel.
It does not call Telegram, Agnes, Pollinations or any other network API.
It does not read Telegram or Agnes secrets and does not publish anything.
"""


def parse_cli(argv: Optional[list[str]] = None) -> dict:
    args = list(argv or [])
    preview = os.getenv("OFFLINE_PREVIEW", "").strip().lower() in {"1", "true", "yes"}
    output = None
    show_help = False
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in {"--preview", "--offline-preview"}:
            preview = True
        elif arg in {"--help", "-h"}:
            show_help = True
        elif arg in {"--output", "-o"} and i + 1 < len(args):
            output = Path(args[i + 1])
            i += 1
        elif arg.startswith("--output="):
            output = Path(arg.split("=", 1)[1])
        i += 1
    return {"preview": preview, "output": output, "help": show_help}


def is_offline_preview(argv: Optional[list[str]] = None) -> bool:
    return bool(parse_cli(argv)["preview"])


def run_offline_preview(output_dir: Optional[Path] = None, argv: Optional[list[str]] = None) -> int:
    parsed = parse_cli(argv)
    if parsed["help"] and not parsed["preview"]:
        print(USAGE)
        return 0

    target = Path(output_dir or parsed["output"] or (ROOT / "generated"))
    target.mkdir(parents=True, exist_ok=True)

    # Default the preview to Germany so a manual trial matches the main offer.
    # Weighted selection remains in build_offline_plan / choose_destination for
    # production fallback and unit tests.
    plan = build_offline_plan(destination=germany_destination())
    if contains_forbidden_claims(plan.telegram_text) or contains_forbidden_claims(plan.instagram_caption):
        print("[preview] safe-copy gate failed")
        return 1

    print(f"[preview] building offline package for {plan.country} -> {target}")
    poster_bg = build_typographic_background((1080, 1350), variant=0)
    poster = build_poster(poster_bg, plan.headline, plan.subheadline)
    scenes = default_reel_scenes(plan.country)
    reel_frames = build_typographic_frames(scenes, size=(1080, 1920))
    decorative = [build_typographic_background((1080, 1350), variant=i) for i in range(5)]
    carousel = build_carousel(plan.carousel_slides, decorative)
    stories = build_stories(plan.story_slides, decorative[:4])

    # save_social_assets writes into ROOT/generated; copy locally if needed below.
    if target.resolve() == (ROOT / "generated").resolve():
        save_social_assets(carousel, stories)

    reel = build_branded_reel(reel_frames, source_video=None, duration=20.0)
    if not poster or len(poster) < 20_000:
        print("[preview] poster was not created")
        return 1
    if not reel:
        print("[preview] reel was not created")
        return 1

    (target / "content_plan.json").write_text(
        json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (target / "instagram_caption.txt").write_text(plan.instagram_caption, encoding="utf-8")
    (target / "post.txt").write_text(plan.telegram_text, encoding="utf-8")
    (target / "post.jpg").write_bytes(poster)
    (target / "poster.jpg").write_bytes(poster)
    (target / "reel.mp4").write_bytes(reel)
    (target / "preview.mp4").write_bytes(reel)

    scenes_dir = target / "scenes"
    scenes_dir.mkdir(exist_ok=True)
    for i, frame in enumerate(reel_frames, 1):
        (scenes_dir / f"scene_{i:02d}.jpg").write_bytes(frame)

    preview_plan = {
        "mode": "offline_preview",
        "published": False,
        "network_calls": 0,
        "paid_api_calls": 0,
        "telegram_sends": 0,
        "country": plan.country,
        "visual_type": "original_typographic_motion_graphics",
        "music": "original procedural instrumental; third-party asset files are not selected",
        "duration_seconds": 20,
        "scenes": scenes,
        "limitations": [
            "No voiceover",
            "No live visa requirements checked",
            "No verified lead attribution or deep link",
            "No Telegram publication",
        ],
    }
    (target / "preview_plan.json").write_text(
        json.dumps(preview_plan, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[preview] wrote poster, reel and copy to {target} without publishing")
    return 0
