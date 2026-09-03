import os
import random
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from social_assets import build_reel_overlay

ROOT = Path(__file__).resolve().parent
MUSIC_DIR = ROOT / "assets" / "music"


def _music_file() -> Optional[Path]:
    if not MUSIC_DIR.exists():
        return None
    files=[p for p in MUSIC_DIR.iterdir() if p.is_file() and p.suffix.lower() in {".mp3",".m4a",".wav",".aac"}]
    return random.choice(files) if files else None


def build_branded_reel(video_bytes: bytes, hook: str, middle: str, cta: str) -> Optional[bytes]:
    if not video_bytes or shutil.which("ffmpeg") is None:
        print("[reel] ffmpeg unavailable or empty source; using source video")
        return video_bytes or None
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        src=td/"source.mp4"; src.write_bytes(video_bytes)
        overlays=[(hook,"top",0.0,1.6),(middle,"middle",1.6,3.4),(cta,"bottom",3.4,5.2)]
        ov_paths=[]
        for i,(text,pos,_,_) in enumerate(overlays):
            p=td/f"ov{i}.png"; p.write_bytes(build_reel_overlay(text,pos)); ov_paths.append(p)
        out=td/"reel.mp4"
        cmd=["ffmpeg","-y","-i",str(src)]
        for p in ov_paths: cmd += ["-loop","1","-i",str(p)]
        music=_music_file()
        if music: cmd += ["-stream_loop","-1","-i",str(music)]
        # scale/crop, overlay timed PNG layers. Loop source slightly if shorter than 7 sec by tpad freeze.
        fc=(
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            "fps=24,tpad=stop_mode=clone:stop_duration=0.5[v0];"
            "[v0][1:v]overlay=0:0:enable='between(t,0,1.6)'[v1];"
            "[v1][2:v]overlay=0:0:enable='between(t,1.6,3.4)'[v2];"
            "[v2][3:v]overlay=0:0:enable='gte(t,3.4)'[vout]"
        )
        cmd += ["-filter_complex",fc,"-map","[vout]"]
        if music:
            # music is intentionally low, avoids abrupt ending
            mi=4
            cmd += ["-map",f"{mi}:a:0","-af","volume=0.16,afade=t=in:st=0:d=0.6,afade=t=out:st=4.4:d=0.5","-shortest"]
        else:
            # keep source audio if it exists; '?' makes mapping optional
            cmd += ["-map","0:a?","-shortest"]
        cmd += ["-t","5.0","-c:v","libx264","-preset","medium","-crf","20","-pix_fmt","yuv420p","-movflags","+faststart","-c:a","aac","-b:a","160k",str(out)]
        try:
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
            if p.returncode != 0 or not out.exists():
                print("[reel] ffmpeg failed:", p.stderr[-1200:])
                return video_bytes
            print(f"[reel] branded reel ready: {out.stat().st_size} bytes, music={'yes' if music else 'no'}")
            return out.read_bytes()
        except Exception as exc:
            print(f"[reel] build failed: {exc}")
            return video_bytes
