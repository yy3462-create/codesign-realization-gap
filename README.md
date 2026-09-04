# Project page — "Co-Design Rankings Do Not Survive Realization"

**Not deployed yet.** GitHub Pages has never been enabled on this repo, so
https://yy3462-create.github.io/codesign-realization-gap/ currently returns 404. See *Deploy* below --
it is one setting away. Until then the only way to see the page is to serve it locally.

Static site (no build step, no framework): `index.html` + `site.css` + `viewer.js`, Three.js vendored
in `vendor/`, one GLB per morphology in `models/`, figures in `figs/`, and six MuJoCo-rendered rollout
clips in `media/`. The 3D viewer replays the *training-time trajectories* (`genesis_rl/videos/*_traj.npz`,
written by `record_icos.py`) through MuJoCo forward kinematics; nothing is re-simulated in the browser.

## What the page shows, and what it deliberately does not (2026-09-04)

Every animation on the page — the viewer and the six clips — is the **abstract space**: the science-line
MJCF (`mjcf_pack/mjcf/{R}_mjx.xml`, quadruped `quadruped_mjx_sci.xml`) with its skeleton, joint order and
`home` keyframe untouched and the visuals replaced by what that simulator computes with (capsule links,
joint spheres; `tools/make_abs_visuals.py` → `{R}_mjx_absvis.xml`). Flat ground only, because that is
the only environment the abstract line was trained on.

The **fabricable-space numbers** (cards, table, captions) are the paper's: the hw7 printable module
build, one 3-DoF leg module per leg, DoF = 3 × legs. Its *animations* are not on the page:

- the hw7 bodies are an older CAD generation, and dressing them in the current parts
  (`tools/make_v50_visuals.py`, "v50vis") gives every leg three motors — a hexapod with 18, a tripod
  with 9 — which is hw7, not the current hardware;
- the current build (hw17, `mujoco_playground/icos/hardware_line/mjcf_pack/hw17_README.md`) keeps the
  science line's true 2/3/4 joints per leg and the 12-motor budget, but has no trained policies yet, and
  its generator still places the M1 stators on the quadruped's four faces for every morphology
  (hw17_README §6) — fix that before rendering it.

When hw17 policies exist: record them with `record_icos.py`, rebuild the GLBs with
`tools/build_models.py --spaces fabricable --variant hw17` (add the variant to `mjcf_to_glb.py`),
restore the second half of the gallery cards and the Fabricable button in `tools/build_site.py`
(`git show 3376425:tools/build_site.py` has the two-sided version), and re-render the clips.

## Preview locally

```bash
cd website && python3 -m http.server 8000     # then open http://localhost:8000
```
(Opening `index.html` from the file system does not work — ES modules and `fetch` need http.)

## Deploy

To publish: repo Settings → Pages → Source **Deploy from a branch** → branch **`main`**, folder
**`/ (root)`** → Save. The first build takes about a minute; after that every push to `main` redeploys.
`.nojekyll` is committed so Pages copies the tree verbatim instead of running Jekyll over it (Jekyll
silently drops anything whose path starts with `_`). Total size ≈ 27 MB, largest file 3.6 MB, both far
under the Pages limits. Nothing is loaded from third-party hosts except the Google Fonts stylesheet.

**Cache-busting.** `build_site.py` hashes every asset the page references (`asset_version()`) and
appends `?v=<10 hex>` to each URL it writes — stylesheet, module script, figures, thumbnails, clips,
paper. `viewer.js` reads that stamp back off its own `import.meta.url` and passes it to everything it
fetches at runtime (`models/index.json`, the GLBs and their `.json` siblings, `data/results.json`,
the terrain fields), so a single stamp covers the whole page.

This is not cosmetic. Pages caches each file independently, so without it a returning visitor can pair
a cached `viewer.js` with a freshly fetched `models/index.json`: the old code asks for
`models/<id>_fab.glb`, which the abstract-only rebuild deleted, the load rejects, and the viewer sits
on "loading model…" forever while the rest of the page looks normal. Reproduced before the fix, gone
after. Any asset change moves the stamp, so that pairing can no longer happen — but a visitor still
holding an `index.html` cached from before this commit needs one hard reload (⇧⌘R / Ctrl-F5) to escape.

Note that this repo is public, so enabling Pages publishes the paper PDF, the models and the clips
along with it.

## Rebuilding

```bash
cd website/tools
pip install mujoco open3d trimesh                 # once
python build_models.py --spaces abstract           # 18 GLBs + models/index.json from ../../genesis_rl/videos
python render_thumbs.py                            # figs/thumbs/{R}_abs.webp (needs a browser; see the script)
python render_mujoco_clips.py --media              # 18 MuJoCo mp4s -> ../../genesis_rl/videos_mujoco/, six -> ../media/
python build_site.py                               # index.html from data/results.json
```

`render_mujoco_clips.py` needs `ffmpeg` on PATH and a GL context: `MUJOCO_GL=egl` on a headless Linux
box (default), `glfw` on a Mac. It replays each `{R}_r4d2_d25m_traj.npz` on the absvis scene with
MuJoCo's offscreen renderer (960 × 540, 25 fps, 20 s), a following free camera and spotlight, shadow map capped at
2048 px. `--variant sci` renders the science files' own meshes instead.

The clip pipeline for the fabricable line (`--spaces fabricable`, `hw7h2`/`hw7s2r` tags, terrain
clips) is still in `build_models.py`; it is just not used by the page right now.

## Files

| path | role |
|---|---|
| `tools/mjcf_to_glb.py` | MJCF → GLB: visual geoms, Open3D decimation to 1500 tris/mesh, body nodes, one glTF animation per clip (25 Hz), Z-up → Y-up root |
| `tools/build_models.py` | discovers clips per morphology/space and writes every GLB + `models/index.json` |
| `tools/make_abs_visuals.py` | the abstract-space visual variants (`{R}_mjx_absvis.xml`) the page uses |
| `tools/make_v50_visuals.py` | v50 parts on the hw7 skeleton (`{R}_mjx_v50vis.xml`) — hw7 topology, not the current build; unused by the page |
| `tools/render_mujoco_clips.py` | MuJoCo offscreen recordings of the abstract trajectories (`media/*.mp4`) |
| `tools/export_terrain.py` | the seed-0 rubble heightfield (exact) and an illustrative stepping-stone field (viewer support, unused while the page is flat-only) |
| `tools/build_site.py` | renders `index.html` from `data/results.json`; author list, links, BibTeX and the six video picks are constants at the top |
| `viewer.js` | Three.js viewer: OrbitControls, follow camera, terrain meshes, path trail, readouts |
| `data/results.json` | the paper's 18×5 table + ranks + symmetry scores (from `paper_iros2026/`) |
