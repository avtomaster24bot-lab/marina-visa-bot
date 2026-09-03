import io
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
LOGO_PATH = ROOT / "assets" / "logo.png"
FONT_REGULAR = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"]
FONT_BOLD = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"]


def _font(size: int, bold: bool = True):
    for p in (FONT_BOLD if bold else FONT_REGULAR):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _open_cover(data: bytes, size: tuple[int, int], centering=(0.5, 0.5)) -> Image.Image:
    try:
        src = Image.open(io.BytesIO(data)).convert("RGB")
        return ImageOps.fit(src, size, Image.LANCZOS, centering=centering)
    except Exception:
        return Image.new("RGB", size, (22, 28, 38))


def _logo(canvas: Image.Image, max_ratio: float = .18):
    if not LOGO_PATH.exists():
        return
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        target = int(canvas.width * max_ratio)
        ratio = target / max(1, logo.width)
        logo = logo.resize((target, max(1, int(logo.height * ratio))), Image.LANCZOS)
        canvas.alpha_composite(
            logo,
            (canvas.width - logo.width - int(canvas.width * .055), int(canvas.height * .045)),
        )
    except Exception as exc:
        print(f"[design] logo failed: {exc}")


def _gradient_overlay(size: tuple[int, int], top_alpha=15, bottom_alpha=205):
    w, h = size
    g = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(g)
    # Horizontal stripes are much faster than pixel-by-pixel loops.
    for y in range(h):
        t = y / max(1, h - 1)
        a = int(top_alpha + (bottom_alpha - top_alpha) * (t ** 2.0))
        draw.line((0, y, w, y), fill=(6, 12, 22, a))
    return g


def _wrap_all(draw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    cur = ""
    for word in words:
        candidate = f"{cur} {word}".strip()
        if not cur or draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            cur = candidate
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _fit_text(draw, text: str, max_width: int, max_lines: int, start_size: int, min_size: int):
    """Fit ALL words. Never truncate text; reduce font until the whole phrase fits."""
    clean = " ".join(str(text or "").split()).strip().upper()
    size = start_size
    while size >= min_size:
        font = _font(size, True)
        lines = _wrap_all(draw, clean, font, max_width)
        if lines and len(lines) <= max_lines:
            return font, lines
        size -= 2

    # Safety fallback: still preserve every word, even if more lines are needed.
    font = _font(min_size, True)
    return font, _wrap_all(draw, clean, font, max_width)


def _as_backgrounds(backgrounds, count: int) -> list[bytes]:
    if isinstance(backgrounds, (bytes, bytearray)):
        return [bytes(backgrounds)] * count
    if isinstance(backgrounds, Sequence):
        valid = [bytes(x) for x in backgrounds if isinstance(x, (bytes, bytearray)) and len(x) > 1000]
        if valid:
            while len(valid) < count:
                valid.append(valid[-1])
            return valid[:count]
    return []


def build_poster(background_bytes: bytes, headline: str, subheadline: str = "") -> bytes:
    size = (1080, 1350)
    base = _open_cover(background_bytes, size, centering=(0.5, 0.45)).convert("RGBA")
    base = Image.alpha_composite(base, _gradient_overlay(size, 5, 220))
    draw = ImageDraw.Draw(base)
    margin = 72

    pill_font = _font(30, True)
    pill = "MARINA • VISA & TRAVEL"
    pb = draw.textbbox((0, 0), pill, font=pill_font)
    pw, ph = pb[2] - pb[0] + 42, pb[3] - pb[1] + 24
    draw.rounded_rectangle((margin, 72, margin + pw, 72 + ph), radius=22, fill=(255, 255, 255, 222))
    draw.text((margin + 21, 82), pill, font=pill_font, fill=(22, 28, 38, 255))
    _logo(base, .17)

    hfont, lines = _fit_text(draw, headline, size[0] - 2 * margin, 3, 72, 52)
    line_h = int(getattr(hfont, "size", 60) * 1.18)
    y = size[1] - 330 - line_h * len(lines)
    for line in lines:
        draw.text((margin, y), line, font=hfont, fill=(255, 255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0, 80))
        y += line_h

    if subheadline:
        sfont, sub_lines = _fit_text(draw, subheadline, size[0] - 2 * margin, 2, 36, 28)
        y += 18
        for line in sub_lines:
            draw.text((margin, y), line, font=sfont, fill=(245, 245, 245, 245))
            y += int(getattr(sfont, "size", 32) * 1.35)

    out = io.BytesIO()
    base.convert("RGB").save(out, "JPEG", quality=94, optimize=True)
    return out.getvalue()


def _card(text: str, size: tuple[int, int], background_bytes: bytes, index: int, total: int) -> bytes:
    base = _open_cover(background_bytes, size, centering=(0.5, 0.48)).convert("RGBA")

    # Keep destination visible. Use overlays instead of blur.
    top_tint = Image.new("RGBA", size, (8, 12, 18, 42))
    base = Image.alpha_composite(base, top_tint)
    base = Image.alpha_composite(base, _gradient_overlay(size, 10, 188))

    draw = ImageDraw.Draw(base)
    margin = int(size[0] * .07)
    _logo(base, .17)

    fsmall = _font(28 if size[1] < 1600 else 30, True)
    draw.text(
        (margin, int(size[1] * .07)),
        f"{index:02d}/{total:02d}",
        font=fsmall,
        fill=(255, 255, 255, 225),
    )

    if size[1] < 1600:  # carousel 4:5
        start, minimum, max_lines = 66, 44, 4
        y_center = .59
    else:  # story 9:16
        start, minimum, max_lines = 74, 48, 4
        y_center = .55

    font, lines = _fit_text(
        draw,
        text,
        size[0] - 2 * margin,
        max_lines,
        start,
        minimum,
    )
    line_h = int(getattr(font, "size", 60) * 1.18)
    total_h = line_h * len(lines)
    y = int(size[1] * y_center) - total_h // 2

    for line in lines:
        draw.text((margin, y), line, font=font, fill=(255, 255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0, 90))
        y += line_h

    draw.rounded_rectangle((margin, y + 22, margin + 180, y + 29), radius=4, fill=(255, 255, 255, 225))

    out = io.BytesIO()
    base.convert("RGB").save(out, "JPEG", quality=94, optimize=True)
    return out.getvalue()


def build_carousel(slides: Iterable[str], backgrounds=None) -> list[bytes]:
    items = list(slides)[:5]
    bgs = _as_backgrounds(backgrounds, len(items))
    if not items or not bgs:
        return []
    return [_card(t, (1080, 1350), bgs[i], i + 1, len(items)) for i, t in enumerate(items)]


def build_stories(slides: Iterable[str], backgrounds=None) -> list[bytes]:
    items = list(slides)[:4]
    bgs = _as_backgrounds(backgrounds, len(items))
    if not items or not bgs:
        return []
    return [_card(t, (1080, 1920), bgs[i], i + 1, len(items)) for i, t in enumerate(items)]


def build_reel_overlay(text: str, position: str = "middle") -> bytes:
    size = (1080, 1920)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    font, lines = _fit_text(draw, text, 900, 3, 70, 48)
    lh = int(getattr(font, "size", 62) * 1.2)
    total = lh * len(lines)
    y = {"top": 300, "middle": (1920 - total) // 2, "bottom": 1420}.get(position, 700)
    top, bottom = y - 38, y + total + 38
    draw.rounded_rectangle((65, top, 1015, bottom), radius=34, fill=(7, 12, 20, 155))
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        tw = box[2] - box[0]
        draw.text(((1080 - tw) // 2, y), line, font=font, fill=(255, 255, 255, 255))
        y += lh
    _logo(canvas, .16)
    out = io.BytesIO()
    canvas.save(out, "PNG")
    return out.getvalue()


def save_social_assets(carousel: list[bytes], stories: list[bytes]) -> None:
    root = ROOT / "generated"
    car = root / "carousels"
    sto = root / "stories"
    car.mkdir(parents=True, exist_ok=True)
    sto.mkdir(parents=True, exist_ok=True)
    for p in car.glob("*.jpg"):
        p.unlink()
    for p in sto.glob("*.jpg"):
        p.unlink()
    for i, d in enumerate(carousel, 1):
        (car / f"slide_{i}.jpg").write_bytes(d)
    for i, d in enumerate(stories, 1):
        (sto / f"story_{i}.jpg").write_bytes(d)
    print(f"[social] saved carousel={len(carousel)} stories={len(stories)}")
