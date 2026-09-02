#!/usr/bin/env python3
"""Visual-only MJCF variants of the 18 abstract-space (science-line) models, drawn as what that
simulator actually computes with: the icosahedral shell, a capsule per leg segment (r = 10 mm, the
collision proxy) and a sphere at every joint (the lumped joint mass). The science files dress the same
skeleton in an early hardware iteration's meshes (partA/partB + XM430), which is not what the abstract
space is about — and its legs have 2–5 DoF, so the fabricable CAD cannot stand in either.

  python make_abs_visuals.py            # writes ../../mjcf_pack/mjcf/{R}_mjx_absvis.xml for all 18

Kinematics, joint order and the `home` keyframe (scene_mjx_{R}_flat_terrain.xml) are untouched; only
visual geoms change. Quadruped: the science-line file is quadruped_mjx_sci.xml.
"""
import argparse, os
import numpy as np
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.environ.get("ICOS_MJCF_PACK", os.path.join(HERE, "..", "..", "mjcf_pack", "mjcf"))
MORPHS = ["quadruped", "tripod", "mixed", "hexapod",
          "g0_444_0", "g0_444_1", "g0_3333_0", "g0_3333_1", "g0_4332_0", "g0_4332_1", "g0_4422_0", "g0_4422_1",
          "g0_42222_0", "g0_42222_1", "g0_33222_0", "g0_33222_1", "g0_222222_0", "g0_222222_1"]
R_LINK, R_JOINT, R_FOOT = 0.010, 0.0145, 0.012
COLORS = {"abs_shell_mat": "0.79 0.81 0.83 1", "abs_link_mat": "0.70 0.77 0.86 1",
          "abs_joint_mat": "0.17 0.19 0.23 1", "abs_foot_mat": "0.17 0.19 0.23 1"}


def fmt(v):
    return " ".join(f"{x:.5f}" for x in v)


def strip(body):
    for e in list(body):
        if e.tag in ("geom", "site"):
            body.remove(e)


def dress(seg, depth=0):
    """seg: a leg segment body. Its child body (if any) sits at the far end of this segment."""
    child = seg.find("body")
    if child is not None:
        end = np.array([float(x) for x in child.get("pos").split()])
    else:   # last segment: the foot sphere of the science model sits at the same distance as the others
        end = np.array([0.0, 0.0, 0.120])
    strip(seg)
    ins = 1 if seg.find("joint") is not None else 0
    seg.insert(ins, ET.Element("geom", {"class": "visual", "type": "sphere", "size": f"{R_JOINT:.4f}",
                                        "material": "abs_joint_mat", "mass": "0.05"}))
    seg.insert(ins + 1, ET.Element("geom", {"class": "visual", "type": "capsule", "size": f"{R_LINK:.4f}",
                                            "fromto": fmt([0, 0, 0]) + " " + fmt(end), "material": "abs_link_mat", "mass": "0.05"}))
    if child is None:
        seg.insert(ins + 2, ET.Element("geom", {"class": "visual", "type": "sphere", "size": f"{R_FOOT:.4f}", "pos": fmt(end),
                                                "material": "abs_foot_mat", "mass": "0.05"}))
    else:
        dress(child, depth + 1)


def convert(R):
    src = os.path.join(PACK, "quadruped_mjx_sci.xml" if R == "quadruped" else f"{R}_mjx.xml")
    tree = ET.parse(src); root = tree.getroot()
    root.set("model", f"{R}_absvis")
    for tag in ("actuator", "sensor", "contact", "equality", "tendon"):
        for e in root.findall(tag):
            root.remove(e)
    asset = root.find("asset")
    for e in list(asset):
        asset.remove(e)
    for name, rgba in COLORS.items():
        ET.SubElement(asset, "material", {"name": name, "rgba": rgba})
    ET.SubElement(asset, "mesh", {"name": "abs_shell", "file": "v50_body.stl", "scale": "0.001 0.001 0.001"})
    body = next(b for b in root.iter("body") if b.get("name") == "body")
    legs = [b for b in body.findall("body") if b.get("name", "").startswith("leg_")]
    strip(body)
    body.insert([c.tag for c in body].index("body") if legs else len(body),
                ET.Element("geom", {"class": "visual", "mesh": "abs_shell", "material": "abs_shell_mat", "mass": "0.4"}))
    for leg in legs:
        dress(leg)
    out = os.path.join(PACK, f"{R}_mjx_absvis.xml")
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
