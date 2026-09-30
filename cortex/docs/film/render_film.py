"""Render xray-film.html frame by frame to a 1080p MP4 (deterministic: window.renderAt(t) per frame).

Usage: python docs/film/render_film.py [--out app/static/xray-film.mp4] [--fps 30] [--stills 5,30,60]
Needs: playwright (local Chromium), imageio-ffmpeg, and three.module.js next to the HTML
(npm i three@0.170.0, then copy node_modules/three/build/three.module.js here).
"""
import argparse
import functools
import glob
import http.server
import subprocess
import threading
import time
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent


def serve():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(HERE))
    h.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE.parent.parent / "app" / "static" / "xray-film.mp4"))
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--stills", default="", help="comma-separated seconds: save PNG previews instead of a video")
    ap.add_argument("--end", type=float, default=0, help="stop early (seconds), for tests")
    a = ap.parse_args()
    port = serve()
    exe = (glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome") or [None])[0]
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe, args=["--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        pg.on("console", lambda m: m.type == "error" and print("console:", m.text))
        pg.on("pageerror", lambda e: print("pageerror:", e))
        pg.goto(f"http://127.0.0.1:{port}/xray-film.html")
        pg.wait_for_function("window.ready === true", timeout=120000)
        if a.stills:
            for s in a.stills.split(","):
                pg.evaluate(f"renderAt({float(s)})")
                pg.screenshot(path=str(HERE / f"still_{float(s):05.1f}.png"))
            return
        dur = a.end or pg.evaluate("DUR")
        n = int(dur * a.fps)
        ff = subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(a.fps),
                               "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p",
                               "-movflags", "+faststart", a.out], stdin=subprocess.PIPE)
        t0 = time.time()
        for i in range(n):
            pg.evaluate(f"renderAt({i / a.fps})")
            ff.stdin.write(pg.screenshot(type="jpeg", quality=94))
            if i % 150 == 0:
                print(f"frame {i}/{n} · {time.time() - t0:.0f}s", flush=True)
        ff.stdin.close(); ff.wait()
        print("wrote", a.out)


if __name__ == "__main__":
    main()
