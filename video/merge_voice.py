"""Merge the karaoke voice-over into the demo video.

    uv run --python 3.11 --with imageio-ffmpeg python video/merge_voice.py [voice file]

Reads video/out/demo.mp4 and video/out/voice.webm (or the file given), writes video/out/demo_with_voice.mp4.
"""
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg

OUT = Path(__file__).resolve().parent / "out"
voice = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / "voice.webm"
dst = OUT / "demo_with_voice.mp4"
subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(OUT / "demo.mp4"), "-i", str(voice),
                "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-shortest", str(dst)], check=True)
print("wrote", dst)
