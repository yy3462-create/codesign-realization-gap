#!/usr/bin/env python3
"""Build every model GLB for the website from the MJCF pack + recorded trajectories.

  python build_models.py --videos ../../genesis_rl/videos --out ../models
  python build_models.py --spaces fabricable            # only the fabricable GLBs (v50 visuals, hw7 kinematics)
  python build_models.py --variant hw7 --spaces fabricable   # the trained model's own hw7 meshes instead

Fabricable visuals default to the current leg design (make_v50_visuals.py -> {R}_mjx_v50vis.xml); the
animation is the same either way (identical joint frames). Abstract visuals default to the proxy drawing
(make_abs_visuals.py -> {R}_mjx_absvis.xml); --abs-variant sci uses the science files' own meshes.

Clip discovery (per morphology R), fabricable space:
  flat    videos/{R}_r4d2_hw7h2_hw7_traj.npz          (re-solved home)  else  {R}_r4d2_hw7s2r_hw7_traj.npz
  rubble  videos/{R}_r4d2_hw7h2_hw7_noise30_traj.npz                    else  {R}_r4d2_hw7s2r_hw7_noise30_traj.npz
  ice     videos/{R}_r4d2_hw7h2ice_hw7_traj.npz                          else  {R}_r4d2_hw7ice_hw7_traj.npz
  stones  videos/{R}_r4d2_hw7st3b_hw7_iso_stones_traj.npz  (4 baselines, ranking reward)  else  {R}_r4d2_hw7st3_hw7_iso_stones_traj.npz
Abstract space: videos/{R}_r4d2_d25m_traj.npz (quadruped: {R}_r4d2_d25m_sci_traj.npz) -> label "flat".
Missing clips are simply skipped; the GLB then only carries the rest pose. Re-run after
record_icos.py produced new trajectories — models/index.json lists what each GLB contains.
"""
import argparse, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MORPHS = ["quadruped", "tripod", "mixed", "hexapod",
          "g0_444_0", "g0_444_1", "g0_3333_0", "g0_3333_1",
          "g0_4332_0", "g0_4332_1", "g0_4422_0", "g0_4422_1",
          "g0_42222_0", "g0_42222_1", "g0_33222_0", "g0_33222_1",
          "g0_222222_0", "g0_222222_1"]
LEGS = {"quadruped": 4, "tripod": 3, "mixed": 5, "hexapod": 6,
        "g0_444_0": 3, "g0_444_1": 3, "g0_3333_0": 4, "g0_3333_1": 4, "g0_4332_0": 4, "g0_4332_1": 4,
        "g0_4422_0": 4, "g0_4422_1": 4, "g0_42222_0": 5, "g0_42222_1": 5, "g0_33222_0": 5,
        "g0_33222_1": 5, "g0_222222_0": 6, "g0_222222_1": 6}
LABEL = {"quadruped": "Q4", "tripod": "T3", "mixed": "M5", "hexapod": "H6",
         "g0_444_0": "A3a", "g0_444_1": "A3b", "g0_3333_0": "B4a", "g0_3333_1": "B4b",
         "g0_4332_0": "C4a", "g0_4332_1": "C4b", "g0_4422_0": "D4a", "g0_4422_1": "D4b",
         "g0_42222_0": "E5a", "g0_42222_1": "E5b", "g0_33222_0": "F5a", "g0_33222_1": "F5b",
         "g0_222222_0": "G6a", "g0_222222_1": "G6b"}
SPECIES = {"quadruped": "(3,3,3,3) hand-designed", "tripod": "(4,4,4) hand-designed",
           "mixed": "(3,3,2,2,2) hand-designed", "hexapod": "(2,2,2,2,2,2) hand-designed",
           "g0_444": "(4,4,4)", "g0_3333": "(3,3,3,3)", "g0_4332": "(4,3,3,2)", "g0_4422": "(4,4,2,2)",
           "g0_42222": "(4,2,2,2,2)", "g0_33222": "(3,3,2,2,2)", "g0_222222": "(2,2,2,2,2,2)"}


def first_existing(videos, *names):
    for n in names:
        p = os.path.join(videos, n)
        if os.path.exists(p):
            return p
    return None


def clips_for(videos, R, space):
    if space == "fabricable":
        c = {"flat": first_existing(videos, f"{R}_r4d2_hw7h2_hw7_traj.npz", f"{R}_r4d2_hw7s2r_hw7_traj.npz"),
             "rubble": first_existing(videos, f"{R}_r4d2_hw7h2_hw7_noise30_traj.npz", f"{R}_r4d2_hw7s2r_hw7_noise30_traj.npz"),
             "ice": first_existing(videos, f"{R}_r4d2_hw7h2ice_hw7_traj.npz", f"{R}_r4d2_hw7ice_hw7_traj.npz"),
             "stones": first_existing(videos, f"{R}_r4d2_hw7st3b_hw7_iso_stones_traj.npz", f"{R}_r4d2_hw7st3_hw7_iso_stones_traj.npz")}
    else:
        c = {"flat": first_existing(videos, f"{R}_r4d2_d25m_sci_traj.npz" if R == "quadruped" else f"{R}_r4d2_d25m_traj.npz")}
    return {k: v for k, v in c.items() if v}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--videos", default=os.path.join(HERE, "..", "..", "genesis_rl", "videos"))
    p.add_argument("--out", default=os.path.join(HERE, "..", "models"))
    p.add_argument("--faces", type=int, default=1500)
    p.add_argument("--only", nargs="*", default=None)
    p.add_argument("--spaces", nargs="*", default=["fabricable", "abstract"])
    p.add_argument("--variant", default="v50vis",
                   help="fabricable visuals: v50vis (current CAD on the hw7 kinematics) or hw7 (the trained model's own meshes)")
    p.add_argument("--abs-variant", default="absvis",
                   help="abstract visuals: absvis (capsules + joint spheres, what the abstract sim computes with) or sci (the science files' meshes)")
    a = p.parse_args()
    os.makedirs(a.out, exist_ok=True)
    index_path = os.path.join(a.out, "index.json")
    # keep entries we are not rebuilding (e.g. --spaces fabricable leaves the abstract GLBs alone)
    old = json.load(open(index_path)) if os.path.exists(index_path) else {"morphologies": []}
    old_by_id = {m["id"]: m for m in old["morphologies"]}
    index = {"variant": a.variant, "abs_variant": a.abs_variant, "morphologies": []}
    for R in MORPHS:
        if a.only and R not in a.only:
            if R in old_by_id:
                index["morphologies"].append(old_by_id[R])
            continue
        entry = {"id": R, "label": LABEL[R], "legs": LEGS[R],
                 "species": SPECIES.get(R, SPECIES.get(R.rsplit("_", 1)[0], "")),
                 "spaces": dict(old_by_id.get(R, {}).get("spaces", {}))}
        for space, tag in (("fabricable", "fab"), ("abstract", "abs")):
            if space not in a.spaces:
                continue
            clips = clips_for(a.videos, R, space)
            out = os.path.join(a.out, f"{R}_{tag}.glb")
            cmd = [sys.executable, os.path.join(HERE, "mjcf_to_glb.py"), "--robot", R, "--space", space,
                   "--out", out, "--faces", str(a.faces), "--variant", a.variant, "--abs-variant", a.abs_variant] + [f"--clip={k}={v}" for k, v in clips.items()]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                print(f"!! {R} {space} failed:\n{r.stderr[-800:]}")
                continue
            print(r.stdout.strip().splitlines()[-1])
            meta = json.load(open(os.path.splitext(out)[0] + ".json"))
            entry["spaces"][space] = {"glb": os.path.basename(out), "meta": os.path.basename(out).replace(".glb", ".json"),
                                      "clips": {k: {"source": os.path.basename(v),
                                                    "displacement_final_m": meta["clips"][k]["displacement_final_m"],
                                                    "seconds": meta["clips"][k]["seconds"]} for k, v in clips.items()}}
        index["morphologies"].append(entry)
    json.dump(index, open(index_path, "w"), indent=1)
    print("wrote", index_path)


if __name__ == "__main__":
    main()
