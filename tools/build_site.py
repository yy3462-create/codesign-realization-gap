#!/usr/bin/env python3
"""Render website/index.html from the template below + data/results.json.

  python build_site.py            # writes ../index.html

The gallery cards and the results table are static HTML (the page reads without JavaScript);
the 3D viewer is viewer.js. Thumbnails come from render_thumbs.py (figs/thumbs/<id>_{fab,abs}.webp).
Author names, links and the BibTeX are the constants right below — edit them here and re-run.
"""
import json, os, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "..")
R = json.load(open(os.path.join(SITE, "data", "results.json")))
rows = R["rows"]
by_id = {r["id"]: r for r in rows}

# ----------------------------------------------------------------------------- edit these
TITLE = "Co-Design Rankings Do Not Survive Realization"
SUBTITLE = "An 18-morphology, 4-environment study on a modular icosahedral legged robot"
VENUE = "IROS 2026 · Workshop on Learning-based Robot Co-design"
AUTHORS = [("Author One", "#", "1"), ("Author Two", "#", "1"), ("Author Three", "#", "1")]
AFFILS = [("1", "Creative Machines Lab, Columbia University")]
PAPER_URL = "paper.pdf"
CODE_URL = "https://github.com/jl6017/mujoco_playground/tree/IROS_workshop/icos/hardware_line"
BIBTEX = """@inproceedings{icos2026realization,
  title     = {Co-Design Rankings Do Not Survive Realization: An 18-Morphology, 4-Environment Study},
  author    = {Author One and Author Two and Author Three},
  booktitle = {IROS 2026 Workshop on Learning-based Robot Co-design: Generative and Iterative Approaches},
  year      = {2026},
  note      = {Non-archival extended abstract}
}"""
# -----------------------------------------------------------------------------

ICON_PDF = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2zm7 1.5V9h5.5L13 3.5zM8 13h8v1.5H8V13zm0 3.5h8V18H8v-1.5z"/></svg>'
ICON_GH = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>'
ICON_CITE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.5 6A4.5 4.5 0 0 0 2 10.5V18h7v-7H5.5a2 2 0 0 1 2-2H8V6H6.5zm10 0A4.5 4.5 0 0 0 12 10.5V18h7v-7h-3.5a2 2 0 0 1 2-2H18V6h-1.5z"/></svg>'


def species_short(s):
    return s.replace(" hand-designed", "")


def rank_chip(a, f):
    d = a - f          # rank improves when f < a
    if d > 2: return f'<span class="chip up" title="rank {a} in the abstract space → {f} fabricable">↑{d}</span>'
    if d < -2: return f'<span class="chip down" title="rank {a} in the abstract space → {f} fabricable">↓{-d}</span>'
    return f'<span class="chip" title="rank {a} in the abstract space → {f} fabricable">·{abs(d)}</span>'


def card(r):
    i = r["id"]; ra, rf = r["rank"]["abstract"], r["rank"]["flat"]
    return f'''<div class="card" data-morph="{i}">
  <div class="lbl"><b>{r["label"]}</b><span class="sp">{species_short(r["species"])} · {r["legs"]} legs</span>{rank_chip(ra, rf)}</div>
  <div class="pairs">
    <button class="half abs" type="button" data-morph="{i}" data-space="abstract" title="{r["label"]} in the abstract simulator — load in the viewer (rest pose)">
      <span class="thumb"><img src="figs/thumbs/{i}_abs.webp" alt="{r["label"]} as the abstract simulator sees it" width="640" height="480" loading="lazy" decoding="async"></span>
      <span class="stat"><b>{r["abstract"]:.1f} m</b><span>rank {ra}</span></span>
    </button>
    <span class="arrow" aria-hidden="true">→</span>
    <button class="half fab" type="button" data-morph="{i}" data-space="fabricable" title="{r["label"]} as a fabricable robot — load in the viewer">
      <span class="thumb"><img src="figs/thumbs/{i}_fab.webp" alt="{r["label"]} as a fabricable robot" width="640" height="480" loading="lazy" decoding="async"></span>
      <span class="stat"><b>{r["flat"]:.1f} m</b><span>rank {rf}</span></span>
    </button>
  </div>
</div>'''


cards = "\n".join(card(r) for r in sorted(rows, key=lambda r: r["rank"]["abstract"]))

trs = "\n".join(
    f'''<tr><td>{r["label"]}</td><td>{r["species"]}</td><td>{r["legs"]}</td>
<td class="a">{r["abstract"]:.2f}</td><td>{r["rank"]["abstract"]}</td>
<td>{r["ideal"]:.2f}</td>
<td class="f">{r["flat"]:.2f}</td><td>{r["rank"]["flat"]}</td>
<td>{r["rubble"]:.2f}</td><td>{r["ice"]:.2f}</td><td>{r["stones"]:.2f}</td><td>{r["F_min"]}</td><td>{r["J_min"]}</td></tr>'''
    for r in sorted(rows, key=lambda r: r["rank"]["flat"]))


authors = " · ".join(f'<a href="{u}">{n}<sup>{s}</sup></a>' for n, u, s in AUTHORS)
affils = " · ".join(f'<sup>{s}</sup>{a}' for s, a in AFFILS)
bib_html = BIBTEX.replace("&", "&amp;").replace("<", "&lt;")

HTML = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>@@TITLE@@</title>
<meta name="description" content="18 morphologies of a modular icosahedral robot, trained in an abstract and a fabricable simulator: the rankings are uncorrelated. Interactive 3D trajectories, figures and data.">
<meta property="og:title" content="@@TITLE@@">
<meta property="og:description" content="@@SUBTITLE@@">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;450;500;600;650;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="site.css">
<script type="importmap">{"imports":{"three":"./vendor/three.module.js","three/addons/":"./vendor/addons/"}}</script>
</head>
<body>

<header class="top">
  <div class="wrap">
    <div class="eyebrow">@@VENUE@@</div>
    <h1>Co-Design Rankings<br>Do Not Survive Realization</h1>
    <p class="subtitle">@@SUBTITLE@@</p>
    <p class="authors">@@AUTHORS@@</p>
    <p class="affil">@@AFFILS@@</p>
    <div class="actions">
      <a class="btn" href="@@PAPER_URL@@">@@ICON_PDF@@Paper</a>
      <a class="btn" href="@@CODE_URL@@">@@ICON_GH@@Code</a>
      <a class="btn" href="#bibtex">@@ICON_CITE@@BibTeX</a>
    </div>

    <div class="viewer-shell" id="viewer">
      <div id="viewport">
        <div class="hud"><div class="name" id="hud-name">—</div><div class="tag" id="hud-tag">loading…</div></div>
        <div class="readout">
          <span>time</span><b id="ro-time">0.00 s</b>
          <span>distance</span><b id="ro-disp">0.00 m</b>
          <span>paper mean</span><b id="ro-paper">—</b>
        </div>
        <div class="hint">drag to orbit · scroll to zoom · right-drag to pan</div>
        <div class="loading" id="loading">loading model…</div>
      </div>
      <div class="controls">
        <div class="group">
          <label class="small" for="morph">Morphology</label>
          <div class="transport">
            <button type="button" class="icon" id="prev" aria-label="Previous morphology">‹</button>
            <select class="morph" id="morph" aria-label="Morphology"></select>
            <button type="button" class="icon" id="next" aria-label="Next morphology">›</button>
          </div>
        </div>
        <div class="group">
          <span class="small">Design space</span>
          <div class="seg" role="group" aria-label="Design space">
            <button type="button" class="space-fab" data-space="fabricable" aria-pressed="true">Fabricable</button>
            <button type="button" class="space-abs" data-space="abstract" aria-pressed="false">Abstract</button>
          </div>
        </div>
        <div class="group">
          <span class="small">Environment</span>
          <div class="seg" role="group" aria-label="Environment">
            <button type="button" data-env="flat" aria-pressed="true">Flat</button>
            <button type="button" data-env="rubble" aria-pressed="false">Rubble</button>
            <button type="button" data-env="ice" aria-pressed="false">Ice</button>
            <button type="button" data-env="stones" aria-pressed="false">Stones</button>
          </div>
        </div>
        <div class="wide">
          <div class="transport">
            <button type="button" id="play" aria-pressed="true" aria-label="Play / pause">Pause</button>
            <div class="seg" role="group" aria-label="Playback speed">
              <button type="button" data-speed="0.25" aria-pressed="false">¼×</button>
              <button type="button" data-speed="0.5" aria-pressed="false">½×</button>
              <button type="button" data-speed="1" aria-pressed="true">1×</button>
              <button type="button" data-speed="2" aria-pressed="false">2×</button>
            </div>
          </div>
          <input type="range" id="scrub" min="0" max="1" step="0.001" value="0" aria-label="Scrub time">
          <div class="transport">
            <button type="button" id="follow" aria-pressed="true">Follow</button>
            <button type="button" id="reset">Reset view</button>
          </div>
        </div>
        <div class="note" id="viewer-note" style="grid-column: 1 / -1"></div>
      </div>
    </div>
    <p class="viewer-caption">Training-time trajectories of all 18 morphologies replayed through MuJoCo forward kinematics · 20 s clips · 4 environments · fabricable bodies drawn with the current leg design (v50: 4 printed parts + 3 × XM430 per leg, same joint layout as the trained model), abstract bodies as the proxies that simulator computes with (capsule links, lumped joint masses)</p>
  </div>
</header>

<section id="tldr">
  <div class="wrap narrow">
    <p class="tldr">The same 18 robot bodies, trained once in the idealised simulator a co-design search uses and once as printable machines: <b class="brick-t">the two rankings are unrelated</b> (ρ<sub>s</sub> = 0.11) — while changing terrain or friction <b class="steel-t">leaves them intact</b> (ρ<sub>s</sub> = 0.7–0.9). Fidelity belongs inside the co-design loop, not after it.</p>
    <details class="abstract">
      <summary>Abstract</summary>
      <div>
      <p>Learning-based co-design methods score candidate robot bodies in a simplified simulator and return a ranked list. We ask how much of that ranking survives when the designs are made buildable. We take 18 morphologies of a modular icosahedral legged robot, sampled from our own evolutionary co-design space, and train each with the same PPO recipe in a replica of the abstract simulator used by the search and in a fabricable simulator calibrated against CAD models and motor datasheets. The two rankings are uncorrelated (ρ<sub>s</sub> = +0.11, p = 0.66; mean rank change 5.9 of 18): the best abstract design drops to 7th, and a design that barely moved in the abstract simulator (0.54 m, 17th) becomes 2nd at 10.8 m. The reshuffle is robust to the training seed (P &lt; 0.02 under resampling), to reward re-weighting and added mass (ρ<sub>s</sub> ≥ 0.77) and to halving the training budget (ρ<sub>s</sub> ≥ 0.90), and it is caused mainly by the changes in geometry, DoF allocation, rest pose and mass rather than by the actuator model (ρ<sub>s</sub> = −0.30 vs. +0.61). Changing the terrain at fixed realization, in contrast, largely preserves the ranking (rubble ρ<sub>s</sub> = 0.90, ice 0.72); only stepping stones reshuffle it as much. We trace the reshuffle to a shell-sliding exploit, to rest poses that penetrate or float above the ground, and to a leg-count advantage that exists only in the abstract simulator. Simulator fidelity should therefore be part of the co-design loop rather than a step after it.</p>
      </div>
    </details>
  </div>
  <div class="wrap">
    <div class="numbers">
      <div><div class="v brick">0.11</div><div class="k">ρ<sub>s</sub> abstract ↔ fabricable ranking (p = 0.66)</div></div>
      <div><div class="v">5.9 / 18</div><div class="k">mean rank shift at realization</div></div>
      <div><div class="v steel">0.90 · 0.72</div><div class="k">ρ<sub>s</sub> rubble · ice — the environment keeps the ranking</div></div>
      <div><div class="v">P &lt; 0.02</div><div class="k">reshuffle vs. seed noise (6 × 3 replication)</div></div>
    </div>
  </div>
</section>

<section id="figures">
  <div class="wrap">
    <h2>Realization reshuffles the ranking; the task environment does not</h2>
    <p class="sub">Rank of each of the 18 bodies after training in the abstract simulator vs. as a fabricable robot — then across terrains.</p>
    <div class="figs">
      <figure class="card-fig" style="max-width:660px;margin:0 auto">
        <img src="figs/fig_slope.png" alt="Slope graph: rank of 18 morphologies in the abstract space versus the fabricable space; lines cross heavily" width="1005" height="480">
        <figcaption>Abstract flat-ground rank → fabricable rank. <span class="key">Q/T/M/H hand-designed · A–G species (4,4,4)…(2,2,2,2,2,2), samples a/b · digit = legs</span></figcaption>
      </figure>
      <div class="figs two">
        <figure class="card-fig">
          <img src="figs/fig_rho_a.png" alt="Bar chart of Spearman rank correlations with the fabricable flat ranking: design space 0.11, stepping stones 0.12, ice 0.72, rubble 0.90" width="1237" height="345">
          <figcaption>Realization sits far outside the seed-noise band (0.89–0.98 from a clean-recipe 6 × 3 seed replication); rubble sits inside it, ice just below — only discrete footholds reshuffle like realization.</figcaption>
        </figure>
        <figure class="card-fig">
          <img src="figs/fig_rho_b.png" alt="Bar chart of median performance retention per leg count on rubble, ice and stepping stones" width="865" height="345">
          <figcaption>The leg-count advantage is environment-conditional.</figcaption>
        </figure>
      </div>
    </div>
  </div>
</section>

<section id="morphologies">
  <div class="wrap">
    <h2>The 18 morphologies, in both simulators</h2>
    <p class="sub"><span class="brick-t">Left: as the abstract simulator sees it</span> → <span class="steel-t">right: as a fabricable robot</span> · 20 s displacement and rank of 18 · ordered by abstract rank · click either side to load it in the viewer</p>
    <div class="gallery" id="gallery">
@@CARDS@@
    </div>
  </div>
</section>

<section id="realization">
  <div class="wrap narrow">
    <h2>What changes at realization</h2>
    <p class="sub">Same reward, same PPO budget, same 18 bodies — only the simulator changes.</p>
    <dl class="speclist">
      <div><dt>Leg module</dt><dd><span class="from">free 12-DoF partition, 2–5 DoF per leg</span><span class="arrow">→</span><span class="to">one printable 3-DoF module, DoF = 3 × legs</span></dd></div>
      <div><dt>Collision</dt><dd><span class="from">sphere proxies, smooth shell</span><span class="arrow">→</span><span class="to">convex-hull body, motor cylinders, skirt rings</span></dd></div>
      <div><dt>Rest pose</dt><dd><span class="from">straight legs, unreachable</span><span class="arrow">→</span><span class="to">solved equilibrium (Δz &lt; 25 mm, no penetration)</span></dd></div>
      <div><dt>Actuation</dt><dd><span class="from">ideal position servo</span><span class="arrow">→</span><span class="to">torque PD, 4.1 N·m / 4.8 rad s⁻¹ envelope, 0–20 ms latency, sensor noise</span></dd></div>
      <div><dt>Mass</dt><dd><span class="from">lumped at joints, 2.2 kg for all</span><span class="arrow">→</span><span class="to">CAD masses at centroids, 1.8–3.1 kg, 9–18 servos</span></dd></div>
    </dl>
    <p class="finding">Reverting only the actuator to the ideal servo leaves the ranking unrelated to the abstract one (ρ<sub>s</sub> = −0.30) but close to the calibrated one (ρ<sub>s</sub> = +0.61): <b>geometry, DoF, rest pose and mass do the damage — not the actuator.</b></p>
  </div>
</section>

<section id="results">
  <div class="wrap">
    <details class="table">
      <summary>Full results table — 18 morphologies × 8 conditions</summary>
      <div class="tablewrap">
        <table id="results-table">
          <thead><tr>
            <th>Morph</th><th>Species</th><th>Legs</th>
            <th>Abstract m</th><th>rank</th><th title="fabricable body, abstract ideal servos">Ideal-servo m</th><th>Fabricable m</th><th>rank</th>
            <th>Rubble m</th><th>Ice m</th><th>Stones m</th><th>F</th><th>J</th>
          </tr></thead>
          <tbody>
@@ROWS@@
          </tbody>
        </table>
      </div>
      <p class="tablenote">Mean 20 s displacement over 4096 rollouts · Ideal-servo = fabricable body with the abstract servo model · F / J = placement / axis mirror-asymmetry (0 = symmetric) · click a header to sort</p>
    </details>
  </div>
</section>

<section id="bibtex">
  <div class="wrap narrow">
    <h2>BibTeX</h2>
    <div class="bibwrap">
      <button type="button" class="copy" id="copy-bib">Copy</button>
      <pre class="bib mono" id="bib">@@BIBTEX@@</pre>
    </div>
  </div>
</section>

<footer>
  <div class="wrap">
    <p>Viewer clips are training-time recordings replayed through MuJoCo forward kinematics on the current leg CAD (v50; identical joint frames to the trained hw7 model); the rubble is the exact seed-0 heightfield, the stepping-stone layout is illustrative.</p>
    <p>Morphologies from the <a href="https://github.com/jl6017/mujoco_playground">ICOS co-design EA</a> (MuJoCo MJX) · trained in <a href="https://github.com/Genesis-Embodied-AI/genesis-world">Genesis</a> with rsl-rl PPO · built @@DATE@@</p>
  </div>
</footer>

<script>
// results table sorting
document.querySelectorAll('#results-table th').forEach((th, i) => th.addEventListener('click', () => {
  const tb = th.closest('table').tBodies[0];
  const dir = th.getAttribute('aria-sort') === 'descending' ? 'ascending' : 'descending';
  th.parentNode.querySelectorAll('th').forEach((x) => x.removeAttribute('aria-sort'));
  th.setAttribute('aria-sort', dir);
  const num = (s) => parseFloat(s.replace(/[^0-9.\\-]/g, ''));
  [...tb.rows].sort((a, b) => {
    const x = a.cells[i].textContent, y = b.cells[i].textContent;
    const nx = num(x), ny = num(y);
    const c = (isNaN(nx) || isNaN(ny)) ? x.localeCompare(y) : nx - ny;
    return dir === 'descending' ? -c : c;
  }).forEach((r) => tb.appendChild(r));
}));
// bibtex copy
document.getElementById('copy-bib').addEventListener('click', async (e) => {
  try { await navigator.clipboard.writeText(document.getElementById('bib').textContent); e.target.textContent = 'Copied'; }
  catch { e.target.textContent = 'Select & copy'; }
  setTimeout(() => { e.target.textContent = 'Copy'; }, 1600);
});
</script>
<script type="module" src="viewer.js"></script>
</body>
</html>
'''

for k, v in {"TITLE": TITLE, "SUBTITLE": SUBTITLE, "VENUE": VENUE, "AUTHORS": authors, "AFFILS": affils,
             "PAPER_URL": PAPER_URL, "CODE_URL": CODE_URL, "ICON_PDF": ICON_PDF, "ICON_GH": ICON_GH,
             "ICON_CITE": ICON_CITE, "CARDS": cards, "ROWS": trs, "BIBTEX": bib_html,
             "DATE": datetime.date.today().isoformat()}.items():
    HTML = HTML.replace(f"@@{k}@@", v)
assert "@@" not in HTML, "unfilled placeholder"
open(os.path.join(SITE, "index.html"), "w").write(HTML)
print("wrote index.html", len(HTML), "bytes")
