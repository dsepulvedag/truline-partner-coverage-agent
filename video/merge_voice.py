"""Merge the karaoke voice-over takes into the demo video.

    uv run --python 3.11 --with imageio-ffmpeg python video/merge_voice.py [takes folder]

Takes are the per-shot files from karaoke.html (voice_01_title.webm, voice_02_plan.webm, ...), looked up in
video/out/ (or the folder given; ~/Downloads works too). Each take is trimmed to its shot and placed at the shot's
start time from timeline.json. Missing shots stay silent. Writes video/out/demo_with_voice.mp4.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg

OUT = Path(__file__).resolve().parent / "out"
src = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else OUT
shots = json.loads((OUT / "timeline.json").read_text())["shots"]

takes = {}
for f in sorted(src.glob("voice_*.webm"), key=lambda p: p.stat().st_mtime):  # newest download of a shot wins
    m = re.match(r"voice_(\d+)_", f.name)
    if m:
        takes[int(m.group(1)) - 1] = f
if not takes:
    sys.exit(f"No voice_NN_*.webm takes found in {src}")

cmd, parts = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(OUT / "demo.mp4")], []
for n, (i, f) in enumerate(sorted(takes.items()), start=1):
    s = shots[i]
    cmd += ["-i", str(f)]
    ms = int(s["start"] * 1000)
    parts.append(f"[{n}:a]atrim=0:{s['seconds']},asetpts=PTS-STARTPTS,adelay={ms}|{ms}[a{n}]")
    print(f"shot {i + 1} ({s['id']}): {f.name} at {s['start']}s")
mix = "".join(f"[a{n}]" for n in range(1, len(takes) + 1))
graph = ";".join(parts) + f";{mix}amix=inputs={len(takes)}:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[aout]"
dst = OUT / "demo_with_voice.mp4"
cmd += ["-filter_complex", graph, "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
        "-t", str(sum(s["seconds"] for s in shots)), str(dst)]
subprocess.run(cmd, check=True)
missing = [s["id"] for i, s in enumerate(shots) if i not in takes]
print("wrote", dst, "| silent shots:", ", ".join(missing) or "none")
