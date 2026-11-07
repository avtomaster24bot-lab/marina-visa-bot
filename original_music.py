"""Original procedural instrumental for local reels.

The audio is synthesized at runtime from sine tones. It does not download
samples, call paid APIs, or embed third-party recordings.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path


def write_procedural_music(path: Path, duration: float = 20.0, sample_rate: int = 22050) -> Path:
    """Write a short original pad-and-pulse instrumental as 16-bit mono WAV."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n_samples = max(1, int(duration * sample_rate))
    chord_a = (130.81, 155.56, 196.00)  # C3, Eb3, G3
    chord_b = (146.83, 174.61, 220.00)  # D3, F3, A3

    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            t = i / sample_rate
            blend = 0.5 + 0.5 * math.sin(2 * math.pi * t / 8.0)
            sample = 0.0
            for freq in chord_a:
                sample += math.sin(2 * math.pi * freq * t) * (1.0 - blend)
            for freq in chord_b:
                sample += math.sin(2 * math.pi * freq * t) * blend
            sample /= 3.0
            tremolo = 0.85 + 0.15 * math.sin(2 * math.pi * 0.35 * t)
            pulse = 0.10 * math.sin(2 * math.pi * 2.0 * t) * math.sin(2 * math.pi * 329.63 * t)
            fade = min(1.0, t / 0.45, max(0.0, (duration - t) / 0.55))
            value = sample * 0.20 * tremolo + pulse
            clipped = max(-1.0, min(1.0, value * fade))
            frames += struct.pack("<h", int(clipped * 32767))
        wf.writeframes(frames)
    return path
