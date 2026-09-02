# Optional env-var override for the abstract-space quadruped

`logs/icos_quadruped_r4d2_d25m/cfgs.pkl` stores `mjcf_file = .../mjcf_pack/mjcf/quadruped_mjx.xml`.
That file was overwritten by the hardware line on 2026-07-18; the science-line model the run was
trained on survives as `quadruped_mjx_sci.xml`. Both `record_icos.py` and `eval_honest.py` rebuild the
environment from `cfgs.pkl`, so for this one run they would silently load the wrong body.

Add these three lines right after the `pickle.load(...)` of `cfgs.pkl` in both scripts:

```python
    _ov = os.environ.get("ICOS_MJCF_OVERRIDE")          # e.g. quadruped_mjx_sci.xml
    if _ov:
        env_cfg["mjcf_file"] = _ov if os.path.isabs(_ov) else os.path.join(HERE, "..", "mjcf_pack", "mjcf", _ov)
        env_cfg["robot_xml"] = None
        print(f"[override] mjcf_file -> {env_cfg['mjcf_file']}")
```

Then:

```bash
ICOS_MJCF_OVERRIDE=quadruped_mjx_sci.xml python record_icos.py --seconds 20 --tag d25m --robots quadruped
mv videos/quadruped_r4d2_d25m_traj.npz videos/quadruped_r4d2_d25m_sci_traj.npz   # name the builder expects
ICOS_MJCF_OVERRIDE=quadruped_mjx_sci.xml python eval_honest.py --exp icos_quadruped_r4d2_d25m
```

(`eval_honest.py` defines `here` in lower case — use that name there.)
