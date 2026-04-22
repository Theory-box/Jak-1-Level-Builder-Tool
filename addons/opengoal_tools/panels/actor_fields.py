# ---------------------------------------------------------------------------
# actor_fields.py — OpenGOAL Level Tools
#
# Data-driven per-actor settings panel. Reads the actor's `fields[]` schema
# from the game database (jak1_game_database.jsonc) and draws UI for each
# field automatically. Replaces many of the bespoke OG_PT_Actor* panels.
#
# A field in the DB looks like:
#   {
#     "key":       "og_orbit_scale",
#     "label":     "Orbit scale",
#     "type":      "float" | "int" | "bool" | "enum" | "string" | "vector3",
#     "default":   ...,
#     "lump":      { "key": "scale", "type": "float" },   (informational)
#     "write_if":  "always" | "if_true" | "if_nonzero" | ...,
#     "choices":   [...]  or "CrateTypes" / "GameTasks" / ... (enums only)
#     "visible_if": { other_field_key: expected_value },  (optional)
#     "note":      "Extra info text shown below the input.",  (optional)
#   }
#
# Adding an actor to the generic panel requires:
#   1. Ensure its `fields[]` in the DB matches its existing og_* Blender props
#   2. Add its etype to GENERIC_PANEL_ETYPES below
#   3. Remove its bespoke OG_PT_Actor<X> class from panels.py + __init__.py
# ---------------------------------------------------------------------------
from __future__ import annotations
import bpy
from bpy.types import Operator, Panel
from bpy.props import StringProperty

from .. import db as _db
from ..utils import _prop_row


# ═════════════════════════════════════════════════════════════════════════════
# Generic setter operators — used by the panel to write custom props
# ═════════════════════════════════════════════════════════════════════════════
class OG_OT_SetActorEnumField(Operator):
    """Set a string-valued custom property on the active actor to a specific value."""
    bl_idname = "og.set_actor_enum_field"
    bl_label = "Set Field"
    bl_options = {"INTERNAL", "UNDO"}

    prop_key: StringProperty()
    value: StringProperty()

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            return {"CANCELLED"}
        obj[self.prop_key] = self.value
        return {"FINISHED"}


class OG_OT_ToggleActorBoolField(Operator):
    """Toggle a boolean custom property on the active actor."""
    bl_idname = "og.toggle_actor_bool_field"
    bl_label = "Toggle Field"
    bl_options = {"INTERNAL", "UNDO"}

    prop_key: StringProperty()

    def execute(self, context):
        obj = context.active_object
        if obj is None:
            return {"CANCELLED"}
        current = bool(obj.get(self.prop_key, False))
        obj[self.prop_key] = not current
        return {"FINISHED"}


# ═════════════════════════════════════════════════════════════════════════════
# Resolve `choices` references against the database
# ═════════════════════════════════════════════════════════════════════════════
def _resolve_choices(choices_spec):
    """Turn a `choices` spec into a list of {value, label} dicts.

    Accepted inputs:
      * list of {value, label, ...} dicts  → returned as-is (with optional fields intact)
      * list of plain strings              → normalised into dicts
      * "CrateTypes"                       → db.crate_types()
      * "CratePickups"                     → db.crate_pickups()
      * "GameTasks"                        → db.game_tasks() plus a "none" entry up top
      * "SoundBanks"                       → db.sound_banks()
      * "BankSFX"                          → flattened bank/sfx list
      * anything else → []
    """
    if isinstance(choices_spec, list):
        out = []
        for c in choices_spec:
            if isinstance(c, dict):
                out.append(c)
            else:
                out.append({"value": str(c), "label": str(c)})
        return out

    if isinstance(choices_spec, str):
        if choices_spec == "CrateTypes":
            return [{"value": t["id"], "label": t["label"]} for t in _db.crate_types()]
        if choices_spec == "CratePickups":
            return [{"value": p["id"], "label": p["label"]} for p in _db.crate_pickups()]
        if choices_spec == "GameTasks":
            items = [{"value": "none", "label": "None"}]
            items += [{"value": t["id"], "label": t["label"]} for t in _db.game_tasks()]
            return items
        if choices_spec == "SoundBanks":
            return [{"value": b["id"], "label": b["label"]} for b in _db.sound_banks()]
        if choices_spec == "BankSFX":
            out = []
            for bank, sounds in _db.bank_sfx().items():
                for s in sounds:
                    out.append({"value": s, "label": f"[{bank}] {s}"})
            return out
    return []


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════
def _field_visible(obj, field) -> bool:
    cond = field.get("visible_if")
    if not cond:
        return True
    for k, expected in cond.items():
        if obj.get(k) != expected:
            return False
    return True


def _resolve_default(field, obj, actor_info):
    """Return the display default for a field."""
    if "default" in field:
        return field["default"]
    # Per-etype defaults (e.g. lavaballoon: 3.0 vs darkecobarrel: 15.0)
    if "default_per_etype" in field and actor_info:
        per = field["default_per_etype"]
        return per.get(actor_info.get("etype"))
    return None


# ═════════════════════════════════════════════════════════════════════════════
# Draw a single field
# ═════════════════════════════════════════════════════════════════════════════
def _draw_note(layout, note: str):
    row = layout.row()
    row.enabled = False
    row.label(text=note, icon="INFO")


def _draw_enum_field(layout, obj, field):
    key = field["key"]
    label = field.get("label", key)
    choices = _resolve_choices(field.get("choices", []))
    if not choices:
        row = layout.row()
        row.alert = True
        row.label(text=f"{label}: no choices defined", icon="ERROR")
        return

    current = obj.get(key)
    if current is None:
        current = field.get("default")

    box = layout.box()
    box.label(text=f"{label}:")
    # Short lists (<=8): radio buttons. Longer lists: still radio, but in a
    # scrollable column. Full dropdown would require a typed EnumProperty.
    col = box.column(align=True)
    for c in choices[:40]:  # cap the render count to avoid UI stalls
        val = c.get("value", "")
        disp = c.get("label", val)
        sub = col.row(align=True)
        icon = "RADIOBUT_ON" if current == val else "RADIOBUT_OFF"
        op = sub.operator("og.set_actor_enum_field", text=disp, icon=icon)
        op.prop_key = key
        op.value = val
    if len(choices) > 40:
        row = box.row()
        row.enabled = False
        row.label(text=f"… (+{len(choices) - 40} more, edit DB to reduce)")


def _draw_bool_field(layout, obj, field):
    key = field["key"]
    label = field.get("label", key)
    val = bool(obj.get(key, field.get("default", False)))
    box = layout.box()
    icon = "CHECKBOX_HLT" if val else "CHECKBOX_DEHLT"
    op = box.operator("og.toggle_actor_bool_field", text=label, icon=icon)
    op.prop_key = key


def _draw_vector3_field(layout, obj, field):
    key = field["key"]
    label = field.get("label", key)
    default = field.get("default")
    if not isinstance(default, list) or len(default) != 3:
        default = [0.0, 0.0, 0.0]
    col = layout.column(align=True)
    col.label(text=f"{label}:")
    for axis, dval in zip("xyz", default):
        _prop_row(col, obj, f"{key}_{axis}", f"  {axis.upper()}:", dval)


def _draw_field(layout, obj, field, actor_info=None):
    if not _field_visible(obj, field):
        return

    ftype = field.get("type", "string")
    label = field.get("label", field["key"])
    default = _resolve_default(field, obj, actor_info)

    if ftype == "enum":
        _draw_enum_field(layout, obj, field)
    elif ftype == "bool":
        _draw_bool_field(layout, obj, field)
    elif ftype == "vector3":
        _draw_vector3_field(layout, obj, field)
    elif ftype == "object_ref":
        # Simple text input for object name. A proper picker would need
        # a typed PointerProperty; not worth adding for a few fields.
        row = layout.row(align=True)
        row.label(text=f"{label}:")
        row.prop(obj, f'["{field["key"]}"]', text="")
    else:
        # float / int / string — _prop_row handles all three
        _prop_row(layout, obj, field["key"], f"{label}:",
                  default if default is not None else 0)

    if field.get("note"):
        _draw_note(layout, field["note"])


# ═════════════════════════════════════════════════════════════════════════════
# The generic panel
# ═════════════════════════════════════════════════════════════════════════════

# Actors whose UI is entirely data-driven (pure field-display with no custom
# logic beyond what the schema expresses). If you add a new entry here, make
# sure the corresponding bespoke OG_PT_Actor* panel has been removed from
# panels.py + __init__.py — otherwise both will draw and duplicate the UI.
GENERIC_PANEL_ETYPES = frozenset({
    # Pure float/int field panels
    "orbit-plat",       # replaces OG_PT_ActorOrbitPlat
    "plat-flip",        # replaces OG_PT_ActorPlatFlip
    "whirlpool",        # replaces OG_PT_ActorWhirlpool
    "square-platform",  # replaces OG_PT_ActorSquarePlatform
    "orb-cache-top",    # replaces OG_PT_ActorOrbCache
    "caveflamepots",    # replaces OG_PT_ActorCaveFlamePots
    "shover",           # replaces OG_PT_ActorShover
    "sharkey",          # replaces OG_PT_ActorSharkey
    "sunkenfisha",      # replaces OG_PT_ActorSunkenFish
    "basebutton",       # replaces OG_PT_ActorBaseButton
    # Shared-field groups
    "lavaballoon", "darkecobarrel",                          # OG_PT_ActorLavaMoving
    "breakaway-left", "breakaway-mid", "breakaway-right",    # OG_PT_ActorBreakaway
    "swamp-bat", "yeti", "villa-starfish", "swamp-rat-nest", # OG_PT_ActorSpawner
    # Bool-toggle panels (checkbox via og.toggle_actor_bool_field)
    "dark-crystal",     # replaces OG_PT_ActorDarkCrystal
    "fuel-cell",        # replaces OG_PT_ActorFuelCell
    "windturbine",      # replaces OG_PT_ActorWindTurbine
    # Enum (radio buttons)
    "ropebridge",       # replaces OG_PT_ActorRopeBridge
    "mis-bone-bridge",  # replaces OG_PT_ActorMisBoneBridge
})


class OG_PT_ActorFields(Panel):
    """Data-driven per-actor settings panel.

    Reads the actor's fields[] schema from the game database and draws UI
    for each field automatically. Replaces most of the former per-actor
    OG_PT_Actor* panels.
    """
    bl_label       = "Actor Settings"
    bl_idname      = "OG_PT_actor_fields"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or "_wp_" in sel.name:
            return False
        parts = sel.name.split("_", 2)
        if len(parts) < 3 or parts[0] != "ACTOR":
            return False
        etype = parts[1]
        return etype in GENERIC_PANEL_ETYPES

    def draw(self, ctx):
        sel = ctx.active_object
        parts = sel.name.split("_", 2)
        etype = parts[1]
        actor = _db.find_actor(etype)
        if not actor:
            self.layout.label(text=f"No DB entry for {etype!r}", icon="ERROR")
            return
        fields = actor.get("fields", [])
        if not fields:
            row = self.layout.row()
            row.enabled = False
            row.label(text="(no configurable fields)", icon="INFO")
            return
        # Include etype on actor_info dict so per-etype defaults work for
        # shared field groups (e.g. lavaballoon=3.0 vs darkecobarrel=15.0)
        actor_info = {"etype": etype, **actor}
        for field in fields:
            _draw_field(self.layout, sel, field, actor_info)


# Exported registry for __init__.py
CLASSES = (
    OG_OT_SetActorEnumField,
    OG_OT_ToggleActorBoolField,
    OG_PT_ActorFields,
)
