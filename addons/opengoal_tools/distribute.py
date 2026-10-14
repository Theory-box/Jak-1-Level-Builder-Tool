# ---------------------------------------------------------------------------
# distribute.py — OpenGOAL Level Tools
# Sync panel option "distribute" (DB, on plat and so its children): export
# this platform N times on its path, evenly spread in time. Copy i (1..N-1)
# is the same actor with phase (A + i / N) wrapped to 0-1, A = its own phase.
# ---------------------------------------------------------------------------
from __future__ import annotations

import copy
import bpy

from . import db as _db


def enabled(o, etype) -> bool:
    return bool(_db.panel_option(etype, "sync", "distribute", False)) and bool(getattr(o, "og_distribute", False))


def phases(a: float, n: int) -> list:
    return [round((a + i / n) % 1.0, 6) for i in range(n)]


def draw(layout, o):
    box = layout.box()
    box.prop(o, "og_distribute")
    if not o.og_distribute:
        return
    box.prop(o, "og_distribute_count")
    a = float(o.get("og_sync_phase", 0.0))
    col = box.column(); col.scale_y = 0.8
    col.label(text="Phases: " + ", ".join(f"{p:.2f}" for p in phases(a, o.og_distribute_count)), icon="TIME")
    col.label(text="Copies share every other setting and the path")


def entities(o, base: dict) -> list:
    """The extra platforms (the original stays as it is)."""
    n = int(o.og_distribute_count)
    sync = base["lump"].get("sync")
    if n < 2 or not sync or len(sync) < 3:
        return []
    out = []
    for i, ph in enumerate(phases(float(sync[2]), n)[1:], start=1):
        e = copy.deepcopy(base)
        e["lump"]["name"] = f"{base['lump']['name']}-{i}"
        e["lump"]["sync"][2] = ph
        out.append(e)
    return out


def register_props():
    T = bpy.types.Object
    T.og_distribute = bpy.props.BoolProperty(
        name="Distribute along the path", default=False,
        description="Export this platform several times on its path, evenly spread in time (phase)")
    T.og_distribute_count = bpy.props.IntProperty(
        name="Platforms", default=2, min=2, max=32,
        description="How many platforms in total (this one included)")


def unregister_props():
    for a in ("og_distribute", "og_distribute_count"):
        try: delattr(bpy.types.Object, a)
        except Exception: pass
