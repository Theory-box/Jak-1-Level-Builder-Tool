# ─────────────────────────────────────────────────────────────────────────
# panels/lighting.py — OpenGOAL Level Tools
#
# Top-level "Lighting" panel for Cycles light-baking to vertex colors.
# Used to live under Level → Light Baking as a sub-panel; promoted to
# its own main panel because lighting is one of the first things a user
# sets up on a level mesh and it deserves a visible top-level entry.
#
# The context-aware per-mesh light-bake section (OG_PT_SelectedLightBaking)
# still lives in panels/selected.py under the Selected Object panel.
# ─────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import bpy
from bpy.types import Panel


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

        col = layout.column(align=True)
        col.label(text="Cycles Bake Settings:", icon="LIGHT")
        col.prop(props, "lightbake_samples")

        layout.separator(factor=0.5)

        targets = [o for o in ctx.selected_objects if o.type == "MESH"]
        if targets:
            box = layout.box()
            box.label(text=f"{len(targets)} mesh(es) selected:", icon="OBJECT_DATA")
            for o in targets[:6]:
                box.label(text=f"  • {o.name}")
            if len(targets) > 6:
                box.label(text=f"  … and {len(targets) - 6} more")
        else:
            layout.label(text="Select mesh object(s) to bake", icon="INFO")

        layout.separator(factor=0.5)
        row = layout.row()
        row.enabled = len(targets) > 0
        row.scale_y = 1.6
        row.operator("og.bake_lighting", text="Bake Lighting → Vertex Color", icon="RENDER_STILL")
        layout.separator(factor=0.3)
        layout.label(text="Result stored in 'BakedLight' layer", icon="GROUP_VCOL")


CLASSES = (
    OG_PT_Lighting,
)
