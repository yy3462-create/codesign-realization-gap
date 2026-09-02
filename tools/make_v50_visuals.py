#!/usr/bin/env python3
"""Visual-only MJCF variants of the 18 hw7 morphologies with the current leg design (v50).

  python make_v50_visuals.py            # writes ../../mjcf_pack/mjcf/{R}_mjx_v50vis.xml for all 18

The kinematic tree (leg frames, joint axes, J2 at 89 mm, J3 at 209 mm, foot at 329 mm) is exactly the
hw7 line's — the v50 design retained the motor transforms — so the recorded hw7 trajectories replay on
these bodies unchanged. Only the visual geoms differ: v50 mount / conn1 / conn2 / foot (4 printed parts
per leg), the XM430 as placed in the v50 assembly, and the plain icosahedral shell.

Frame bookkeeping: the v50 leg frame sits 6 mm outside the MJCF leg frame along the face normal
(the motor back cover; MJCF's conn12 geom carried the same +6 mm offset), so
    p_mjcf_leg = p_v50 + (0, 0, 6 mm).
Mount orientation about the face normal (the C3 "position" chosen in the CAD gates) is
rho_k = angle(face vertex k) - 90 deg; the quadruped uses the gate-approved positions.

Meshes: mjcf_pack/mesh/v50_{mount,conn1,conn2,foot,motor,body}.stl (mm; exported from the
"ICOS Leg v50" design, decimated for the web). Collision geoms, sites, sensors and actuators are dropped:
these files exist only for forward kinematics + rendering (mjcf_to_glb.py --variant v50vis).
"""
import argparse, copy, os, sys
import numpy as np
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.environ.get("ICOS_MJCF_PACK", os.path.join(HERE, "..", "..", "mjcf_pack", "mjcf"))
MORPHS = ["quadruped", "tripod", "mixed", "hexapod",
          "g0_444_0", "g0_444_1", "g0_3333_0", "g0_3333_1", "g0_4332_0", "g0_4332_1", "g0_4422_0", "g0_4422_1",
          "g0_42222_0", "g0_42222_1", "g0_33222_0", "g0_33222_1", "g0_222222_0", "g0_222222_1"]

# icosahedron used by the v50 assembly (mm; circumradius 80.08 = the ICOS body), face order = face ids
ICO_V = np.array([[-42.1, 68.119, 0.0], [-68.119, 0.0, 42.1], [0.0, 42.1, 68.119], [42.1, 68.119, 0.0],
                  [0.0, 42.1, -68.119], [-68.119, 0.0, -42.1], [68.119, 0.0, 42.1], [0.0, -42.1, 68.119],
                  [-42.1, -68.119, 0.0], [0.0, -42.1, -68.119], [68.119, 0.0, -42.1], [42.1, -68.119, 0.0]])
ICO_F = np.array([[0, 1, 2], [0, 2, 3], [0, 3, 4], [0, 4, 5], [0, 5, 1], [3, 2, 6], [2, 1, 7], [1, 5, 8], [5, 4, 9], [4, 3, 10], [11, 6, 7], [11, 7, 8], [11, 8, 9], [11, 9, 10], [11, 10, 6], [7, 6, 2], [8, 7, 1], [9, 8, 5], [10, 9, 4], [6, 10, 3]])
QUAD_RHO = {0: -82.2, 3: 82.2, 10: 97.8, 14: 0.0}          # gate-approved C3 positions (ICOS Leg v50)

OFF = 0.006                                                # v50 frame -> MJCF leg frame, along z (m)
J2 = np.array([-0.023, 0.0, 0.083]); J3 = np.array([-0.023, 0.0, 0.203])   # v50 frame (m)
R_MOTOR23 = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]], dtype=float)    # motorT[2], motorT[3] rotation

COLORS = {  # rgba for the web renders (site palette: orange mounts, steel links, graphite motors)
    "v50_mount": "0.93 0.58 0.14 1", "v50_conn1": "0.31 0.49 0.66 1", "v50_conn2": "0.66 0.71 0.77 1",
    "v50_foot": "0.31 0.49 0.66 1", "v50_motor": "0.17 0.19 0.23 1", "v50_body": "0.79 0.81 0.83 1",
}


def quat_to_R(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def R_to_quat(R):
    """rotation matrix -> MuJoCo wxyz quaternion"""
    t = np.trace(R)
    if t > 0:
        s = 0.5 / np.sqrt(t + 1.0); w = 0.25 / s
        x, y, z = (R[2, 1] - R[1, 2]) * s, (R[0, 2] - R[2, 0]) * s, (R[1, 0] - R[0, 1]) * s
    else:
        i = int(np.argmax(np.diag(R))); j, k = (i + 1) % 3, (i + 2) % 3
        s = 2.0 * np.sqrt(1.0 + R[i, i] - R[j, j] - R[k, k])
        q = np.zeros(4); q[i + 1] = 0.25 * s
        q[0] = (R[k, j] - R[j, k]) / s; q[j + 1] = (R[j, i] + R[i, j]) / s; q[k + 1] = (R[k, i] + R[i, k]) / s
        w, x, y, z = q
    q = np.array([w, x, y, z]); return q / np.linalg.norm(q)


def Rz(deg):
    c, s = np.cos(np.radians(deg)), np.sin(np.radians(deg))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def fmt(v):
    return " ".join(f"{x:.5f}" for x in v)


def face_of(pos):
    n = np.array(pos) / np.linalg.norm(pos)
    c = np.array([ICO_V[f].mean(axis=0) for f in ICO_F]); c /= np.linalg.norm(c, axis=1, keepdims=True)
    fid = int(np.argmax(c @ n)); assert c[fid] @ n > 0.999, "leg frame is not on an icosahedron face"
    return fid


def rho_for(fid, R_leg, k=0):
    c = ICO_V[ICO_F[fid]].mean(axis=0)
    d = R_leg.T @ (ICO_V[ICO_F[fid][k]] - c)
    return np.degrees(np.arctan2(d[1], d[0])) - 90.0


def geom(mesh, pos, quat=None):
    # nominal mass: MuJoCo refuses massless moving bodies (only kinematics are used from these files)
    g = ET.Element("geom", {"class": "visual", "mesh": mesh, "material": mesh + "_mat", "pos": fmt(pos), "mass": "0.05"})
    if quat is not None:
        g.set("quat", fmt(quat))
    return g


def convert(R, verbose=True):
    src = os.path.join(PACK, f"{R}_mjx_hw7.xml")
    tree = ET.parse(src); root = tree.getroot()
    root.set("model", f"{R}_v50vis")
    for tag in ("actuator", "sensor", "contact", "equality", "tendon"):
        for e in root.findall(tag):
            root.remove(e)
    asset = root.find("asset")
    for e in list(asset):
        asset.remove(e)
    for name, rgba in COLORS.items():
        ET.SubElement(asset, "material", {"name": name + "_mat", "rgba": rgba})
        ET.SubElement(asset, "mesh", {"name": name, "file": name + ".stl", "scale": "0.001 0.001 0.001"})

    bodies = {b.get("name"): b for b in root.iter("body")}
    body = bodies["body"]
    for e in list(body):
        if e.tag in ("geom", "site"):
            body.remove(e)
    body.append(geom("v50_body", [0, 0, 0]))
    legs = [b for b in body.findall("body") if b.get("name", "").startswith("leg_")]
    q_m23 = R_to_quat(R_MOTOR23)
    for leg in legs:
        p = np.array([float(x) for x in leg.get("pos").split()])
        q = np.array([float(x) for x in leg.get("quat").split()])
        Rl = quat_to_R(q)
        fid = face_of(p)
        rho = QUAD_RHO[fid] if (R == "quadruped" and fid in QUAD_RHO) else rho_for(fid, Rl, 0)
        p0 = p + Rl @ np.array([0, 0, OFF])                 # v50 leg origin in the body frame
        q_st = R_to_quat(Rl @ Rz(rho))                      # stator parts turn with the mount position
        body.append(geom("v50_mount", p0, q_st))
        body.append(geom("v50_motor", p0, q_st))
        # leg_N (J1): conn1 + motor 2
        for e in list(leg):
            if e.tag in ("geom", "site"):
                leg.remove(e)
        seg1 = leg.find("body"); seg2 = seg1.find("body")
        for e in list(seg1):
            if e.tag in ("geom", "site"):
                seg1.remove(e)
        for e in list(seg2):
            if e.tag in ("geom", "site"):
                seg2.remove(e)
        # geoms first, then the child body (MuJoCo does not care, keeps the file readable)
        ins = list(leg).index(seg1)
        leg.insert(ins, geom("v50_conn1", [0, 0, OFF]))
        leg.insert(ins + 1, geom("v50_motor", J2 + [0, 0, OFF], q_m23))
        ins = list(seg1).index(seg2)
        seg1.insert(ins, geom("v50_conn2", [0, 0, -J2[2]]))            # seg1 origin = v50 (0,0,83)
        seg1.insert(ins + 1, geom("v50_motor", J3 - [0, 0, J2[2]], q_m23))
        seg2.append(geom("v50_foot", [0, 0, -J3[2]]))                  # seg2 origin = v50 (0,0,203)
        if verbose:
            print(f"  {R}: {leg.get('name')} -> face {fid}, rho {rho:+.1f} deg")
    out = os.path.join(PACK, f"{R}_mjx_v50vis.xml")
    ET.indent(tree, space="  ")
    tree.write(out, encoding="unicode")
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--only", nargs="*", default=None)
    a = p.parse_args()
    for R in (a.only or MORPHS):
        print("wrote", convert(R))


if __name__ == "__main__":
    main()
