import io
import os
import textwrap
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
LOGO_PATH = ROOT / "assets" / "logo.png"

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def _font(size: int):
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _logo(canvas: Image.Image, max_width_ratio: float = 0.20):
    if not LOGO_PATH.exists():
        return
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        max_w = int(canvas.width * max_width_ratio)
        scale = max_w / max(1, logo.width)
        logo = logo.resize((max_w, max(1, int(logo.height * scale))), Image.LANCZOS)
        canvas.alpha_composite(logo, (canvas.width - logo.width - int(canvas.width * .05), int(canvas.height * .04)))
    except Exception as exc:
        print(f"[social] logo overlay failed: {exc}")


def _card(text: str, size: tuple[int, int], background_bytes: bytes | None = None) -> bytes:
    w, h = size
    if background_bytes:
        try:
            base = Image.open(io.BytesIO(background_bytes)).convert("RGB")
            base = ImageOps.fit(base, size, Image.LANCZOS)
        except Exception:
            base = Image.new("RGB", size, (28, 35, 48))
    else:
        base = Image.new("RGB", size, (28, 35, 48))

    rgba = base.convert("RGBA")
    shade = Image.new("RGBA", size, (0, 0, 0, 125))
    rgba = Image.alpha_composite(rgba, shade)
    draw = ImageDraw.Draw(rgba)

    font = _font(max(40, w // 13))
    lines = textwrap.wrap(text.strip(), width=20)[:5]
    line_h = int(getattr(font, "size", 60) * 1.25)
    total_h = line_h * len(lines)
    y = (h - total_h) // 2
    margin = int(w * 0.08)
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        tw = box[2] - box[0]
        draw.text(((w - tw) // 2, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_h

    _logo(rgba)
    out = io.BytesIO()
    rgba.convert("RGB").save(out, format="JPEG", quality=91)
    return out.getvalue()


def build_carousel(slides: Iterable[str], background_bytes: bytes | None = None) -> list[bytes]:
    return [_card(text, (1080, 1350), background_bytes) for text in list(slides)[:6]]


def build_stories(slides: Iterable[str], background_bytes: bytes | None = None) -> list[bytes]:
    return [_card(text, (1080, 1920), background_bytes) for text in list(slides)[:5]]


def save_social_assets(carousel: list[bytes], stories: list[bytes]) -> None:
    root = ROOT / "generated"
    car_dir = root / "carousels"
    story_dir = root / "stories"
    car_dir.mkdir(parents=True, exist_ok=True)
    story_dir.mkdir(parents=True, exist_ok=True)
    for p in car_dir.glob("*.jpg"):
        p.unlink()
    for p in story_dir.glob("*.jpg"):
        p.unlink()
    for i, data in enumerate(carousel, 1):
        (car_dir / f"slide_{i}.jpg").write_bytes(data)
    for i, data in enumerate(stories, 1):
        (story_dir / f"story_{i}.jpg").write_bytes(data)
    print(f"[social] saved carousel={len(carousel)} stories={len(stories)}")
