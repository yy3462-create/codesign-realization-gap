#!/usr/bin/env python3
"""Single-file preview of the site with a few morphologies embedded as data URIs
(for the claude.ai artifact preview; the real site keeps the files separate).

  python build_preview.py --morphs quadruped g0_222222_0 g0_444_0 --out /tmp/preview.html
"""
import argparse, base64, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "..")
THREE = "https://cdn.jsdelivr.net/npm/three@0.160.1/"

def b64(path, mime):
    return f"data:{mime};base64," + base64.b64encode(open(path, "rb").read()).decode()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--morphs", nargs="+", default=["quadruped", "g0_222222_0", "g0_444_0"])
    p.add_argument("--out", default="/tmp/preview.html")
    a = p.parse_args()

    html = open(os.path.join(SITE, "index.html")).read()
    body = html[html.index("<body>") + 6: html.index("</body>")]
    css = open(os.path.join(SITE, "site.css")).read()
    js = open(os.path.join(SITE, "viewer.js")).read()
    index = json.load(open(os.path.join(SITE, "models", "index.json")))
    keep = [m for m in index["morphologies"] if m["id"] in a.morphs]
    embed = {"models/index.json": {"morphologies": keep},
             "data/results.json": json.load(open(os.path.join(SITE, "data", "results.json")))}
    for k in ("rubble", "stones"):
        embed[f"models/terrain_{k}.json"] = json.load(open(os.path.join(SITE, "models", f"terrain_{k}.json")))
    for m in keep:
        for sp in m["spaces"].values():
            embed[f"models/{sp['glb']}"] = b64(os.path.join(SITE, "models", sp["glb"]), "model/gltf-binary")
            embed[f"models/{sp['meta']}"] = json.load(open(os.path.join(SITE, "models", sp["meta"])))
    # figures as data URIs, PDF link -> note
    for fig in ("fig_slope.png", "fig_rho_a.png", "fig_rho_b.png"):
        body = body.replace(f'src="figs/{fig}"', f'src="{b64(os.path.join(SITE, "figs", fig), "image/png")}"')
    for th in sorted(os.listdir(os.path.join(SITE, "figs", "thumbs"))):
        if th.endswith(".webp"):
            body = body.replace(f'src="figs/thumbs/{th}"', f'src="{b64(os.path.join(SITE, "figs", "thumbs", th), "image/webp")}"')
    body = body.replace('href="paper.pdf"', 'href="#" title="PDF is in paper_iros2026/paper.pdf"')
    # gallery cards only for embedded morphologies: keep all cards but mark the others
    ids = {m["id"] for m in keep}
    body = re.sub(r'<button class="half (abs|fab)" type="button" data-morph="([^"]+)"',
                  lambda mm: mm.group(0) if mm.group(2) in ids else mm.group(0).replace('type="button"', 'type="button" disabled style="cursor:default"'), body)
    body = body.replace('<script type="module" src="viewer.js"></script>',
                        '<script>window.__EMBED = ' + json.dumps(embed, separators=(",", ":")) + ';</script>\n'
                        '<script type="module">\n' + js + '\n</script>')
    out = ('<title>Co-Design Rankings Do Not Survive Realization</title>\n'
           '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;450;500;600;650;700&family=IBM+Plex+Mono:wght@400;500&display=swap">\n'
           '<style>\n' + css + '\n</style>\n'
           '<script type="importmap">{"imports":{"three":"' + THREE + 'build/three.module.js","three/addons/":"' + THREE + 'examples/jsm/"}}</script>\n'
           '<div style="background:var(--orange);color:#14181d;font:500 .8rem/1.4 IBM Plex Mono,monospace;padding:8px 16px;text-align:center">Preview build — ' + str(len(keep)) + ' of 18 morphologies are loadable in the viewer (' + ", ".join(m["label"] for m in keep) + '); the full site in <code>website/</code> carries all 18.</div>\n'
           + body)
    open(a.out, "w").write(out)
    print(f"{a.out}: {os.path.getsize(a.out)/1e6:.1f} MB, embedded {len(keep)} morphologies")

if __name__ == "__main__":
    main()
