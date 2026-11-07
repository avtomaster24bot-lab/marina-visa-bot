import io
import json
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageStat

from reel_builder import build_branded_reel

SAMPLE_TIMES = (2, 6, 10, 14, 18)


def _extract_frame(video: Path, second: int, dest: Path) -> Path:
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(second), "-i", str(video), "-frames:v", "1", "-q:v", "2", str(dest)],
        check=True,
        capture_output=True,
    )
    return dest


def _mean_abs_diff(a: Path, b: Path) -> float:
    left = Image.open(a).convert("RGB")
    right = Image.open(b).convert("RGB")
    stats = ImageStat.Stat(ImageChops.difference(left, right))
    return sum(stats.mean) / max(1, len(stats.mean))


def _audio_rms(video: Path) -> tuple[float, float, float]:
    wav_path = video.with_suffix(".probe.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "22050", str(wav_path)],
        check=True,
        capture_output=True,
    )
    with wave.open(str(wav_path), "rb") as wf:
        raw = wf.readframes(wf.getnframes())
        sample_rate = wf.getframerate()
    samples = []
    peak = 0
    total = 0.0
    for i in range(0, len(raw) - 1, 2):
        value = int.from_bytes(raw[i:i + 2], "little", signed=True)
        samples.append(value)
        peak = max(peak, abs(value))
        total += float(value) * float(value)
    rms = (total / max(1, len(samples))) ** 0.5
    duration = len(samples) / sample_rate
    return rms, float(peak), duration


class ReelSceneChangeTests(unittest.TestCase):
    def test_sampled_frames_change_semantically(self):
        colors = [
            (200, 30, 30),
            (30, 180, 40),
            (30, 60, 200),
            (220, 200, 30),
            (180, 40, 180),
        ]
        labels = ["SCENE-A1", "SCENE-B2", "SCENE-C3", "SCENE-D4", "SCENE-E5"]
        frames = []
        for color, label in zip(colors, labels):
            image = Image.new("RGB", (1080, 1920), color)
            draw = ImageDraw.Draw(image)
            draw.rectangle((80, 760, 1000, 1160), fill=(255, 255, 255))
            draw.text((140, 900), label, fill=(0, 0, 0))
            buf = io.BytesIO()
            image.save(buf, "JPEG", quality=92)
            frames.append(buf.getvalue())

        reel = build_branded_reel(frames, source_video=None, duration=20.0)
        self.assertIsNotNone(reel)
        self.assertGreater(len(reel), 40_000)

        with tempfile.TemporaryDirectory() as raw:
            video = Path(raw) / "reel.mp4"
            video.write_bytes(reel)
            probe = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration:stream=codec_type,codec_name,width,height",
                    "-of", "json",
                    str(video),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            info = json.loads(probe.stdout)
            duration = float(info["format"]["duration"])
            self.assertGreaterEqual(duration, 15)
            self.assertLessEqual(duration, 25)
            kinds = {stream.get("codec_type") for stream in info["streams"]}
            self.assertIn("audio", kinds)
            self.assertIn("video", kinds)

            extracted = []
            for second in SAMPLE_TIMES:
                extracted.append(_extract_frame(video, second, Path(raw) / f"t{second}.jpg"))

            for i in range(len(extracted) - 1):
                mae = _mean_abs_diff(extracted[i], extracted[i + 1])
                self.assertGreater(
                    mae,
                    12.0,
                    f"frames at {SAMPLE_TIMES[i]}s and {SAMPLE_TIMES[i + 1]}s look the same (mae={mae:.2f})",
                )

            rms, peak, audio_duration = _audio_rms(video)
            self.assertGreater(rms, 100.0, f"audio too quiet or silent: rms={rms}")
            self.assertGreater(peak, 500.0)
            self.assertGreater(audio_duration, 14.0)


if __name__ == "__main__":
    unittest.main()
