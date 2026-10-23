"""Record the 57-second demo video with Playwright and assemble it with ffmpeg.

    uv run --python 3.11 --with playwright --with imageio-ffmpeg python video/record_demo.py login
    uv run --python 3.11 --with playwright --with imageio-ffmpeg python video/record_demo.py record

`login` opens a real browser window: sign in to Snowsight yourself (the script never touches credentials).
The session is kept in a profile outside the repo (~/.truline_recorder_profile). `record` reuses it, records
each shot as its own clip, trims the loading time, and writes video/out/demo.mp4 + video/out/timeline.json.
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
CLIPS = OUT / "clips"
PROFILE = Path.home() / ".truline_recorder_profile"
APP = "https://app.snowflake.com/us-west-2/zvb07385/#/streamlit-apps/TRULINE.APP.COVERAGE_WORKBENCH"
SIZE = {"width": 1280, "height": 720}
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

SCRIPT = json.loads((HERE / "voiceover.json").read_text())


def app_frame(page, text, timeout=180):
    """The Streamlit app runs in an iframe; return the frame that shows `text`."""
    end = time.time() + timeout
    while time.time() < end:
        for f in page.frames:
            try:
                if f.get_by_text(text, exact=False).first.is_visible(timeout=200):
                    return f
            except Exception:  # noqa: BLE001 - frames come and go while Snowsight loads
                pass
        time.sleep(0.5)
    raise TimeoutError(f"'{text}' never appeared")


def wheel(page, dy, steps=6, pause=0.12):
    page.mouse.move(800, 420)
    for _ in range(steps):
        page.mouse.wheel(0, dy / steps)
        time.sleep(pause)


def shot(ctx, name, url, ready_text, actions):
    """Open a page, wait until `ready_text` is visible (+ settle), run actions; return (video, ready_offset)."""
    page = ctx.new_page()
    t0 = time.time()
    page.goto(url)
    frame = app_frame(page, ready_text) if ready_text else None
    if frame is not None and frame.locator('[data-testid="stDialog"]').count():
        page.keyboard.press("Escape")
    time.sleep(3 if ready_text else 0.3)
    ready = time.time() - t0
    mark = actions(page, frame)
    page.close()
    start = (mark - t0) if mark else ready
    print(f"recorded {name}: trimmed from {start:.1f}s")
    return page.video, start


def login():
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(PROFILE), headless=False, viewport=SIZE)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(APP)
        print("Sign in to Snowsight in the browser window. Waiting up to 10 minutes for the app to load…")
        app_frame(page, "Weekly delegation plan", timeout=600)
        print("Signed in; the session is saved in", PROFILE)
        ctx.close()


def record():
    if CLIPS.exists():
        shutil.rmtree(CLIPS)
    CLIPS.mkdir(parents=True)
    hold = {s["id"]: s["seconds"] for s in SCRIPT["shots"]}
    takes = []  # (shot id, video, ready offset, seconds)
    with sync_playwright() as p:
        # Cards: plain local pages.
        browser = p.chromium.launch()
        cards = browser.new_context(viewport=SIZE, record_video_dir=str(CLIPS), record_video_size=SIZE)

        def card(sid, file):
            page = cards.new_page()
            page.goto((HERE / "cards" / file).as_uri())
            time.sleep(hold[sid] + 0.6)
            page.close()
            takes.append((sid, page.video, 0.4, hold[sid]))

        card("title", "title.html")
        card("personas", "personas.html")
        card("close", "close.html")
        cards.close()
        browser.close()

        # App shots: the signed-in profile.
        ctx = p.chromium.launch_persistent_context(str(PROFILE), headless=False, viewport=SIZE,
                                                   record_video_dir=str(CLIPS), record_video_size=SIZE)
        for pg in ctx.pages:
            pg.close()

        def plan(page, f):  # shots 2 + 3 (15 s)
            time.sleep(3.5)                       # nav + identity badge + KPIs
            wheel(page, 500)                      # plan summary with citations
            time.sleep(2.5)
            f.get_by_text("Show", exact=True).first.scroll_into_view_if_needed()
            time.sleep(1.5)
            labels = f.locator('[data-testid="stCheckbox"] label')
            labels.nth(0).scroll_into_view_if_needed()
            time.sleep(1.0)
            labels.nth(0).click()
            time.sleep(0.6)
            labels.nth(1).click()
            time.sleep(0.6)
            f.get_by_role("button", name="Approve ticked plays").click(force=True)
            time.sleep(4.0)                       # toast

        v, r = shot(ctx, "plan", APP, "Run this week's plan", plan)
        takes.append(("plan", v, r, hold["plan"]))

        def brief(page, f):  # shot 4 (7 s)
            f.get_by_text("Internal strategic brief").first.scroll_into_view_if_needed()
            time.sleep(2.5)
            wheel(page, 450)
            time.sleep(1.5)
            f.get_by_text("Evidence").first.click(force=True)
            time.sleep(2.5)

        v, r = shot(ctx, "brief", APP + "/!/account_brief", "Internal strategic brief", brief)
        takes.append(("brief", v, r, hold["brief"]))

        def why(page, f):  # shot 5 (6 s)
            f.get_by_text("Signal:").first.scroll_into_view_if_needed()
            time.sleep(2.5)
            wheel(page, 350)
            time.sleep(3.0)

        v, r = shot(ctx, "why", APP + "/!/account_brief", "Signal:", why)
        takes.append(("why", v, r, hold["why"]))

        def tail(page, f):  # shot 6 (5 s)
            time.sleep(1.5)
            f.get_by_text("Claim check").first.scroll_into_view_if_needed()
            time.sleep(1.5)
            wheel(page, 300)
            time.sleep(1.5)

        v, r = shot(ctx, "tail", APP + "/!/long_tail", "Long-tail partners", tail)
        takes.append(("tail", v, r, hold["tail"]))

        def audit(page, f):  # second half of shot 7 (5 s): click, then the block lands ~1.5 s in
            f.get_by_role("button", name="Inject and re-check").click(force=True)
            f.get_by_text("Blocked").first.wait_for(timeout=60000)
            shown = time.time()
            time.sleep(4.0)
            return shown - 1.5

        v, r = shot(ctx, "audit", APP + "/!/audit", "Catch a made-up number", audit)
        takes.append(("audit", v, r, hold["audit"]))
        ctx.close()
        takes = [(sid, vid.path(), start, secs) for sid, vid, start, secs in takes]  # resolve while Playwright runs

    # Assemble in script order: trim each clip from its ready point for its planned length.
    order = [s["id"] for s in SCRIPT["shots"]]
    by_id = {t[0]: t for t in takes}
    parts = []
    for i, sid in enumerate(order):
        _, video, start, secs = by_id[sid]
        src, dst = video, CLIPS / f"{i:02d}_{sid}.mp4"
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-i", src, "-t", str(secs),
                        "-vf", "scale=1280:720,fps=30", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(dst)], check=True)
        parts.append(dst)
    (CLIPS / "list.txt").write_text("".join(f"file '{x.name}'\n" for x in parts))
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(CLIPS / "list.txt"),
                    "-c", "copy", str(OUT / "demo.mp4")], check=True)
    t, timeline = 0.0, []
    for s in SCRIPT["shots"]:
        timeline.append({**s, "start": round(t, 2), "end": round(t + s["seconds"], 2)})
        t += s["seconds"]
    (OUT / "timeline.json").write_text(json.dumps({"duration": t, "shots": timeline}, indent=1))
    shutil.copy(HERE / "karaoke.html", OUT / "karaoke.html")
    print(f"wrote {OUT / 'demo.mp4'} ({t:.0f} s) and timeline.json")


def redo_audit():
    """Re-record only the audit clip and rebuild demo.mp4 from the clips already on disk."""
    secs = {s["id"]: s["seconds"] for s in SCRIPT["shots"]}["audit"]
    i = [s["id"] for s in SCRIPT["shots"]].index("audit")
    tmp = OUT / "redo"
    shutil.rmtree(tmp, ignore_errors=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(PROFILE), headless=False, viewport=SIZE,
                                                   record_video_dir=str(tmp), record_video_size=SIZE)
        for pg in ctx.pages:
            pg.close()

        def audit(page, f):
            f.get_by_role("button", name="Inject and re-check").click(force=True)
            f.get_by_text("Blocked").first.wait_for(timeout=60000)
            shown = time.time()
            time.sleep(4.0)
            return shown - 1.5

        v, start = shot(ctx, "audit", APP + "/!/audit", "Catch a made-up number", audit)
        ctx.close()
        src = v.path()
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-i", src, "-t", str(secs),
                    "-vf", "scale=1280:720,fps=30", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
                    str(CLIPS / f"{i:02d}_audit.mp4")], check=True)
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(CLIPS / "list.txt"),
                    "-c", "copy", str(OUT / "demo.mp4")], check=True)
    print("rebuilt", OUT / "demo.mp4")


if __name__ == "__main__":
    {"login": login, "record": record, "redo-audit": redo_audit}[sys.argv[1]]()
