"""Developer Tools › Addon Settings › Import Settings from .blend: copy this
add-on's per-.blend settings (launch timing, build settings, export filter,
Project Folders, Warning Settings) from another .blend.

The other file's first scene is linked (read-only) just long enough to read
the values, then its library is removed again; nothing else is brought in."""
from __future__ import annotations

import json

import bpy
from bpy.props import BoolProperty, StringProperty

# (key, label, scene pointer, property names or None = every property of it)
GROUPS = (
    ("timing", "Launch Timing", "og_props", ("og_launch_boot_wait", "og_launch_listener_wait")),
    ("build", "Build Settings", "og_props", ("og_ignore_game_gd", "og_clean_renamed", "og_navmesh_system",
                                             "og_camera_system")),
    ("filter", "Export Filter", "og_export_filter", None),
    ("folders", "Project Folders", "og_props", ("og_blend_paths_enabled", "og_blend_exe_path", "og_blend_data_path",
                                                "og_blend_decompiler_path", "og_blend_code_path",
                                                "og_blend_db_override_path")),
    ("warnings", "Warning Settings", "og_warnings", None),
)


def _names(owner, names):
    if names is not None:
        return list(names)
    return [p.identifier for p in owner.bl_rna.properties
            if p.identifier not in ("rna_type", "name") and not p.is_readonly
            and p.type in ("BOOLEAN", "INT", "FLOAT", "STRING", "ENUM")]


def read_settings(scene):
    """{group: {prop: value}} of a scene."""
    out = {}
    for key, _label, ptr, names in GROUPS:
        owner = getattr(scene, ptr, None)
        if owner is None:
            continue
        vals = {}
        for n in _names(owner, names):
            if hasattr(owner, n):
                v = getattr(owner, n)
                vals[n] = list(v) if hasattr(v, "__len__") and not isinstance(v, str) else v
        out[key] = vals
    return out


def read_blend(path):
    """read_settings() of the first scene of another .blend (linked, then removed)."""
    with bpy.data.libraries.load(path, link=True) as (src, dst):
        if not src.scenes:
            return None
        dst.scenes = [src.scenes[0]]
    sc = dst.scenes[0]
    lib = sc.library if sc is not None else None
    try:
        return read_settings(sc) if sc is not None else None
    finally:
        if lib is not None:
            bpy.data.libraries.remove(lib)


def apply_settings(scene, data, groups):
    n = 0
    for key, _label, ptr, _names in GROUPS:
        if key not in groups or key not in data:
            continue
        owner = getattr(scene, ptr, None)
        for prop, v in data[key].items():
            if owner is not None and hasattr(owner, prop):
                try:
                    setattr(owner, prop, v); n += 1
                except (TypeError, ValueError, AttributeError):
                    pass
    return n


def _fmt(v):
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, bool):
        return "on" if v else "off"
    return str(v) if v != "" else "(empty)"


def _label(owner, prop):
    p = owner.bl_rna.properties.get(prop) if owner is not None else None
    return p.name if p is not None else prop


class OG_OT_ImportSettingsPick(bpy.types.Operator):
    """Pick a .blend and import this add-on's settings from it (you choose which ones next)"""
    bl_idname = "og.import_settings_pick"
    bl_label = "Import Settings from .blend"

    filepath: StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.blend", options={"HIDDEN"})

    def invoke(self, ctx, event):
        ctx.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, ctx):
        if bpy.path.abspath(self.filepath) == bpy.data.filepath:
            self.report({"WARNING"}, "That's this .blend"); return {"CANCELLED"}
        try:
            data = read_blend(self.filepath)
        except Exception as e:
            self.report({"ERROR"}, f"Couldn't read {self.filepath}: {e}"); return {"CANCELLED"}
        if not data:
            self.report({"ERROR"}, "No scene in that file"); return {"CANCELLED"}
        bpy.ops.og.import_settings_confirm("INVOKE_DEFAULT", filepath=self.filepath, data=json.dumps(data))
        return {"FINISHED"}


class OG_OT_ImportSettingsConfirm(bpy.types.Operator):
    """Import the ticked groups of settings"""
    bl_idname = "og.import_settings_confirm"
    bl_label = "Import Settings"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    data: StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    use_timing: BoolProperty(name="Launch Timing", default=True)
    use_build: BoolProperty(name="Build Settings", default=True)
    use_filter: BoolProperty(name="Export Filter", default=True)
    use_folders: BoolProperty(name="Project Folders", default=True)
    use_warnings: BoolProperty(name="Warning Settings", default=True)

    def invoke(self, ctx, event):
        return ctx.window_manager.invoke_props_dialog(self, width=460, title="Import Settings",
                                                      confirm_text="Import")

    def draw(self, ctx):
        data = json.loads(self.data or "{}")
        layout = self.layout
        layout.label(text=f"From {bpy.path.basename(self.filepath)}  (current → imported)", icon="FILE_BLEND")
        for key, label, ptr, _names in GROUPS:
            vals = data.get(key)
            if vals is None:
                continue
            owner = getattr(ctx.scene, ptr, None)
            box = layout.box()
            box.prop(self, f"use_{key}")
            col = box.column(align=True); col.enabled = getattr(self, f"use_{key}"); col.scale_y = 0.8
            changed = 0
            for prop, v in vals.items():
                cur = getattr(owner, prop, None) if owner is not None else None
                if isinstance(cur, (list, tuple)) or (cur is not None and hasattr(cur, "__len__") and not isinstance(cur, str)):
                    cur = list(cur)
                if cur == v:
                    continue
                changed += 1
                col.label(text=f"{_label(owner, prop)}:  {_fmt(cur)}  →  {_fmt(v)}")
            if not changed:
                col.label(text="Same as this .blend", icon="CHECKMARK")

    def execute(self, ctx):
        data = json.loads(self.data or "{}")
        groups = {k for k, *_r in GROUPS if getattr(self, f"use_{k}")}
        n = apply_settings(ctx.scene, data, groups)
        from . import required
        required.mark_dirty()
        self.report({"INFO"}, f"Imported {len(groups)} group(s) of settings ({n} values) from "
                              f"{bpy.path.basename(self.filepath)}")
        return {"FINISHED"}


CLASSES = (OG_OT_ImportSettingsPick, OG_OT_ImportSettingsConfirm)
