import os
import random
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent
CLIENT_IMAGES = ROOT / "assets" / "client" / "images"
CLIENT_VIDEOS = ROOT / "assets" / "client" / "videos"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm"}


def _probability(name: str, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(os.getenv(name, str(default)))))
    except ValueError:
        return default


def _files(folder: Path, extensions: set[str]) -> list[Path]:
    if not folder.exists():
        return []
    return [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in extensions]


def choose_client_image() -> Optional[bytes]:
    items = _files(CLIENT_IMAGES, IMAGE_EXTS)
    if not items or random.random() >= _probability("CLIENT_IMAGE_PROBABILITY", 0.35):
        return None
    chosen = random.choice(items)
    print(f"[media] client image selected: {chosen.name}")
    return chosen.read_bytes()


def choose_client_video() -> Optional[bytes]:
    items = _files(CLIENT_VIDEOS, VIDEO_EXTS)
    if not items or random.random() >= _probability("CLIENT_VIDEO_PROBABILITY", 0.30):
        return None
    chosen = random.choice(items)
    print(f"[media] client video selected: {chosen.name}")
    return chosen.read_bytes()
