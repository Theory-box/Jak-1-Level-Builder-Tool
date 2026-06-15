# ─────────────────────────────────────────────────────────────────────────
# panels/console.py — OpenGOAL Console
#
# A dedicated, scrolling mirror of goalc's REPL output inside Blender's
# "OpenGOAL" sidebar tab. Output is captured from the goalc process the
# addon launches (see build.py: _repl_reader / _repl_pump / launch_goalc)
# and rendered through a UIList so the full buffer scrolls without a
# per-frame line cap.
#
# This panel is display-only. It never sends to goalc; existing nREPL
# command flow (launch, load, checkpoints) is untouched.
# ─────────────────────────────────────────────────────────────────────────

import bpy


class OGConsoleLine(bpy.types.PropertyGroup):
    text: bpy.props.StringProperty()


class OG_UL_console(bpy.types.UIList):
    """One scrollback line per row. Virtualized by Blender, so a large
    buffer stays responsive. Rows don't wrap/scroll horizontally — long
    lines clip at panel width; use Copy to get the untruncated text."""
    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_prop, index):
        layout.label(text=item.text if item.text else " ")


class OG_OT_console_clear(bpy.types.Operator):
    bl_idname = "og.console_clear"
    bl_label = "Clear"
    bl_description = "Clear the OpenGOAL console buffer"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        wm = context.window_manager
        wm.og_console.clear()
        wm.og_console_index = 0
        return {'FINISHED'}


class OG_OT_console_copy(bpy.types.Operator):
    bl_idname = "og.console_copy"
    bl_label = "Copy"
    bl_description = "Copy the full OpenGOAL console buffer to the clipboard"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        wm = context.window_manager
        wm.clipboard = "\n".join(l.text for l in wm.og_console)
        self.report({'INFO'}, f"Copied {len(wm.og_console)} line(s)")
        return {'FINISHED'}


class OG_PT_console(bpy.types.Panel):
    bl_idname = "OG_PT_console"
    bl_label = "OpenGOAL Console"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OpenGOAL"
    bl_options = {'DEFAULT_CLOSED'}

    _STATUS_ICON = {
        "running":  'PLAY',
        "closed":   'PAUSE',
        "external": 'ERROR',
        "off":      'RADIOBUT_OFF',
        "idle":     'RADIOBUT_OFF',
    }

    def draw(self, context):
        from .. import build  # local import avoids import-order issues at register
        wm = context.window_manager
        layout = self.layout

        row = layout.row(align=True)
        row.prop(wm, "og_mirror_enabled", text="Mirror", toggle=True, icon='CONSOLE')
        row.prop(wm, "og_console_follow", text="Follow", toggle=True, icon='TRIA_DOWN')

        row = layout.row(align=True)
        row.operator("og.console_copy", text="Copy", icon='COPYDOWN')
        row.operator("og.console_clear", text="Clear", icon='TRASH')

        # Status + dual-instance warning. Both read cached values only — no
        # subprocess calls happen in draw() (the pump refreshes the count).
        status, detail = build.mirror_status()
        layout.label(text=f"goalc: {status}",
                     icon=self._STATUS_ICON.get(status, 'DOT'))
        if getattr(build, "_GOALC_COUNT", 0) > 1:
            box = layout.box()
            box.alert = True
            box.label(text="Multiple goalc processes running", icon='ERROR')
            box.label(text="Only the addon-launched one is mirrored.")
        if status == "external":
            layout.label(text="Relaunch goalc via the addon to mirror it",
                         icon='INFO')

        layout.template_list("OG_UL_console", "", wm, "og_console",
                             wm, "og_console_index", rows=14)


CLASSES = (
    OGConsoleLine,
    OG_UL_console,
    OG_OT_console_clear,
    OG_OT_console_copy,
    OG_PT_console,
)
