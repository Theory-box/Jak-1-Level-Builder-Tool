# ---------------------------------------------------------------------------
# plat_grid.py — OpenGOAL Level Tools
# DB panel "plat-grid": a grid of platforms spawned by one actor
# (citb-drop-plat). The game reads
#   'count     int32 [x-count z-count]
#   'plat-type int8 per platform, index x + z * x-count (0 = none, 1-5 colours);
#              without it every slot is random 0-5
# The platforms sit 4 m apart, centred on the actor, x along the actor's X and
# z along its game Z (Blender -Y). goalc has no int8 lump type, so plat-type is
# written as int32 words holding 4 bytes each (little endian: the bytes come
# out in index order).
# ---------------------------------------------------------------------------
from __future__ import annotations

import bpy
import mathutils

SPACING = 4.0   # m (16384 game units)

# value -> (label, icon, model)
TYPES = (
    ("None",   "X",                None),
    ("Red",    "COLORSET_01_VEC",  "levels/citadel/citb-drop-plat-red-lod0.glb"),
    ("Green",  "COLORSET_03_VEC",  "levels/citadel/citb-drop-plat-green-lod0.glb"),
    ("Blue",   "COLORSET_04_VEC",  "levels/citadel/citb-drop-plat-blue-lod0.glb"),
    ("Yellow", "COLORSET_09_VEC",  "levels/citadel/citb-drop-plat-yellow-lod0.glb"),
    ("Plain",  "COLORSET_13_VEC",  "levels/citadel/citb-drop-plat-lod0.glb"),
)
_MODES = (("random", "Random", "Every slot gets a random type (0-5) each time the platforms spawn"),
          ("custom", "Custom", "Set each platform yourself"))


def dims(o):
    return max(1, int(o.og_grid_x)), max(1, int(o.og_grid_z))


def _parse(o):
    """Stored types: "nx,nz:v,v,..." -> (nx, nz, [values])."""
    s = str(o.get("og_grid_types", ""))
    try:
        head, vals = s.split(":")
        nx, nz = (int(x) for x in head.split(","))
        v = [int(x) for x in vals.split(",")] if vals else []
        if len(v) == nx * nz:
            return nx, nz, v
    except ValueError:
        pass
    return 0, 0, []


def types(o):
    """One value per slot (index x + z * nx) for the current counts; slots
    kept by position when the counts change, new ones Plain."""
    nx, nz = dims(o)
    ox, oz, old = _parse(o)
    return [old[x + z * ox] if (x < ox and z < oz) else 5 for z in range(nz) for x in range(nx)]


def set_types(o, vals):
    nx, nz = dims(o)
    o["og_grid_types"] = f"{nx},{nz}:" + ",".join(str(int(v)) for v in vals)


def lumps(o):
    nx, nz = dims(o)
    out = {"count": ["int32", nx, nz]}
    if o.og_grid_mode == "custom":
        b = bytes(int(v) & 0xFF for v in types(o))
        b += bytes(-len(b) % 4)
        words = [int.from_bytes(b[i:i + 4], "little", signed=True) for i in range(0, len(b), 4)]
        out["plat-type"] = ["int32", *words]
    return out


def slot_offset(o, x, z):
    """Blender local offset of slot (x, z) from the actor."""
    nx, nz = dims(o)
    gx = (x - (nx - 1) / 2) * SPACING
    gz = (z - (nz - 1) / 2) * SPACING
    return mathutils.Vector((gx, -gz, 0.0))


# ── Preview ────────────────────────────────────────────────────────────────

def build_preview(ctx, o) -> bool:
    """One platform model per slot (Plain models for Random)."""
    from . import model_preview as mp
    col = mp._ensure_preview_collection(ctx.scene)
    nx, nz = dims(o)
    vals = types(o) if o.og_grid_mode == "custom" else [5] * (nx * nz)
    made = []
    for i, v in enumerate(vals):
        rel = TYPES[v][2]
        if not rel:
            continue
        m = mp._reuse_or_import(ctx, mp._glb_path(rel), rel.rsplit("/", 1)[1][:-4])
        if m is None:
            continue
        for c in list(m.users_collection):
            c.objects.unlink(m)
        col.objects.link(m)
        m.name = f"{o.name}_preview"
        m.parent = o
        m.matrix_parent_inverse = mathutils.Matrix()
        m.location = slot_offset(o, i % nx, i // nx)
        m[mp._PREVIEW_PROP] = True
        m.display_type = "TEXTURED" if o.og_grid_mode == "custom" else "WIRE"
        m.hide_select = not mp._select_via_preview()
        made.append(m)
    o.empty_display_size = max(nx, nz) * SPACING / 2
    return bool(made)


def refresh(ctx, o):
    prefs = ctx.preferences.addons.get("opengoal_tools")
    if not (prefs and prefs.preferences.preview_models):
        return
    from . import model_preview as mp
    mp.remove_preview(o)
    build_preview(ctx, o)


def _upd(self, ctx):
    if self.name.startswith("ACTOR_"):
        set_types(self, types(self))   # keep the stored grid in step with the counts
        refresh(ctx, self)


# ── UI ─────────────────────────────────────────────────────────────────────

def draw(layout, o):
    note = layout.column(); note.scale_y = 0.75
    note.label(text="Spawns its platforms on a 'trigger:", icon="INFO")
    note.label(text="      link it from a button or a trigger volume")
    row = layout.row(align=True)
    row.prop(o, "og_grid_x", text="Count X")
    row.prop(o, "og_grid_z", text="Count Z")
    layout.row().prop(o, "og_grid_mode", expand=True)
    if o.og_grid_mode != "custom":
        layout.label(text="Each slot: random colour or empty", icon="INFO")
        return
    nx, nz = dims(o)
    vals = types(o)
    box = layout.box()
    box.label(text="Platforms (top view; click to change)")
    grid = box.column(align=True)
    for z in range(nz):
        r = grid.row(align=True)
        for x in range(nx):
            i = x + z * nx
            v = vals[i]
            op = r.operator("og.plat_grid_cycle", text=str(v), icon=TYPES[v][1], depress=v != 0)
            op.index = i
    leg = box.column(align=True); leg.scale_y = 0.75
    leg.label(text="  ".join(f"{i} {t[0]}" for i, t in enumerate(TYPES)))
    r = box.row(align=True)
    for v in range(6):
        op = r.operator("og.plat_grid_fill", text="", icon=TYPES[v][1])
        op.value = v


class OG_OT_PlatGridCycle(bpy.types.Operator):
    """Next platform type for this slot (0 none, 1 red, 2 green, 3 blue, 4 yellow, 5 plain)"""
    bl_idname  = "og.plat_grid_cycle"
    bl_label   = "Platform Type"
    bl_options = {"INTERNAL", "UNDO"}

    index: bpy.props.IntProperty()

    def execute(self, ctx):
        o = ctx.active_object
        vals = types(o)
        if 0 <= self.index < len(vals):
            vals[self.index] = (vals[self.index] + 1) % len(TYPES)
            set_types(o, vals)
            refresh(ctx, o)
        return {"FINISHED"}


class OG_OT_PlatGridFill(bpy.types.Operator):
    """Set every slot to this type"""
    bl_idname  = "og.plat_grid_fill"
    bl_label   = "Fill"
    bl_options = {"INTERNAL", "UNDO"}

    value: bpy.props.IntProperty()

    def execute(self, ctx):
        o = ctx.active_object
        set_types(o, [self.value] * len(types(o)))
        refresh(ctx, o)
        return {"FINISHED"}


CLASSES = (OG_OT_PlatGridCycle, OG_OT_PlatGridFill)


def register_props():
    T = bpy.types.Object
    T.og_grid_x = bpy.props.IntProperty(name="Count X", default=3, min=1, max=16, update=_upd,
                                        description="Platforms along the actor's X axis ('count lump)")
    T.og_grid_z = bpy.props.IntProperty(name="Count Z", default=3, min=1, max=16, update=_upd,
                                        description="Rows along the actor's forward axis ('count lump)")
    T.og_grid_mode = bpy.props.EnumProperty(name="Platforms", items=_MODES, default="random", update=_upd)


def unregister_props():
    for a in ("og_grid_x", "og_grid_z", "og_grid_mode"):
        try: delattr(bpy.types.Object, a)
        except Exception: pass
