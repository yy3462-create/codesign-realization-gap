#!/usr/bin/env python3
"""Export the training terrains for the web viewer.

rubble: the exact heightfield genesis_rl/icos_env.py builds for --terrain noise --terrain_amp 0.03
        (seed 0 is shared by every rubble run), 28 m x 28 m at 0.05 m, quantised plateaus.
        Written as ../models/terrain_rubble.json  {n, hs, origin, z_mm: [...row-major int...]}.
stones: the Isaac-style stepping-stone field is generated with numpy's *global* RNG inside Genesis,
        so the exact layout of a training run is not recoverable; we export an illustrative field
        with the same stone size (0.25 m after cell truncation), 50 mm gaps, ±5 mm stone heights,
        a 0.5 m central platform and 0.5 m deep holes (the fallback plane sat at z = -0.5 m).
"""
import json, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "models")


def make_noise_hf(n, amp, seed=0, quantize=0.4):          # verbatim from genesis_rl/icos_env.py
    rng = np.random.default_rng(seed)

    def up(g, n):
        m = g.shape[0]
        xi = np.linspace(0, m - 1, n)
        i0 = np.clip(np.floor(xi).astype(int), 0, m - 2)
        t = xi - i0
        a = g[i0, :] * (1 - t)[:, None] + g[i0 + 1, :] * t[:, None]
        return a[:, i0] * (1 - t)[None, :] + a[:, i0 + 1] * t[None, :]

    hf = sum(up(rng.standard_normal((2 ** (o + 4) + 1,) * 2), n) * (0.7 ** o) for o in range(5))
    hf = hf / (np.abs(hf).max() + 1e-9) * amp
    if quantize > 0:
        q = amp * quantize
        hf = np.round(hf / q) * q
    return hf


def rubble(size=28.0, hs=0.05, amp=0.03, seed=0):
    n = max(int(size / hs), 32)
    hf = make_noise_hf(n, amp, seed)
    xx = (np.arange(n) + 0.5) * hs - size / 2
    X, Y = np.meshgrid(xx, xx, indexing="ij")
    hf *= np.clip((np.hypot(X, Y) - 0.7) / 0.8, 0.0, 1.0)      # flattened spawn disc
    hf -= hf.min()
    hf = hf + 0.03                                              # raised 3 cm above the fallback plane
    return {"kind": "rubble", "n": n, "hs": hs, "origin": -size / 2, "amp": amp, "seed": seed,
            "z_mm": [int(round(v * 1000)) for v in hf.ravel()]}   # hf[ix, iy], x = origin + (ix+0.5)*hs


def stones(field=18.0, hs=0.05, stone=0.30, gap=0.05, max_h=0.01, platform=0.5, depth=-0.5, seed=0):
    rng = np.random.default_rng(seed)
    n = int(field / hs)
    stone_c, gap_c, plat_c = int(stone / hs), int(gap / hs), int(platform / hs)
    hr = np.arange(-int(max_h / 0.005) - 1, int(max_h / 0.005)) * 0.005      # Isaac height_range in 5 mm units
    z = np.full((n, n), depth)
    y = 0
    while y < n:
        y1 = min(n, y + stone_c)
        x = int(rng.integers(0, stone_c))
        x0 = max(0, x - gap_c)
        z[0:x0, y:y1] = rng.choice(hr)
        while x < n:
            x1 = min(n, x + stone_c)
            z[x:x1, y:y1] = rng.choice(hr)
            x += stone_c + gap_c
        y += stone_c + gap_c
    c = n // 2
    z[c - plat_c // 2:c + plat_c // 2, c - plat_c // 2:c + plat_c // 2] = 0.0
    z = z + 0.03
    return {"kind": "stones", "n": n, "hs": hs, "origin": -field / 2, "illustrative": True,
            "note": "layout regenerated with a fixed seed; the training run's random offsets are not recoverable",
            "z_mm": [int(round(v * 1000)) for v in z.ravel()]}


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("terrain_rubble.json", rubble), ("terrain_stones.json", stones)):
        d = fn()
        json.dump(d, open(os.path.join(OUT, name), "w"), separators=(",", ":"))
        zs = np.array(d["z_mm"])
        print(f"{name}: {d['n']}x{d['n']} cells, z {zs.min()}..{zs.max()} mm, {os.path.getsize(os.path.join(OUT, name))/1e6:.2f} MB")
