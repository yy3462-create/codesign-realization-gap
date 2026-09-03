# Project page — "Co-Design Rankings Do Not Survive Realization"

Static site (no build step, no framework): `index.html` + `site.css` + `viewer.js`, Three.js vendored
in `vendor/`, one GLB per morphology and design space in `models/`, figures in `figs/`.
The 3D viewer replays the *training-time trajectories* (`genesis_rl/videos/*_traj.npz`, written by
`record_icos.py`) through MuJoCo forward kinematics; nothing is re-simulated in the browser.

## Preview locally

```bash
cd website && python3 -m http.server 8000     # then open http://localhost:8000
```
(Opening `index.html` from the file system does not work — ES modules and `fetch` need http.)

## Deploy

Any static host works. GitHub Pages: push this folder to a public repo (or the `docs/` folder of one),
Settings → Pages → deploy from branch. Total size ≈ 40 MB, dominated by `models/` (36 GLBs, 0.4–1.9 MB
each). Nothing is loaded from third-party hosts except the Google Fonts stylesheet.

## Updating the animations when new trajectories arrive

`models/index.json` lists, per morphology and space, which clips exist and which run they came from.
Right now (2026-09-01):

| space | flat | rubble | ice | stones |
|---|---|---|---|---|
| fabricable | 18/18 (`hw7s2r`; the 8 re-solved-home `hw7h2` runs are **not** recorded yet (g0_4422_1's hw7h2 dirs exist but are empty — never trained)) | 18/18 | 18/18 | 14/18 (the 4 baselines' `hw7st3` runs were never recorded) |
| abstract | 0/18 (rest pose only) | — | — | — |

1. Record the missing clips on the Mac (Genesis, `gtest` env; each takes ~1–2 min):
   ```bash
   cd ~/Desktop/CreativeM/SymmetricRobot/genesis_rl && conda activate gtest
   # re-solved-home flat/rubble/ice runs (9 morphologies)
   python record_icos.py --seconds 20 --tag hw7h2_hw7 --robots hexapod g0_444_0 g0_3333_0 g0_4332_1 g0_4422_0 g0_4422_1 g0_33222_0 g0_33222_1 g0_222222_0
   python record_icos.py --seconds 20 --tag hw7h2_hw7_noise30 --robots hexapod g0_444_0 g0_3333_0 g0_4332_1 g0_4422_0 g0_4422_1 g0_33222_0 g0_33222_1 g0_222222_0
   python record_icos.py --seconds 20 --tag hw7h2ice_hw7 --robots hexapod g0_444_0 g0_3333_0 g0_4332_1 g0_4422_0 g0_4422_1 g0_33222_0 g0_33222_1 g0_222222_0
   # stepping stones for the 4 baselines
   python record_icos.py --seconds 20 --tag hw7st3_hw7_iso_stones --robots quadruped tripod mixed hexapod
   # abstract space (17 morphologies use their own _mjx.xml; see the quadruped note below)
   python record_icos.py --seconds 20 --tag d25m --all
   ```
   **Quadruped in the abstract space:** `logs/icos_quadruped_r4d2_d25m/cfgs.pkl` points at
   `quadruped_mjx.xml`, which has since become the hardware model; the science-line file is
   `quadruped_mjx_sci.xml`. `record_icos.py` (and `eval_honest.py`) must override `env_cfg["mjcf_file"]`
   for that one run — a 3-line env-var hook, see `tools/PATCH_record_icos.md`. Save the result as
   `videos/quadruped_r4d2_d25m_sci_traj.npz` (the builder looks for that name).
2. Rebuild the GLBs and the index (MuJoCo + Open3D, CPU, ~2 min for all 36):
   ```bash
   cd website/tools
   pip install mujoco open3d trimesh        # once
   python build_models.py                   # reads ../../genesis_rl/videos, writes ../models
   python build_site.py                     # regenerates index.html (gallery + table from data/results.json)
   ```
   `export_terrain.py` only needs re-running if the terrain parameters change.

## Files

| path | role |
|---|---|
| `tools/mjcf_to_glb.py` | MJCF → GLB: visual geoms, Open3D decimation to 1500 tris/mesh, body nodes, one glTF animation per clip (25 Hz), Z-up → Y-up root |
| `tools/build_models.py` | discovers clips per morphology/space and writes every GLB + `models/index.json` |
| `tools/export_terrain.py` | the seed-0 rubble heightfield (exact) and an illustrative stepping-stone field |
| `tools/build_site.py` | renders `index.html` from `data/results.json` |
| `viewer.js` | Three.js viewer: OrbitControls, follow camera, terrain meshes, path trail, readouts |
| `data/results.json` | the paper's 18×5 table + ranks + symmetry scores (from `paper_iros2026/`) |

Author names, the code link and the BibTeX are placeholders in `tools/build_site.py` — edit there and re-run it.
