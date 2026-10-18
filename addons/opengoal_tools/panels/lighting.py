# ─────────────────────────────────────────────────────────────────────────
# panels/lighting.py — OpenGOAL Level Tools
#
# Top-level "Lighting" panel for Cycles light-baking to vertex colors.
# Used to live under Level → Light Baking as a sub-panel; promoted to
# its own main panel because lighting is one of the first things a user
# sets up on a level mesh and it deserves a visible top-level entry.
#
# The bake options (bake.py: emit, curve, domain, blur) are drawn here too;
# baking is only in this panel.
# ─────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import bpy
from bpy.types import Panel
from ..operators.build import _bakeable_meshes


class OG_PT_Lighting(Panel):
    bl_label       = "💡  Light Baking"
    bl_idname      = "OG_PT_lighting"
    bl_order = 5
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        layout = self.layout
        props  = ctx.scene.og_props

        # Mood, sky, texture remap and the fog override: Level > Settings > Visuals

        # ── Light baking: the Bake button first, then its settings ─────────
        sel = ctx.selected_objects
        targets = _bakeable_meshes(sel)
        skipped = len(sel) - len(targets)
        from ..collections import _active_level_col as _alc
        _lvc = _alc(ctx.scene)
        tod_n = 0
        if _lvc is not None and _lvc.og_bake.tod_enabled:
            from .. import bake as _bk0
            tod_n = sum(1 for *_x, t in _bk0.tod_times(_lvc.og_bake) if t.enabled)
        row = layout.row(align=True)
        row.scale_y = 1.6
        sub = row.row(align=True)
        sub.enabled = len(targets) > 0
        sub.operator("og.bake_lighting", icon="RENDER_STILL",
                     text=f"Bake {len(targets)} mesh(es)" + (f" ({tod_n} Time of day)" if tod_n else ""))
        row.operator("og.select_level_geometry", text="", icon="RESTRICT_SELECT_OFF")
        st = getattr(ctx.window_manager, "og_bake_status", "")
        if st:
            r = layout.row(); r.alert = st.startswith("Bake error")
            r.label(text=st, icon="ERROR" if r.alert else "INFO")
        if targets:
            box = layout.box()
            header = f"{len(targets)} mesh(es) selected"
            if skipped:
                header += f"  ({skipped} non-mesh / empty skipped)"
            box.prop(props, "show_bake_selection", text=header, emboss=False,
                     icon="TRIA_DOWN" if props.show_bake_selection else "TRIA_RIGHT")
            if props.show_bake_selection:
                from .. import bake as _bk
                for o in targets[:20]:
                    box.label(text=f"  • {o.name}", icon="LIGHT" if _bk.has_emission(o) else "BLANK1")
                if len(targets) > 20:
                    box.label(text=f"  … and {len(targets) - 20} more")
        elif skipped:
            layout.label(text=f"Selected items have no bakeable geometry  ({skipped} skipped)", icon="INFO")
        else:
            layout.label(text="Select mesh object(s) to bake", icon="INFO")
        layout.label(text="Result stored in 'BakedLight' layer", icon="GROUP_VCOL")

        layout.separator(factor=0.5)
        from ..collections import _active_level_col
        from .. import bake as _bake
        _lv = _active_level_col(ctx.scene)
        if _lv is not None:
            _bake.draw_options(layout, _lv, ctx.scene)   # samples + options (collapsible)
            _bake.draw_tod(layout, _lv)
        else:
            layout.prop(props, "lightbake_samples")


class OG_OT_SelectLevelGeometry(bpy.types.Operator):
    """Select every mesh of the level's GLB (Geometry and its folders; not
    Disable Export folders, not meshes with rendering off)"""
    bl_idname = "og.select_level_geometry"
    bl_label = "Select Level Geometry"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        from ..collections import _active_level_col
        from ..export.glb import exported_meshes
        lv = _active_level_col(ctx.scene)
        if lv is None:
            self.report({"ERROR"}, "No active level"); return {"CANCELLED"}
        meshes = exported_meshes(lv)
        vl = ctx.view_layer
        for o in ctx.selected_objects:
            o.select_set(False)
        picked, skipped = [], 0
        for o in meshes:
            if o.name in vl.objects and o.visible_get() and not o.hide_select:
                o.select_set(True); picked.append(o)
            else:
                skipped += 1
        if picked:
            vl.objects.active = picked[0]
        self.report({"INFO"}, f"Selected {len(picked)} level mesh(es)"
                              + (f" ({skipped} hidden / unselectable skipped)" if skipped else ""))
        return {"FINISHED"}


CLASSES = (
    OG_PT_Lighting,
    OG_OT_SelectLevelGeometry,
)
