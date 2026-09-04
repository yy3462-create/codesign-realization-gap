#!/usr/bin/env python3
"""MuJoCo screen recordings of the recorded training-time trajectories.

Replays genesis_rl/videos/{R}_r4d2_d25m_traj.npz (base_pos, base_quat wxyz, dof_pos in qpos order, dt)
on the abstract-space scene of each morphology and renders it with MuJoCo's own offscreen renderer —
the same forward kinematics the 3D viewer uses, drawn by MuJoCo instead of three.js.

  python render_mujoco_clips.py                       # all 18 -> ../../genesis_rl/videos_mujoco/
  python render_mujoco_clips.py --only quadruped hexapod
  python render_mujoco_clips.py --media               # also copy the page's six clips into ../media/
  python render_mujoco_clips.py --variant sci         # the science files' own meshes instead of absvis

Scene: mjcf_pack/mjcf/scene_mjx_{R}_flat_terrain.xml with its robot include swapped for
{R}_mjx_{variant}.xml (default absvis: capsule links + joint spheres, what the abstract simulator
computes with).  Visual-only variants have no sensors / actuators, so the sensor include and the
keyframe ctrl are dropped.  Output 960 x 540, 25 fps, h264 (ffmpeg on PATH).

Headless: MUJOCO_GL=egl on Linux (default here), glfw on macOS.  The scene files ask for an 8192 px
shadow map; that is capped at 2048 because software GL otherwise crawls (~3 fps).
"""
import argparse, os, re, shutil, subprocess, sys
os.environ.setdefault("MUJOCO_GL", "egl" if sys.platform.startswith("linux") else "glfw")
import mujoco, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.environ.get("ICOS_MJCF_PACK", os.path.join(HERE, "..", "..", "mjcf_pack", "mjcf"))
VIDEOS = os.path.join(HERE, "..", "..", "genesis_rl", "videos")
MORPHS = ["quadruped", "tripod", "mixed", "hexapod",
          "g0_444_0", "g0_444_1", "g0_3333_0", "g0_3333_1", "g0_4332_0", "g0_4332_1", "g0_4422_0", "g0_4422_1",
          "g0_42222_0", "g0_42222_1", "g0_33222_0", "g0_33222_1", "g0_222222_0", "g0_222222_1"]
PAGE_CLIPS = ["g0_444_0", "g0_444_1", "quadruped", "hexapod", "g0_222222_0", "g0_42222_1"]   # tools/build_site.py VIDEO_PICKS


def npz_for(R):
    return os.path.join(VIDEOS, "quadruped_r4d2_d25m_sci_traj.npz" if R == "quadruped" else f"{R}_r4d2_d25m_traj.npz")


def stem_for(R):
    return "quadruped_r4d2_d25m_sci_mujoco" if R == "quadruped" else f"{R}_r4d2_d25m_mujoco"


def scene_for(R, variant, w, h):
    src = open(os.path.join(PACK, f"scene_mjx_{R}_flat_terrain.xml")).read()
    if variant != "sci":
        src = re.sub(r'<include file="[^"]*_mjx(?:_sci)?\.xml"/>', f'<include file="{R}_mjx_{variant}.xml"/>', src, count=1)
        src = re.sub(r'\s*<include file="sensor_[^"]*"/>', '', src)     # visual-only variants have no sensor sites
        src = re.sub(r'\s+ctrl="[^"]*"', '', src)                        # ... and no actuators
    elif R == "quadruped":                                               # the live quadruped file is the hardware one
        src = src.replace('<include file="quadruped_mjx.xml"/>', '<include file="quadruped_mjx_sci.xml"/>')
    tmp = os.path.join(PACK, f"_render_{R}_{variant}.xml")
    open(tmp, "w").write(src)
    m = mujoco.MjModel.from_xml_path(tmp)
    os.remove(tmp)
    m.vis.global_.offwidth, m.vis.global_.offheight = w, h
    m.vis.quality.shadowsize = min(m.vis.quality.shadowsize, 2048)
    return m


def render(R, out, variant="absvis", fps=25, w=960, h=540, dist=0.95, az=135.0, el=-18.0):
    m = scene_for(R, variant, w, h)
    d = mujoco.MjData(m)
    z = np.load(npz_for(R))
    bp, bq, dp, dt = z["base_pos"], z["base_quat"], z["dof_pos"], float(z["dt"])
    assert m.nq == 7 + dp.shape[1], f"{R}: model nq {m.nq} vs trajectory 7+{dp.shape[1]}"
    step = max(1, int(round(1.0 / (fps * dt))))
    cam = mujoco.MjvCamera(); cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.distance, cam.azimuth, cam.elevation = dist, az, el
    opt = mujoco.MjvOption()
    r = mujoco.Renderer(m, h, w)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
                           "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p",
                           "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    light0 = m.light_pos.copy()          # the scene's spotlight sits at a fixed (3, 0, 4); a body 15 m away
    n = 0                                #   walks out of its cone and its shadow map aliases -> move it along
    for i in range(0, len(bp), step):
        d.qpos[:3] = bp[i]; d.qpos[3:7] = bq[i]; d.qpos[7:] = dp[i]
        m.light_pos[:] = light0 + np.array([bp[i][0], bp[i][1], 0.0])
        mujoco.mj_forward(m, d)
        cam.lookat[:] = [bp[i][0], bp[i][1], 0.12]
        r.update_scene(d, cam, opt)
        ff.stdin.write(r.render().tobytes()); n += 1
    ff.stdin.close(); ff.wait(); r.close()
    print(f"  {R}: {n} frames, {n / fps:.1f} s -> {out}")
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--only", nargs="*", default=None)
    p.add_argument("--out", default=os.path.join(HERE, "..", "..", "genesis_rl", "videos_mujoco"))
    p.add_argument("--variant", default="absvis", help="absvis (capsules + joint spheres) or sci (the science files' meshes)")
    p.add_argument("--media", action="store_true", help="copy the page's six clips into ../media/ as well")
    p.add_argument("--fps", type=int, default=25); p.add_argument("--w", type=int, default=960); p.add_argument("--h", type=int, default=540)
    a = p.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for R in (a.only or MORPHS):
        render(R, os.path.join(a.out, stem_for(R) + ".mp4"), a.variant, a.fps, a.w, a.h)
    if a.media:
        media = os.path.join(HERE, "..", "media"); os.makedirs(media, exist_ok=True)
        for R in PAGE_CLIPS:
            if a.only and R not in a.only: continue
            shutil.copy2(os.path.join(a.out, stem_for(R) + ".mp4"), media)
        print("copied the page clips into", media)


if __name__ == "__main__":
    main()
