#!/usr/bin/env python3
"""MJCF (+ recorded trajectories) -> self-contained GLB for the project website.

  python mjcf_to_glb.py --robot quadruped --space fabricable \
      --clip flat=videos/quadruped_r4d2_hw7s2r_hw7_traj.npz \
      --clip rubble=videos/quadruped_r4d2_hw7s2r_hw7_noise30_traj.npz \
      --out ../models/quadruped_fab.glb

What it does
  * compiles the robot MJCF with MuJoCo, keeps the *visual* geoms (group 2), decimates every
    unique mesh to --faces triangles (fast_simplification), converts primitives to meshes;
  * one glTF node per MuJoCo body (world pose), one child node per geom (local pose);
  * for each --clip label=traj.npz (written by genesis_rl/record_icos.py: base_pos, base_quat
    (wxyz), dof_pos in qpos order, dt) it runs MuJoCo forward kinematics per frame and writes a
    glTF animation named `label` (25 Hz, LINEAR) that drives the body nodes;
  * a root node rotates MuJoCo's Z-up world into glTF's Y-up;
  * a sidecar JSON (same stem) carries per-clip displacement curves and metadata for the UI.

No Genesis needed: only mujoco, numpy, trimesh, open3d (decimation).
"""
import argparse, json, os, struct, sys
import numpy as np
import mujoco
import trimesh

try:
    import open3d as o3d
except ImportError:
    o3d = None

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.environ.get("ICOS_MJCF_PACK", os.path.join(HERE, "..", "..", "mjcf_pack", "mjcf"))
ANIM_HZ = 25.0
ZUP_TO_YUP = (-0.70710678, 0.0, 0.0, 0.70710678)     # glTF xyzw: -90 deg about X


# ----------------------------------------------------------------------------- geometry
def geom_mesh(m, g, faces_target):
    """Return (vertices Nx3 float32, faces Mx3 uint32) in the geom's local frame."""
    t = m.geom_type[g]
    if t == mujoco.mjtGeom.mjGEOM_MESH:
        mid = m.geom_dataid[g]
        va, vn = m.mesh_vertadr[mid], m.mesh_vertnum[mid]
        fa, fn = m.mesh_faceadr[mid], m.mesh_facenum[mid]
        v = np.array(m.mesh_vert[va:va + vn], dtype=np.float64)
        f = np.array(m.mesh_face[fa:fa + fn], dtype=np.int64)
        if o3d is not None and fn > faces_target:
            mesh = o3d.geometry.TriangleMesh(o3d.utility.Vector3dVector(v), o3d.utility.Vector3iVector(f))
            mesh.remove_duplicated_vertices(); mesh.remove_degenerate_triangles()
            mesh = mesh.simplify_quadric_decimation(target_number_of_triangles=faces_target)
            v, f = np.asarray(mesh.vertices), np.asarray(mesh.triangles)
        return v.astype(np.float32), f.astype(np.uint32)
    s = m.geom_size[g]
    if t == mujoco.mjtGeom.mjGEOM_SPHERE:
        tm = trimesh.creation.icosphere(subdivisions=2, radius=float(s[0]))
    elif t == mujoco.mjtGeom.mjGEOM_BOX:
        tm = trimesh.creation.box(extents=2.0 * s[:3])
    elif t == mujoco.mjtGeom.mjGEOM_CYLINDER:
        tm = trimesh.creation.cylinder(radius=float(s[0]), height=2.0 * float(s[1]), sections=32)
    elif t == mujoco.mjtGeom.mjGEOM_CAPSULE:
        tm = trimesh.creation.capsule(radius=float(s[0]), height=2.0 * float(s[1]), count=[12, 12])
    else:
        return None
    return np.asarray(tm.vertices, dtype=np.float32), np.asarray(tm.faces, dtype=np.uint32)


def flat_triangles(v, f):
    """Unindexed triangle soup with flat normals (mechanical parts look right this way)."""
    tri = v[f]                                   # (M,3,3)
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    n /= (np.linalg.norm(n, axis=1, keepdims=True) + 1e-12)
    pos = tri.reshape(-1, 3).astype(np.float32)
    nor = np.repeat(n, 3, axis=0).astype(np.float32)
    return pos, nor


def quat_wxyz_to_xyzw(q):
    return [float(q[1]), float(q[2]), float(q[3]), float(q[0])]


# ----------------------------------------------------------------------------- glb writer
class GLB:
    def __init__(self):
        self.bin = bytearray()
        self.views, self.accs = [], []
        self.gltf = {"asset": {"version": "2.0", "generator": "mjcf_to_glb.py"},
                     "scenes": [{"nodes": []}], "scene": 0, "nodes": [], "meshes": [],
                     "materials": [], "accessors": self.accs, "bufferViews": self.views,
                     "buffers": [], "animations": []}

    def _pad(self):
        while len(self.bin) % 4:
            self.bin.append(0)

    def add_accessor(self, arr, ctype, target=None, minmax=False):
        arr = np.ascontiguousarray(arr)
        self._pad()
        off = len(self.bin)
        self.bin += arr.tobytes()
        view = {"buffer": 0, "byteOffset": off, "byteLength": arr.nbytes}
        if target:
            view["target"] = target
        self.views.append(view)
        comp = {np.dtype("float32"): 5126, np.dtype("uint32"): 5125, np.dtype("uint16"): 5123}[arr.dtype]
        acc = {"bufferView": len(self.views) - 1, "componentType": comp,
               "count": int(arr.shape[0]), "type": ctype}
        if minmax:
            acc["min"] = [float(x) for x in arr.min(axis=0).reshape(-1)]
            acc["max"] = [float(x) for x in arr.max(axis=0).reshape(-1)]
        self.accs.append(acc)
        return len(self.accs) - 1

    def add_material(self, rgba, metallic=0.1, rough=0.6):
        self.gltf["materials"].append({
            "pbrMetallicRoughness": {"baseColorFactor": [float(x) for x in rgba],
                                     "metallicFactor": metallic, "roughnessFactor": rough},
            "doubleSided": True})
        return len(self.gltf["materials"]) - 1

    def add_mesh(self, pos, nor, material):
        p = self.add_accessor(pos, "VEC3", 34962, minmax=True)
        n = self.add_accessor(nor, "VEC3", 34962)
        self.gltf["meshes"].append({"primitives": [{"attributes": {"POSITION": p, "NORMAL": n},
                                                    "material": material}]})
        return len(self.gltf["meshes"]) - 1

    def add_node(self, name, translation=None, rotation=None, mesh=None, children=None):
        node = {"name": name}
        if translation is not None:
            node["translation"] = [float(x) for x in translation]
        if rotation is not None:
            node["rotation"] = [float(x) for x in rotation]
        if mesh is not None:
            node["mesh"] = mesh
        if children:
            node["children"] = children
        self.gltf["nodes"].append(node)
        return len(self.gltf["nodes"]) - 1

    def add_animation(self, name, times, tracks):
        """tracks: {node_index: (translations Tx3, rotations_xyzw Tx4)}"""
        t_acc = self.add_accessor(np.asarray(times, dtype=np.float32), "SCALAR", minmax=True)
        samplers, channels = [], []
        for node, (tr, rot) in tracks.items():
            a_tr = self.add_accessor(np.asarray(tr, dtype=np.float32), "VEC3")
            a_rot = self.add_accessor(np.asarray(rot, dtype=np.float32), "VEC4")
            for path, acc in (("translation", a_tr), ("rotation", a_rot)):
                samplers.append({"input": t_acc, "output": acc, "interpolation": "LINEAR"})
                channels.append({"sampler": len(samplers) - 1, "target": {"node": node, "path": path}})
        self.gltf["animations"].append({"name": name, "samplers": samplers, "channels": channels})

    def write(self, path):
        self._pad()
        self.gltf["buffers"] = [{"byteLength": len(self.bin)}]
        js = json.dumps(self.gltf, separators=(",", ":")).encode()
        while len(js) % 4:
            js += b" "
        total = 12 + 8 + len(js) + 8 + len(self.bin)
        with open(path, "wb") as f:
            f.write(struct.pack("<III", 0x46546C67, 2, total))
            f.write(struct.pack("<II", len(js), 0x4E4F534A)); f.write(js)
            f.write(struct.pack("<II", len(self.bin), 0x004E4942)); f.write(bytes(self.bin))
        return total


# ----------------------------------------------------------------------------- main build
def keyframe_qpos(scene_xml):
    """Read the `home` keyframe qpos from a scene XML without compiling it (includes may be stale)."""
    import xml.etree.ElementTree as ET
    root = ET.parse(scene_xml).getroot()
    for k in root.iter("key"):
        return np.array([float(x) for x in k.get("qpos").split()])
    return None


def build(robot_xml, scene_xml, clips, out, faces_target=1500):
    m = mujoco.MjModel.from_xml_path(robot_xml)
    d = mujoco.MjData(m)
    glb = GLB()

    # materials keyed by rgba
    mat_cache = {}
    def material(rgba):
        k = tuple(np.round(rgba, 3))
        if k not in mat_cache:
            mat_cache[k] = glb.add_material(rgba)
        return mat_cache[k]

    # unique geometry keyed by (type, mesh id or size)
    def geom_rgba(g):
        mid = int(m.geom_matid[g])
        return m.mat_rgba[mid] if mid >= 0 else m.geom_rgba[g]

    mesh_cache = {}
    def mesh_for(g):
        t = int(m.geom_type[g])
        key = (t, int(m.geom_dataid[g])) if t == mujoco.mjtGeom.mjGEOM_MESH else (t, tuple(np.round(m.geom_size[g], 5)))
        key = key + (material(geom_rgba(g)),)
        if key not in mesh_cache:
            vf = geom_mesh(m, g, faces_target)
            if vf is None:
                mesh_cache[key] = None
            else:
                pos, nor = flat_triangles(*vf)
                mesh_cache[key] = glb.add_mesh(pos, nor, key[-1])
        return mesh_cache[key]

    # nodes: body nodes (animated) with geom children
    body_nodes = {}
    for b in range(1, m.nbody):
        children = []
        for g in range(m.ngeom):
            if m.geom_bodyid[g] != b or m.geom_group[g] != 2:
                continue
            mesh = mesh_for(g)
            if mesh is None:
                continue
            children.append(glb.add_node(f"geom_{m.geom(g).name or g}", m.geom_pos[g],
                                         quat_wxyz_to_xyzw(m.geom_quat[g]), mesh=mesh))
        body_nodes[b] = glb.add_node(m.body(b).name, children=children)

    # rest pose = home keyframe if available, else qpos0
    q0 = keyframe_qpos(scene_xml) if scene_xml and os.path.exists(scene_xml) else None
    if q0 is None or len(q0) != m.nq:
        q0 = m.qpos0.copy()

    def fk(qpos):
        d.qpos[:] = qpos
        mujoco.mj_kinematics(m, d)
        return d.xpos.copy(), d.xquat.copy()

    xp, xq = fk(q0)
    for b, n in body_nodes.items():
        glb.gltf["nodes"][n]["translation"] = [float(x) for x in xp[b]]
        glb.gltf["nodes"][n]["rotation"] = quat_wxyz_to_xyzw(xq[b])
    root = glb.add_node("mujoco_world_Zup_to_Yup", rotation=ZUP_TO_YUP, children=list(body_nodes.values()))
    glb.gltf["scenes"][0]["nodes"] = [root]

    # animations
    meta = {"robot": os.path.basename(robot_xml), "bodies": [m.body(b).name for b in body_nodes],
            "nq": int(m.nq), "clips": {}}
    for label, npz in clips:
        tr = np.load(npz)
        bp, bq, dp, dt = tr["base_pos"], tr["base_quat"], tr["dof_pos"], float(tr["dt"])
        assert dp.shape[1] == m.nq - 7, f"{npz}: {dp.shape[1]} dofs but model has {m.nq - 7}"
        step = max(1, int(round(1.0 / (ANIM_HZ * dt))))
        idx = np.arange(0, len(bp), step)
        times = idx * dt
        tracks = {n: ([], []) for n in body_nodes.values()}
        for i in idx:
            q = np.concatenate([bp[i], bq[i], dp[i]])
            xp, xq = fk(q)
            for b, n in body_nodes.items():
                tracks[n][0].append(xp[b]); tracks[n][1].append(quat_wxyz_to_xyzw(xq[b]))
        glb.add_animation(label, times, tracks)
        disp = np.linalg.norm(bp[:, :2] - bp[0, :2], axis=1)
        meta["clips"][label] = {
            "npz": os.path.basename(npz), "dt": dt, "frames": int(len(bp)), "seconds": float(len(bp) * dt),
            "terrain": {"kind": str(tr["terrain_kind"]), "amp": float(tr["terrain_amp"]), "seed": int(tr["terrain_seed"])},
            "displacement_final_m": float(disp[-1]), "displacement_max_m": float(disp.max()),
            "displacement_curve": [round(float(x), 3) for x in disp[::step]],
            "start_xy": [float(bp[0, 0]), float(bp[0, 1])],
            "path_xy": [[round(float(x), 3), round(float(y), 3)] for x, y in bp[::step, :2]],
        }
    size = glb.write(out)
    json.dump(meta, open(os.path.splitext(out)[0] + ".json", "w"), indent=0)
    print(f"{os.path.basename(out)}: {size/1e6:.2f} MB, {len(glb.gltf['meshes'])} unique meshes, "
          f"{len(body_nodes)} bodies, clips={[c[0] for c in clips]}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--robot", required=True, help="quadruped / g0_444_0 / ...")
    p.add_argument("--space", choices=["fabricable", "abstract"], default="fabricable")
    p.add_argument("--clip", action="append", default=[], help="label=path/to/traj.npz (repeatable)")
    p.add_argument("--out", required=True)
    p.add_argument("--faces", type=int, default=1500, help="triangle budget per unique mesh")
    p.add_argument("--variant", default="hw7",
                   help="fabricable robot XML suffix: hw7 (trained model) or v50vis (same kinematics, current CAD visuals)")
    p.add_argument("--abs-variant", default="sci",
                   help="abstract robot XML: sci (the science files, partA/partB meshes) or absvis (capsule + sphere proxies)")
    a = p.parse_args()
    if a.space == "fabricable":
        robot_xml = os.path.join(PACK, f"{a.robot}_mjx_{a.variant}.xml")
        scene_xml = os.path.join(PACK, f"scene_mjx_{a.robot}_flat_terrain_hw7.xml")   # home keyframe of the trained model
    else:   # abstract / science line: the live quadruped file is the hardware one, use the sci backup
        if a.abs_variant == "sci":
            robot_xml = os.path.join(PACK, "quadruped_mjx_sci.xml" if a.robot == "quadruped" else f"{a.robot}_mjx.xml")
        else:   # e.g. absvis: same skeleton drawn as capsules + joint spheres (make_abs_visuals.py)
            robot_xml = os.path.join(PACK, f"{a.robot}_mjx_{a.abs_variant}.xml")
        scene_xml = os.path.join(PACK, f"scene_mjx_{a.robot}_flat_terrain.xml")
    clips = [tuple(c.split("=", 1)) for c in a.clip]
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    build(robot_xml, scene_xml, clips, a.out, a.faces)


if __name__ == "__main__":
    main()
