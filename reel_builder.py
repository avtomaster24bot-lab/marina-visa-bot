Нужны референсы стиimport random
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent
MUSIC_DIR = ROOT / "assets" / "music"


def _music_file() -> Optional[Path]:
    if not MUSIC_DIR.exists():
        return None
    files = [
        p for p in MUSIC_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in {".mp3", ".m4a", ".wav", ".aac"}
    ]
    return random.choice(files) if files else None


def build_branded_reel(
    story_frames: list[bytes],
    source_video: bytes | None = None,
) -> Optional[bytes]:
    """
    Quality-first Reel builder.

    The published Reel is built from the already branded 9:16 Story frames.
    This guarantees:
      - Russian text is always visible and correct;
      - the Reel matches the same campaign as the post/carousel;
      - no dependence on Agnes generating readable text;
      - no silent fallback to a meaningless raw AI clip.

    Agnes source video, when available, is preserved separately by smart_poster.py
    as optional B-roll for later review, but it is not allowed to replace the
    coherent branded Reel.
    """
    if not story_frames:
        print("[reel] no Story frames; cannot build branded Reel")
        return None

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("[reel] ffmpeg unavailable; branded Reel cannot be built")
        return None

    frames = story_frames[:4]
    if len(frames) < 2:
        print("[reel] at least 2 Story frames are required")
        return None

    with tempfile.TemporaryDirectory() as td_raw:
        td = Path(td_raw)
        image_paths: list[Path] = []
        for i, raw in enumerate(frames):
            p = td / f"frame_{i}.jpg"
            p.write_bytes(raw)
            image_paths.append(p)

        out = td / "reel.mp4"
        seconds_per_slide = 1.55
        fps = 24
        frames_per_slide = int(seconds_per_slide * fps)

        cmd = [ffmpeg, "-y"]
        for p in image_paths:
            cmd += ["-loop", "1", "-t", str(seconds_per_slide), "-i", str(p)]

        music = _music_file()
        if music:
            cmd += ["-stream_loop", "-1", "-i", str(music)]

        filters = []
        labels = []
        for i in range(len(image_paths)):
            # Very subtle zoom creates motion without making the text unreadable.
            filters.append(
                f"[{i}:v]"
                "scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,"
                f"zoompan=z='min(zoom+0.00055,1.035)':d={frames_per_slide}:"
                "s=1080x1920:fps=24,setsar=1,format=yuv420p"
                f"[v{i}]"
            )
            labels.append(f"[v{i}]")

        filters.append(
            "".join(labels)
            + f"concat=n={len(image_paths)}:v=1:a=0[outv]"
        )

        cmd += [
            "-filter_complex", ";".join(filters),
            "-map", "[outv]",
        ]

        total_duration = seconds_per_slide * len(image_paths)
        if music:
            music_index = len(image_paths)
            cmd += [
                "-map", f"{music_index}:a:0",
                "-af", f"volume=0.16,afade=t=in:st=0:d=0.45,afade=t=out:st={max(0.5,total_duration-0.7):.2f}:d=0.6",
                "-shortest",
                "-c:a", "aac", "-b:a", "160k",
            ]

        cmd += [
            "-t", f"{total_duration:.2f}",
            "-r", "24",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "19",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(out),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        except Exception as exc:
            print(f"[reel] ffmpeg execution failed: {exc}")
            return None

        if result.returncode != 0 or not out.exists():
            print("[reel] ffmpeg failed; stderr follows:")
            print(result.stderr[-3000:])
            return None

        reel = out.read_bytes()
        if len(reel) < 40_000:
            print(f"[reel] output suspiciously small: {len(reel)} bytes")
            return None

        print(
            f"[reel] branded motion Reel ready: {len(reel)} bytes; "
            f"slides={len(image_paths)}; music={'yes' if music else 'no'}"
        )
        return reel
ля рисовки (если рисованный стиль) и персонажей
