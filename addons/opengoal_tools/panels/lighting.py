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
    bl_label       = "💡  Lighting"
    bl_idname      = "OG_PT_lighting"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        layout = self.layout
        props  = ctx.scene.og_props

        # ── Level Lighting (mood + sky) ────────────────────────────────────
        # Writes :mood, :mood-func and :sky into level-info.gc on every export.
        box = layout.box()
        box.label(text="Level Lighting:", icon="LIGHT_SUN")
        box.prop(props, "mood", text="Mood")
        box.prop(props, "sky",  text="Has Sky")

        # ── Fog Override ───────────────────────────────────────────────────
        # When enabled the exporter injects a fog-control actor that overrides
        # *math-camera* fog values every frame.  When disabled, no fog-control
        # is emitted -- mood drives fog with no leftovers.
        fog_box = layout.box()
        fog_box.label(text="Fog Override:", icon="MOD_FLUIDSIM")
        fog_box.prop(props, "fog_override_enabled")
        if props.fog_override_enabled:
            sub = fog_box.column(align=True)
            sub.prop(props, "fog_color")
            sub.prop(props, "fog_start")
            sub.prop(props, "fog_end")
            sub.prop(props, "fog_max")
            sub.prop(props, "fog_min")

        layout.separator(factor=0.5)

        # ── Light baking: the Bake button first, then its settings ─────────
        sel = ctx.selected_objects
        targets = _bakeable_meshes(sel)
        skipped = len(sel) - len(targets)
        layout.label(text="Light Baking:", icon="LIGHT")
        row = layout.row()
        row.enabled = len(targets) > 0
        row.scale_y = 1.6
        row.operator("og.bake_lighting", text=f"Bake {len(targets)} mesh(es) → Vertex Color", icon="RENDER_STILL")
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
        col = layout.column(align=True)
        col.label(text="Cycles Bake Settings:", icon="SETTINGS")
        col.prop(props, "lightbake_samples")
        from ..collections import _active_level_col
        from .. import bake as _bake
        _lv = _active_level_col(ctx.scene)
        if _lv is not None:
            _bake.draw_options(layout, _lv)


CLASSES = (
    OG_PT_Lighting,
)
