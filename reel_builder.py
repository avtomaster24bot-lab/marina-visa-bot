import random
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent
MUSIC_DIR = ROOT / "assets" / "music"


def _music_file() -> Optional[Path]:
    """
    Find a usable music file anywhere inside assets/music.
    """
    if not MUSIC_DIR.exists():
        print(f"[reel] music directory not found: {MUSIC_DIR}")
        return None

    extensions = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac"}

    files = [
        p
        for p in MUSIC_DIR.rglob("*")
        if p.is_file() and p.suffix.lower() in extensions
    ]

    print(f"[reel] found {len(files)} music file(s)")

    if not files:
        return None

    music = random.choice(files)
    print(f"[reel] selected music: {music}")
    return music


def _has_audio_stream(path: Path) -> bool:
    """
    Check that the final MP4 really contains an audio stream.
    """
    ffprobe = shutil.which("ffprobe")

    if not ffprobe:
        print("[reel] ffprobe not found; cannot verify audio stream")
        return False

    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        codec = result.stdout.strip()

        if codec:
            print(f"[reel] audio stream confirmed: {codec}")
            return True

        print("[reel] no audio stream found in final MP4")
        return False

    except Exception as exc:
        print(f"[reel] ffprobe failed: {exc}")
        return False


def build_branded_reel(
    story_frames: list[bytes],
    source_video: bytes | None = None,
) -> Optional[bytes]:

    if not story_frames:
        print("[reel] no Story frames; cannot build branded Reel")
        return None

    ffmpeg = shutil.which("ffmpeg")

    if not ffmpeg:
        print("[reel] ffmpeg unavailable")
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

        # ОСТАВЛЯЕМ ПРЕЖНЮЮ ДЛИТЕЛЬНОСТЬ
        seconds_per_slide = 1.55
        fps = 24
        frames_per_slide = int(seconds_per_slide * fps)

        total_duration = seconds_per_slide * len(image_paths)

        cmd = [ffmpeg, "-y"]

        for p in image_paths:
            cmd += [
                "-loop",
                "1",
                "-t",
                str(seconds_per_slide),
                "-i",
                str(p),
            ]

        music = _music_file()

        if music:
            cmd += [
                "-stream_loop",
                "-1",
                "-i",
                str(music),
            ]

        filters = []
        labels = []

        for i in range(len(image_paths)):
            filters.append(
                f"[{i}:v]"
                "scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,"
                f"zoompan=z='min(zoom+0.00055,1.035)':"
                f"d={frames_per_slide}:"
                "s=1080x1920:"
                "fps=24,"
                "setsar=1,"
                "format=yuv420p"
                f"[v{i}]"
            )

            labels.append(f"[v{i}]")

        filters.append(
            "".join(labels)
            + f"concat=n={len(image_paths)}:v=1:a=0[outv]"
        )

        cmd += [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
        ]

        if music:
            music_index = len(image_paths)

            cmd += [
                "-map",
                f"{music_index}:a:0",
                "-af",
                (
                    "volume=0.24,"
                    "afade=t=in:st=0:d=0.35,"
                    f"afade=t=out:st={max(0.5, total_duration - 0.5):.2f}:d=0.45"
                ),
                "-c:a",
                "aac",
                "-b:a",
                "192k",
            ]

        cmd += [
            "-t",
            f"{total_duration:.2f}",
            "-r",
            "24",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "19",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out),
        ]

        print(
            f"[reel] building Reel: "
            f"{total_duration:.2f}s "
            f"music={'yes' if music else 'no'}"
        )

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=240,
            )

        except Exception as exc:
            print(f"[reel] ffmpeg execution failed: {exc}")
            return None

        if result.returncode != 0 or not out.exists():
            print("[reel] ffmpeg failed:")
            print(result.stderr[-4000:])
            return None

        if music:
            _has_audio_stream(out)

        reel = out.read_bytes()

        if len(reel) < 40_000:
            print(
                f"[reel] output suspiciously small: "
                f"{len(reel)} bytes"
            )
            return None

        print(
            f"[reel] Reel ready: "
            f"{len(reel)} bytes; "
            f"slides={len(image_paths)}; "
            f"music={'yes' if music else 'no'}"
        )

        return reel
