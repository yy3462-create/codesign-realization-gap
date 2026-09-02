#!/usr/bin/env python3
"""Render gallery thumbnails (rest pose, transparent background) for every GLB in models/.

  pip install playwright pillow && playwright install chromium      # once
  python render_thumbs.py                    # writes ../figs/thumbs/<stem>.webp for all 36 GLBs
  python render_thumbs.py --only quadruped_fab g0_222222_0_abs --size 1200x800 --out /tmp/x

Uses tools/thumb.html (the vendored three.js) inside headless Chromium, so the thumbnails match the
viewer's lighting and materials. Software WebGL is enabled so it also works on machines without a GPU.
"""
import argparse, functools, http.server, io, os, socketserver, threading, time

from PIL import Image
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.abspath(os.path.join(HERE, ".."))


def serve(root, port):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
    handler.log_message = lambda *a, **k: None
    class S(socketserver.TCPServer):
        allow_reuse_address = True
    srv = S(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def fit(im, fw, fh, margin):
    """Scale the cropped render to fill (1 - 2*margin) of a fw x fh transparent canvas, centred."""
    sx = fw * (1 - 2 * margin) / im.width
    sy = fh * (1 - 2 * margin) / im.height
    s = min(sx, sy)
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    out = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
    out.alpha_composite(im, ((fw - im.width) // 2, (fh - im.height) // 2))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--only", nargs="*", help="GLB stems (default: all in models/)")
    p.add_argument("--out", default=os.path.join(SITE, "figs", "thumbs"))
    p.add_argument("--size", default="1000x750", help="render canvas in CSS pixels (rendered at --dpr)")
    p.add_argument("--final", default="640x480", help="output size; the render is cropped to its content and fitted")
    p.add_argument("--margin", type=float, default=0.07, help="empty margin around the content, fraction of the output")
    p.add_argument("--dpr", type=float, default=1.6)
    p.add_argument("--az", type=float, default=35.0)
    p.add_argument("--el", type=float, default=22.0)
    p.add_argument("--fov", type=float, default=28.0)
    p.add_argument("--pad", type=float, default=1.12)
    p.add_argument("--pose", default="", help="clip@seconds, e.g. flat@4.0 (default: rest pose)")
    p.add_argument("--quality", type=int, default=82)
    p.add_argument("--png", action="store_true", help="also keep the PNG")
    p.add_argument("--port", type=int, default=8765)
    a = p.parse_args()
    w, h = [int(x) for x in a.size.split("x")]
    fw, fh = [int(x) for x in a.final.split("x")]
    os.makedirs(a.out, exist_ok=True)
    stems = a.only or sorted(f[:-4] for f in os.listdir(os.path.join(SITE, "models")) if f.endswith(".glb"))

    srv = serve(SITE, a.port)
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=a.dpr)
        pg = ctx.new_page()
        for stem in stems:
            url = (f"http://127.0.0.1:{a.port}/tools/thumb.html?glb=../models/{stem}.glb&w={w}&h={h}"
                   f"&az={a.az}&el={a.el}&fov={a.fov}&pad={a.pad}&dpr={a.dpr}" + (f"&t={a.pose}" if a.pose else ""))
            pg.goto(url)
            for _ in range(600):
                if pg.evaluate("window.__done === true || !!window.__error"):
                    break
                time.sleep(0.05)
            err = pg.evaluate("window.__error || null")
            if err:
                print(f"{stem}: ERROR {err}"); continue
            png = pg.screenshot(omit_background=True, clip={"x": 0, "y": 0, "width": w, "height": h})
            im = Image.open(io.BytesIO(png)).convert("RGBA")
            bbox = im.getbbox()
            im = fit(im.crop(bbox), fw, fh, a.margin) if bbox else im.resize((fw, fh))
            im.save(os.path.join(a.out, stem + ".webp"), "WEBP", quality=a.quality, method=6)
            if a.png:
                im.save(os.path.join(a.out, stem + ".png"))
            print(f"{stem}: {im.size[0]}x{im.size[1]}, content bbox {bbox}, "
                  f"{os.path.getsize(os.path.join(a.out, stem + '.webp'))/1e3:.0f} kB")
        b.close()
    srv.shutdown()


if __name__ == "__main__":
    main()
