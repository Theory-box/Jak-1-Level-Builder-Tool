# ---------------------------------------------------------------------------
# level_counts.py — OpenGOAL Level Tools
# How many orbs a level holds (its progress page's orb count), from the lumps
# each actor exports (DB fields + custom lump rows), so it follows every
# setting:
#   money                1 (or its eco-info)
#   eco-info money N     N   crates, pickup-spawner, enemies with Change Drop,
#                            swamp-rat-nest ... (an actor's drop / contents)
#   orb-cache-top        orb-cache-count (20)
#   plant-boss           5 (bounces after the fight)
#   sunken-pipegame      1 per button whose prize is money (prize-type 5)
#   gnawer               extra-count [5, N]: N
#   battlecontroller     normal drop money: 1 per lurker but the last
#                        (num-lurkers total), final pickup money: +1;
#                        the per-lurker special drops are random (not counted)
# Level > Settings > Gameplay > Orb count (blank = this count) overrides it.
# ---------------------------------------------------------------------------
from __future__ import annotations

from .collections import is_actor
import bpy

_MONEY = "(pickup-type money)"


def _lumps(o, etype):
    """The schema lumps the export writes for o, custom lump rows on top."""
    from . import db as _db
    from .export.schema_emit import emit_schema_lumps
    from .data import _parse_lump_row
    lump = dict(emit_schema_lumps(_db.prop_getter(o), _db.inherited_fields(etype), etype=etype,
                                  choice_tables={"CratePickups": _db.crate_pickups()}))
    for row in getattr(o, "og_lump_rows", []):
        value, err = _parse_lump_row(row.key, row.ltype, row.value)
        if not err:
            lump[row.key.strip()] = value
    return lump


def _num(v, i=1, default=0):
    try:
        return int(float(v[i])) if isinstance(v, (list, tuple)) and len(v) > i else int(float(v))
    except (TypeError, ValueError):
        return default


def actor_orbs(o) -> int:
    """Orbs one actor puts in the level."""
    etype = o.name.split("_", 2)[1]
    lump = _lumps(o, etype)
    ei = lump.get("eco-info")
    eco = (_num(ei, 2, 1) if isinstance(ei, (list, tuple)) and len(ei) > 1 and str(ei[1]) == _MONEY else 0)
    if etype == "money":
        return eco if ei is not None else 1
    if etype == "orb-cache-top":
        return _num(lump.get("orb-cache-count", 20), 1, 20)
    if etype == "plant-boss":
        return 5
    if etype == "gnawer":
        ec = lump.get("extra-count")
        return _num(ec, 2) if isinstance(ec, (list, tuple)) and len(ec) > 2 and _num(ec, 1) == 5 else 0
    if etype == "battlecontroller" or o.get("og_bc_drop") is not None:
        n = 0
        if eco:
            total = lump.get("num-lurkers")
            n += max(_num(total, 2, 0) - 1, 0) if isinstance(total, (list, tuple)) and len(total) > 2 else 0
        if o.get("og_bc_end_pickup", True) and str(o.get("og_bc_final_pickup", "")) == "money":
            n += 1
        return n
    n = eco
    for k in ("prize-type-a", "prize-type-b", "prize-type-c"):
        if k in lump and _num(lump[k]) == 5:
            n += 1
    return n


def auto_orbs(level_col) -> int:
    from .collections import _recursive_col_objects
    n = 0
    for o in _recursive_col_objects(level_col, exclude_no_export=True):
        if is_actor(o):
            try:
                n += actor_orbs(o)
            except Exception:
                pass
    level_col["og_orb_count_auto"] = n               # shown next to the Orb count field
    return n


def level_orbs(level_col) -> int:
    """The orb count to export: the typed one, else the automatic count."""
    v = level_col.og_level.orb_count.strip() if hasattr(level_col, "og_level") else ""
    if v.isdigit():
        return int(v)
    return auto_orbs(level_col)


class OG_OT_CountOrbs(bpy.types.Operator):
    """Count the orbs of this level's actors (orbs, crates, orb caches, enemy drops, pipe game, plant boss ...)"""
    bl_idname = "og.count_orbs"
    bl_label = "Count Orbs"

    def execute(self, ctx):
        from .collections import _active_level_col
        col = _active_level_col(ctx.scene)
        if col is None:
            return {"CANCELLED"}
        self.report({"INFO"}, f"{col.name}: {auto_orbs(col)} orbs")
        return {"FINISHED"}


CLASSES = (OG_OT_CountOrbs,)
