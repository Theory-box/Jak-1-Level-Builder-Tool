# ───────────────────────────────────────────────────────────────────────
# panels/level.py — OpenGOAL Level Tools
#
# Level management panels: audit, music, light-baking, level flow, clean.
#
# Auto-generated from the original panels.py by the refactor split.
# Edit freely — this is no longer a generated file.
# ───────────────────────────────────────────────────────────────────────

from __future__ import annotations

import bpy
from bpy.types import Panel, Operator
from pathlib import Path
from ..data import (
    ENTITY_DEFS, ENTITY_WIKI, ENTITY_ENUM_ITEMS, ENEMY_ENUM_ITEMS, VERTEX_EXPORT_TYPES,
    PROP_ENUM_ITEMS, NPC_ENUM_ITEMS, PICKUP_ENUM_ITEMS, PLATFORM_ENUM_ITEMS,
    CRATE_ITEMS, CRATE_PICKUP_ITEMS, ALL_SFX_ITEMS, SBK_SOUNDS, LEVEL_BANKS,
    LUMP_REFERENCE, ACTOR_LINK_DEFS, LUMP_TYPE_ITEMS,
    NAV_UNSAFE_TYPES, NEEDS_PATH_TYPES, IS_PROP_TYPES, ETYPE_AG,
    _lump_ref_for_etype, _actor_link_slots, _actor_has_links,
    _actor_links, _actor_get_link, AGGRO_TRIGGER_EVENTS,
    _parse_lump_row, _LUMP_HARDCODED_KEYS,
    GLOBAL_TPAGE_GROUPS, _is_custom_type,
)
from ..collections import (
    _get_level_prop, _set_level_prop, _level_objects, _active_level_col,
    _all_level_collections, _classify_object, _col_path_for_entity,
    _recursive_col_objects, _ensure_sub_collection, _link_object_to_sub_collection,
    _COL_PATH_NAVMESHES, _COL_PATH_WAYPOINTS, _COL_PATH_EXPORT_AS,
    _COL_PATH_TRIGGERS, _COL_PATH_CAMERAS, _COL_PATH_SOUND_EMITTERS,
    _COL_PATH_SPAWNABLE_ENEMIES, _COL_PATH_GEO_SOLID,
)
from ..export import (
    _nick, _iso, _lname, _ldir, _goal_src, _level_info, _game_gp,
    _levels_dir, _entity_gc,
    _actor_uses_waypoints, _actor_uses_navmesh,
    _actor_is_platform, _actor_is_launcher, _actor_is_spawner,
    _actor_is_enemy, _actor_supports_aggro_trigger,
    _vol_links, _vols_linking_to, _classify_target,
    _vol_get_link_to, _vol_has_link_to,
    collect_cameras, collect_aggro_triggers, log,
)
from ..build import (
    _EXE, _BUILD_STATE, _PLAY_STATE, goalc_ok, kill_gk,
    _exe_root, _data_root, _data, _goalc, _gk, _user_dir,
)
from ..properties import OGLumpRow, OG_UL_LumpRows
from ..utils import (
    _is_linkable, _is_aggro_target, _vol_for_target,
    _ENEMY_CATS, _NPC_CATS, _PICKUP_CATS, _PROP_CATS,
    _draw_platform_settings, _header_sep, _draw_entity_sub,
    _draw_wiki_preview, _prop_row,
    _preview_collections, _load_previews, _unload_previews,
)
from .. import model_preview as _mp
from ..audit import run_audit



# ─── Module constants (rescued from the original panels.py) ────────────────
_AUDIT_ICONS = {
    "ERROR":   "ERROR",
    "WARNING": "ERROR",
    "INFO":    "INFO",
}

_AUDIT_SEVERITY_LABEL = {
    "ERROR":   "\U0001F534",  # 🔴
    "WARNING": "\U0001F7E1",  # 🟡
    "INFO":    "\u2139",      # ℹ
}


class OG_PT_Level(Panel):
    bl_label       = "⚙  Level"
    bl_idname      = "OG_PT_level"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"

    def draw(self, ctx):
        layout = self.layout
        props  = ctx.scene.og_props
        scene  = ctx.scene

        levels = _all_level_collections(scene)
        level_col = _active_level_col(scene)

        # ── No levels exist → show Add Level button only ─────────────────
        if not levels:
            layout.label(text="No levels in this file", icon="INFO")
            row = layout.row(align=True)
            row.operator("og.create_level", text="Add Level", icon="ADD")
            row.operator("og.assign_collection_as_level", text="Assign Existing", icon="OUTLINER_COLLECTION")
            return

        # ── Level selector dropdown + edit button ────────────────────────
        row = layout.row(align=True)
        row.prop(props, "active_level", text="")
        row.operator("og.edit_level", text="", icon="GREASEPENCIL")

        if level_col is None:
            return

        # ── Level info (compact) ──────────────────────────────────────────
        name = str(level_col.get("og_level_name", ""))
        base_id = int(level_col.get("og_base_id", 10000))
        if name:
            name_clean = name.lower().replace(" ", "-")
            if len(name_clean) > 10:
                warn = layout.row()
                warn.alert = True
                warn.label(text=f"Name too long ({len(name_clean)} chars, max 10)!", icon="ERROR")
            else:
                row = layout.row()
                row.enabled = False
                row.label(text=f"ID: {base_id}   ISO: {_iso(name)}   Nick: {_nick(name)}")

        layout.separator(factor=0.4)

        # Vis nick override
        vnick = str(level_col.get("og_vis_nick_override", ""))
        row_vn = layout.row(align=True)
        row_vn.enabled = False
        row_vn.label(text=f"Vis Nick Override: {vnick if vnick else '(auto)'}")



class OG_PT_LevelManagerSub(Panel):
    bl_label       = "🗂  Level Manager"
    bl_idname      = "OG_PT_level_manager"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_level"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        layout = self.layout
        scene  = ctx.scene
        levels = _all_level_collections(scene)
        active = _active_level_col(scene)

        if not levels:
            layout.label(text="No levels in this file")

        for col in levels:
            lname     = col.get("og_level_name", col.name)
            is_active = (active is not None and col.name == active.name)

            row = layout.row(align=True)
            # Checkbox appearance via toggle operator — depress=is_active gives filled look
            op = row.operator("og.set_active_level",
                              text=lname,
                              icon="CHECKBOX_HLT" if is_active else "CHECKBOX_DEHLT",
                              depress=is_active)
            op.col_name = col.name

        layout.separator(factor=0.4)
        row = layout.row(align=True)
        row.operator("og.create_level",               text="Add Level",       icon="ADD")
        row.operator("og.assign_collection_as_level", text="Assign Existing", icon="OUTLINER_COLLECTION")



class OG_OT_SortLevelObjects(Operator):
    """Sort all loose objects in the active level into the correct sub-collections.

    'Loose' means either:
      - Directly in the level collection (no sub-collection), OR
      - In a sub-collection but the wrong one (e.g. a mesh in Spawnables)

    Classification rules:
      MESH, not VOL_          → Geometry / Solid
      VOL_                    → Triggers
      ACTOR_ empty            → Spawnables / (category)
      SPAWN_ / CHECKPOINT_    → Spawns
      *_wp_* / *_wpb_*        → Waypoints
      AMBIENT_                → Sound Emitters
      CAMERA_ (camera)        → Cameras
    Objects that can't be classified are left in place with a warning.
    """
    bl_idname   = "og.sort_level_objects"
    bl_label    = "Sort Collection Objects"
    bl_options  = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        scene     = ctx.scene
        level_col = _active_level_col(scene)
        if level_col is None:
            self.report({"ERROR"}, "No active level collection")
            return {"CANCELLED"}

        # Gather every object in the level (all sub-collections included)
        all_objs = _recursive_col_objects(level_col, exclude_no_export=False)

        moved   = []
        skipped = []

        for obj in all_objs:
            target_path = _classify_object(obj)
            if target_path is None:
                skipped.append(obj.name)
                continue

            # Find where the object currently lives within the level
            target_col = _ensure_sub_collection(level_col, *target_path)

            # Already in the right collection — skip
            if obj.name in target_col.objects:
                continue

            # Link into target
            target_col.objects.link(obj)

            # Unlink from scene root if present
            if obj.name in scene.collection.objects:
                scene.collection.objects.unlink(obj)

            # Unlink from every other collection except the target
            for col in bpy.data.collections:
                if col == target_col:
                    continue
                if obj.name in col.objects:
                    col.objects.unlink(obj)

            moved.append(f"{obj.name} → {'/'.join(target_path)}")
            log(f"[sort] {obj.name} → {target_path}")

        if moved:
            self.report({"INFO"}, f"Sorted {len(moved)} object(s)")
            for m in moved:
                log(f"  [sort] {m}")
        else:
            self.report({"INFO"}, "Everything already sorted")

        if skipped:
            self.report({"WARNING"}, f"Could not classify {len(skipped)} object(s): {', '.join(skipped[:5])}")

        return {"FINISHED"}



class OG_PT_CollectionProperties(Panel):
    bl_label       = "📂  Collections"
    bl_idname      = "OG_PT_collection_props"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_level"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        return _active_level_col(ctx.scene) is not None

    def draw(self, ctx):
        pass  # sub-panels draw the content



class OG_PT_DisableExport(Panel):
    bl_label       = "Disable Export"
    bl_idname      = "OG_PT_disable_export"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_collection_props"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        return _active_level_col(ctx.scene) is not None

    def draw(self, ctx):
        layout = self.layout
        level_col = _active_level_col(ctx.scene)
        if level_col is None:
            return

        children = sorted(level_col.children, key=lambda c: c.name)

        if not children:
            layout.label(text="No sub-collections")
        else:
            for col in children:
                layout.prop(col, "og_no_export", text=col.name)



class OG_PT_CleanSub(Panel):
    bl_label       = "🧹  Clean"
    bl_idname      = "OG_PT_clean_sub"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_collection_props"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        return _active_level_col(ctx.scene) is not None

    def draw(self, ctx):
        layout = self.layout
        layout.operator("og.sort_level_objects",
                        text="Sort Collection Objects",
                        icon="SORTSIZE")



class OG_PT_Music(Panel):
    bl_label       = "🎵  Music"
    bl_idname      = "OG_PT_music"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_level"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        layout = self.layout
        props  = ctx.scene.og_props

        box = layout.box()
        box.label(text="Level Music", icon="PLAY")
        box.prop(props, "music_bank", text="Music Bank")

        box2 = layout.box()
        box2.label(text="Sound Banks  (max 2)", icon="SPEAKER")
        b1 = props.sound_bank_1
        b2 = props.sound_bank_2
        col2 = box2.column(align=True)
        col2.prop(props, "sound_bank_1", text="Bank 1")
        col2.prop(props, "sound_bank_2", text="Bank 2")
        if b1 != "none" and b1 == b2:
            box2.label(text="⚠ Bank 1 and Bank 2 are the same", icon="ERROR")
        n_common = len(SBK_SOUNDS.get("common", []))
        n_level  = len(set(SBK_SOUNDS.get(b1, [])) | set(SBK_SOUNDS.get(b2, [])))
        box2.label(text=f"{n_common} common  +  {n_level} level  =  {n_common + n_level} available", icon="INFO")



class OG_OT_RunAudit(Operator):
    """Scan the active level for configuration errors, warnings, and info"""
    bl_idname  = "og.run_audit"
    bl_label   = "Run Audit"
    bl_options = {"REGISTER"}

    def execute(self, ctx):
        scene   = ctx.scene
        results = scene.og_audit_results
        results.clear()
        scene.og_audit_results_index = 0

        issues = run_audit(scene)
        for issue in issues:
            item          = results.add()
            item.severity = issue["severity"]
            item.message  = issue["message"]
            item.obj_name = issue.get("obj_name") or ""

        self.report({"INFO"}, f"Audit complete — {len(issues)} issue(s) found.")
        return {"FINISHED"}



class OG_OT_AuditSelectObject(Operator):
    """Select and frame the object linked to this audit result"""
    bl_idname  = "og.audit_select_object"
    bl_label   = "Select"
    bl_options = {"REGISTER", "UNDO"}

    obj_name: bpy.props.StringProperty()

    def execute(self, ctx):
        obj = ctx.scene.objects.get(self.obj_name)
        if obj is None:
            self.report({"WARNING"}, f"Object '{self.obj_name}' not found.")
            return {"CANCELLED"}
        for o in ctx.scene.objects:
            o.select_set(False)
        obj.select_set(True)
        ctx.view_layer.objects.active = obj
        for area in ctx.screen.areas:
            if area.type == "VIEW_3D":
                with ctx.temp_override(area=area, region=area.regions[-1]):
                    bpy.ops.view3d.view_selected()
                break
        return {"FINISHED"}



class OG_PT_LevelAudit(Panel):
    bl_label       = "🔍  Level Audit"
    bl_idname      = "OG_PT_level_audit"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_level"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw_header(self, ctx):
        results  = ctx.scene.og_audit_results
        errors   = sum(1 for r in results if r.severity == "ERROR")
        warnings = sum(1 for r in results if r.severity == "WARNING")
        if errors:
            self.layout.label(text=f"{errors}E {warnings}W", icon="ERROR")
        elif warnings:
            self.layout.label(text=f"{warnings}W", icon="ERROR")

    def draw(self, ctx):
        layout  = self.layout
        scene   = ctx.scene
        results = scene.og_audit_results

        layout.operator("og.run_audit", text="Run Audit", icon="VIEWZOOM")

        if not results:
            layout.label(text="Press Run Audit to check the level.", icon="INFO")
            return

        errors   = sum(1 for r in results if r.severity == "ERROR")
        warnings = sum(1 for r in results if r.severity == "WARNING")
        infos    = sum(1 for r in results if r.severity == "INFO")

        row = layout.row()
        row.enabled = False
        row.label(text=f"{errors} error(s)  ·  {warnings} warning(s)  ·  {infos} info")

        layout.separator(factor=0.5)

        for r in results:
            box    = layout.box()
            header = box.row(align=True)
            icon   = _AUDIT_ICONS.get(r.severity, "DOT")
            prefix = _AUDIT_SEVERITY_LABEL.get(r.severity, "")
            header.label(text=f"{prefix}  {r.severity}", icon=icon)
            if r.obj_name:
                op = header.operator("og.audit_select_object", text="", icon="RESTRICT_SELECT_OFF")
                op.obj_name = r.obj_name

            # Word-wrap message into ~55-char lines
            col   = box.column(align=True)
            col.scale_y = 0.85
            words = r.message.split(" ")
            line  = ""
            for word in words:
                test = (line + " " + word).strip()
                if len(test) > 55 and line:
                    col.label(text=line)
                    line = word
                else:
                    line = test
            if line:
                col.label(text=line)

            if r.obj_name:
                sub = box.row()
                sub.enabled = False
                sub.scale_y = 0.75
                sub.label(text=f"  {r.obj_name}", icon="OBJECT_DATA")



class OG_OT_CleanLevelFiles(Operator):
    """Delete generated files for the current level so the next build writes them fresh.
    Removes: obs.gc, .jsonc, .glb, .gd — forces a clean compile without stale cached data."""
    bl_idname = "og.clean_level_files"
    bl_label  = "Clean Level Files"
    bl_description = "Delete generated level files to force a clean rebuild (obs.gc, jsonc, glb, gd)"

    def execute(self, ctx):
        name = _lname(ctx)
        if not name:
            self.report({"ERROR"}, "No level name set")
            return {"CANCELLED"}

        deleted = []
        skipped = []

        # goal_src obs.gc — the one that causes stale compile errors
        obs_gc = _goal_src() / "levels" / name / f"{name}-obs.gc"
        # custom_assets files
        assets = _ldir(name)
        targets = [
            obs_gc,
            assets / f"{name}.jsonc",
            assets / f"{name}.glb",
            assets / f"{_nick(name)}.gd",
        ]

        for p in targets:
            if p.exists():
                p.unlink()
                deleted.append(p.name)
            else:
                skipped.append(p.name)

        if deleted:
            self.report({"INFO"}, f"Deleted: {', '.join(deleted)}" +
                        (f"  (not found: {', '.join(skipped)})" if skipped else ""))
        else:
            self.report({"WARNING"}, f"Nothing to delete — files not found for '{name}'")
        return {"FINISHED"}




# ─── Classes to register ───────────────────────────────────────────────────
CLASSES = (
    OG_PT_Level,
    OG_PT_LevelManagerSub,
    OG_OT_SortLevelObjects,
    OG_PT_CollectionProperties,
    OG_PT_DisableExport,
    OG_PT_CleanSub,
    OG_PT_Music,
    OG_OT_RunAudit,
    OG_OT_AuditSelectObject,
    OG_PT_LevelAudit,
    OG_OT_CleanLevelFiles,
)
