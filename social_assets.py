import io
import textwrap
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

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


def _open_cover(data: bytes, size: tuple[int, int]) -> Image.Image:
    try:
        src = Image.open(io.BytesIO(data)).convert("RGB")
        return ImageOps.fit(src, size, Image.LANCZOS, centering=(0.5, 0.45))
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
        canvas.alpha_composite(logo, (canvas.width - logo.width - int(canvas.width * .055), int(canvas.height * .045)))
    except Exception as exc:
        print(f"[design] logo failed: {exc}")


def _gradient_overlay(size: tuple[int, int], top_alpha=15, bottom_alpha=205):
    w, h = size
    g = Image.new("RGBA", size, (0,0,0,0))
    px = g.load()
    for y in range(h):
        t = y / max(1, h-1)
        a = int(top_alpha + (bottom_alpha-top_alpha) * (t ** 2.2))
        for x in range(w):
            px[x,y] = (6, 12, 22, a)
    return g


def _wrap(draw, text, font, max_width, max_lines=4):
    words = text.split()
    lines, cur = [], ""
    for word in words:
        candidate = f"{cur} {word}".strip()
        if draw.textbbox((0,0), candidate, font=font)[2] <= max_width or not cur:
            cur = candidate
        else:
            lines.append(cur)
            cur = word
            if len(lines) >= max_lines-1:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines


def build_poster(background_bytes: bytes, headline: str, subheadline: str = "") -> bytes:
    size = (1080, 1350)
    base = _open_cover(background_bytes, size).convert("RGBA")
    base = Image.alpha_composite(base, _gradient_overlay(size, 5, 220))
    draw = ImageDraw.Draw(base)
    margin = 72
    # small brand/category pill
    pill_font = _font(30, True)
    pill = "MARINA • VISA & TRAVEL"
    pb = draw.textbbox((0,0), pill, font=pill_font)
    pw, ph = pb[2]-pb[0] + 42, pb[3]-pb[1] + 24
    draw.rounded_rectangle((margin, 72, margin+pw, 72+ph), radius=22, fill=(255,255,255,222))
    draw.text((margin+21, 82), pill, font=pill_font, fill=(22,28,38,255))
    _logo(base, .17)

    headline = headline.upper().strip()
    hfont = _font(72, True)
    lines = _wrap(draw, headline, hfont, size[0]-2*margin, 3)
    line_h = 86
    y = size[1] - 325 - line_h * len(lines)
    for line in lines:
        draw.text((margin, y), line, font=hfont, fill=(255,255,255,255), stroke_width=1, stroke_fill=(0,0,0,80))
        y += line_h
    if subheadline:
        sfont = _font(36, False)
        sub_lines = _wrap(draw, subheadline, sfont, size[0]-2*margin, 2)
        y += 18
        for line in sub_lines:
            draw.text((margin, y), line, font=sfont, fill=(245,245,245,245))
            y += 50

    out = io.BytesIO()
    base.convert("RGB").save(out, "JPEG", quality=94, optimize=True)
    return out.getvalue()


def _card(text: str, size: tuple[int,int], background_bytes: bytes, index: int, total: int) -> bytes:
    base = _open_cover(background_bytes, size)
    # blur a little so text becomes primary, but keep destination recognizable
    base = base.filter(ImageFilter.GaussianBlur(radius=1.2)).convert("RGBA")
    dark = Image.new("RGBA", size, (7,12,20,150))
    base = Image.alpha_composite(base, dark)
    draw = ImageDraw.Draw(base)
    margin = int(size[0] * .075)
    _logo(base, .17)
    # progress marker
    fsmall = _font(28, True)
    draw.text((margin, int(size[1]*.075)), f"{index:02d}/{total:02d}", font=fsmall, fill=(255,255,255,205))
    f = _font(68 if size[1] < 1600 else 76, True)
    lines = _wrap(draw, text.upper(), f, size[0]-2*margin, 4)
    lh = int(getattr(f,"size",70)*1.18)
    y = int(size[1]*.52) - (len(lines)*lh)//2
    for line in lines:
        draw.text((margin,y), line, font=f, fill=(255,255,255,255))
        y += lh
    # thin accent rule (neutral white, no explicit brand color assumption)
    draw.rounded_rectangle((margin, y+24, margin+180, y+31), radius=4, fill=(255,255,255,210))
    out = io.BytesIO(); base.convert("RGB").save(out,"JPEG",quality=93,optimize=True); return out.getvalue()


def build_carousel(slides: Iterable[str], background_bytes: bytes | None = None) -> list[bytes]:
    items = list(slides)[:6]
    if not background_bytes:
        return []
    return [_card(t,(1080,1350),background_bytes,i+1,len(items)) for i,t in enumerate(items)]


def build_stories(slides: Iterable[str], background_bytes: bytes | None = None) -> list[bytes]:
    items = list(slides)[:5]
    if not background_bytes:
        return []
    return [_card(t,(1080,1920),background_bytes,i+1,len(items)) for i,t in enumerate(items)]


def build_reel_overlay(text: str, position: str = "middle") -> bytes:
    size=(1080,1920)
    canvas=Image.new("RGBA",size,(0,0,0,0)); draw=ImageDraw.Draw(canvas)
    font=_font(70,True)
    lines=_wrap(draw,text.upper(),font,900,3)
    lh=84; total=lh*len(lines)
    y={"top":300,"middle":(1920-total)//2,"bottom":1420}.get(position,700)
    # translucent rounded panel
    top=y-38; bottom=y+total+38
    draw.rounded_rectangle((65,top,1015,bottom),radius=34,fill=(7,12,20,155))
    for line in lines:
        box=draw.textbbox((0,0),line,font=font); tw=box[2]-box[0]
        draw.text(((1080-tw)//2,y),line,font=font,fill=(255,255,255,255))
        y+=lh
    _logo(canvas,.16)
    out=io.BytesIO(); canvas.save(out,"PNG"); return out.getvalue()


def save_social_assets(carousel: list[bytes], stories: list[bytes]) -> None:
    root=ROOT/"generated"; car=root/"carousels"; sto=root/"stories"; car.mkdir(parents=True,exist_ok=True); sto.mkdir(parents=True,exist_ok=True)
    for p in car.glob("*.jpg"): p.unlink()
    for p in sto.glob("*.jpg"): p.unlink()
    for i,d in enumerate(carousel,1): (car/f"slide_{i}.jpg").write_bytes(d)
    for i,d in enumerate(stories,1): (sto/f"story_{i}.jpg").write_bytes(d)
    print(f"[social] saved carousel={len(carousel)} stories={len(stories)}")
