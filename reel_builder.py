import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from original_music import write_procedural_music

MIN_REEL_SECONDS = 15.0
MAX_REEL_SECONDS = 25.0
DEFAULT_REEL_SECONDS = 20.0


def _clamp_duration(duration: float) -> float:
    try:
        value = float(duration)
    except (TypeError, ValueError):
        value = DEFAULT_REEL_SECONDS
    return max(MIN_REEL_SECONDS, min(MAX_REEL_SECONDS, value))


def _has_audio_stream(path: Path) -> bool:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        print("[reel] ffprobe not found; cannot verify audio stream")
        return False
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_name",
                "-of", "default=noprint_wrappers=1:nokey=1",
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


def _resolve_music(td: Path, total_duration: float) -> Path:
    """Always synthesize an original procedural instrumental.

    Bundled files in assets/music/ are not selected. No license confirmation
    was documented for those MP3s, so this stage does not implement an opt-in.
    """
    generated = td / "original_procedural_music.wav"
    write_procedural_music(generated, duration=total_duration)
    print(f"[reel] using original procedural music: {generated}")
    return generated


def build_branded_reel(
    story_frames: list[bytes],
    source_video: bytes | None = None,
    duration: float = DEFAULT_REEL_SECONDS,
) -> Optional[bytes]:
    """Build a 15-25s local motion reel with titles already in the frames and music.

    source_video is accepted for compatibility but is not composited. The previous
    paid B-roll path never appeared in the finished file, so it is ignored here.
    """
    if source_video:
        print("[reel] ignoring unused source video; paid B-roll is not composited")

    if not story_frames:
        print("[reel] no Story frames; cannot build branded Reel")
        return None

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("[reel] ffmpeg unavailable")
        return None

    frames = list(story_frames[:5])
    if len(frames) < 2:
        print("[reel] at least 2 Story frames are required")
        return None

    total_duration = _clamp_duration(duration)
    seconds_per_slide = total_duration / len(frames)
    fps = 24
    frames_per_slide = max(1, int(round(seconds_per_slide * fps)))

    with tempfile.TemporaryDirectory() as td_raw:
        td = Path(td_raw)
        image_paths: list[Path] = []
        for i, raw in enumerate(frames):
            p = td / f"frame_{i}.jpg"
            p.write_bytes(raw)
            image_paths.append(p)

        out = td / "reel.mp4"
        cmd = [ffmpeg, "-y"]
        for p in image_paths:
            cmd += ["-loop", "1", "-t", f"{seconds_per_slide:.3f}", "-i", str(p)]

        music = _resolve_music(td, total_duration)
        cmd += ["-stream_loop", "-1", "-i", str(music)]

        filters = []
        labels = []
        for i in range(len(image_paths)):
            filters.append(
                f"[{i}:v]"
                "scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,"
                f"zoompan=z='min(zoom+0.00045,1.04)':"
                f"d={frames_per_slide}:"
                "s=1080x1920:"
                "fps=24,"
                "setsar=1,"
                "format=yuv420p"
                f"[v{i}]"
            )
            labels.append(f"[v{i}]")
        filters.append("".join(labels) + f"concat=n={len(image_paths)}:v=1:a=0[outv]")

        music_index = len(image_paths)
        fade_out_start = max(0.5, total_duration - 0.55)
        cmd += [
            "-filter_complex", ";".join(filters),
            "-map", "[outv]",
            "-map", f"{music_index}:a:0",
            "-af", (
                "volume=0.26,"
                "afade=t=in:st=0:d=0.4,"
                f"afade=t=out:st={fade_out_start:.2f}:d=0.5"
            ),
            "-c:a", "aac",
            "-b:a", "192k",
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

        print(
            f"[reel] building Reel: {total_duration:.2f}s "
            f"slides={len(image_paths)} music=procedural"
        )
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        except Exception as exc:
            print(f"[reel] ffmpeg execution failed: {exc}")
            return None

        if result.returncode != 0 or not out.exists():
            print("[reel] ffmpeg failed:")
            print(result.stderr[-4000:])
            return None

        if not _has_audio_stream(out):
            print("[reel] retrying procedural music after silent mux")
            fallback_music = td / "fallback_procedural.wav"
            write_procedural_music(fallback_music, duration=total_duration)
            retry = list(cmd)
            try:
                music_pos = retry.index(str(music))
                retry[music_pos] = str(fallback_music)
            except ValueError:
                retry = cmd
            retry_result = subprocess.run(retry, capture_output=True, text=True, timeout=240)
            if retry_result.returncode != 0 or not out.exists():
                print("[reel] procedural music retry failed:")
                print(retry_result.stderr[-2000:])
                return None

        reel = out.read_bytes()
        if len(reel) < 40_000:
            print(f"[reel] output suspiciously small: {len(reel)} bytes")
            return None

        print(
            f"[reel] Reel ready: {len(reel)} bytes; "
            f"slides={len(image_paths)}; duration={total_duration:.2f}s"
        )
        return reel
