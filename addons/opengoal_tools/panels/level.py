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
    ACTOR_LINK_DEFS, LUMP_TYPE_ITEMS,
    ETYPE_AG,
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
    _level_index_in_use, _vis_nick_in_use, _resolve_vis_nick,
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
from ..game_text import draw_field
from ..properties import OGLumpRow, OG_UL_LumpRows, draw_command_list
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

        # ── Level selector dropdown ──────────────────────────────────────
        row = layout.row(align=True)
        row.prop(props, "active_level", text="")

        if level_col is None:
            return


# ---------------------------------------------------------------------------
# Level > Settings  (sub-panel)
# ---------------------------------------------------------------------------

class OG_PT_LevelSettings(Panel):
    bl_label       = "⚙  Settings"
    bl_idname      = "OG_PT_level_settings"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_level"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _active_level_col(context.scene) is not None

    def draw(self, ctx):
        layout = self.layout
        props  = ctx.scene.og_props
        scene  = ctx.scene
        col    = _active_level_col(scene)
        if col is None:
            return

        s = col.og_level

        # ── Base settings ──────────────────────────────────────────────
        layout.prop(props, "level_name")
        draw_field(layout, s, "menu_name")
        layout.prop(props, "vis_nick_override")
        layout.prop(props, "level_index")

        # Derived / read-only info
        name = str(col.get("og_level_name", col.name))
        nick_eff = _resolve_vis_nick(col)
        info = layout.row(); info.enabled = False
        info.label(text=f"ISO: {_iso(name)}   Effective Nick: {nick_eff}")

        # Collision + length warnings
        if len(name) > 10:
            w = layout.row(); w.alert = True
            w.label(text=f"Name too long ({len(name)}/10 chars)", icon="ERROR")

        lidx = int(col.get("og_level_index", 100))
        if _level_index_in_use(scene, lidx, exclude_col=col):
            w = layout.row(); w.alert = True
            w.label(text=f"Level index {lidx} collides with another level", icon="ERROR")

        if nick_eff and _vis_nick_in_use(scene, nick_eff, exclude_col=col):
            w = layout.row(); w.alert = True
            w.label(text=f"Nickname '{nick_eff}' collides with another level", icon="ERROR")

        # ── Sound & Music ──────────────────────────────────────────────
        head, body = layout.panel("og_lvl_sound", default_closed=True)
        head.label(text="Sound & Music", icon="SPEAKER")
        if body is not None:
            _draw_sound(body, props)

        # ── Visuals ────────────────────────────────────────────────────
        head, body = layout.panel("og_lvl_visuals", default_closed=True)
        head.label(text="Visuals", icon="LIGHT_SUN")
        if body is not None:
            body.prop(props, "mood")
            if props.mood == "custom":
                body.prop(s, "mood_custom")
            body.prop(s, "mood_func")
            if s.mood_func == "CUSTOM":
                body.prop(s, "mood_func_custom")
            body.prop(s, "ocean")
            if s.ocean == "CUSTOM":
                body.prop(s, "ocean_custom")
            body.prop(s, "sun_fade", slider=True)
            body.prop(props, "sky_source")
            if props.sky_source == "custom":
                body.prop(s, "sky_custom")
            body.prop(props, "texture_source")
            hint = body.column(); hint.enabled = False; hint.scale_y = 0.7
            hint.label(text="Texture remap: Flut Flut eyes, water, dark eco pools,", icon="INFO")
            hint.label(text="dying enemies (things drawn with generic textures)", icon="BLANK1")

        # ── Gameplay ───────────────────────────────────────────────────
        head, body = layout.panel("og_lvl_gameplay", default_closed=True)
        head.label(text="Gameplay", icon="ARMATURE_DATA")
        if body is not None:
            _draw_checkpoint_list(body, scene)
            body.prop(props, "bottom_height")
            _draw_tasks(body, s)
            body.prop(s, "wall_angle")
            body.prop(s, "double_sided")
            if s.double_sided:
                w = body.row(); w.alert = True
                w.label(text="Doubles the collision mesh", icon="ERROR")

        # ── Others ─────────────────────────────────────────────────────
        head, body = layout.panel("og_lvl_others", default_closed=True)
        head.label(text="Others", icon="PREFERENCES")
        if body is not None:
            others = body
            body.prop(s, "bsphere")
            if s.bsphere is None:
                hint = body.row(); hint.enabled = False; hint.scale_y = 0.7
                hint.label(text="No sphere: computed from the checkpoints", icon="INFO")
            body.prop(props, "base_id")
            body.prop(props, "actor_name_nick")
            ch, cb = body.panel("og_lvl_commands", default_closed=True)
            ch.label(text="Commands", icon="CONSOLE")
            if cb is not None:
                draw_command_list(cb, s, "load_cmds", "Load Commands", owner="LEVEL")
                draw_command_list(cb, s, "alt_load_cmds", "Alt Load Commands", owner="LEVEL")
                cb.prop(s, "priority")
                cb.prop(s, "wait_for_load")
            # Always Include (export/includes.py)
            box = others.box()
            box.prop(props, "include_enabled")
            if props.include_enabled:
                row = box.row(align=True)
                row.prop_search(props, "include_text", bpy.data, "texts", text="")
                row.operator("og.include_create", text="", icon="ADD")
                row.operator("og.include_edit", text="", icon="TEXT")
                row.operator("og.include_template", text="", icon="FILE_TEXT")
                from ..export import includes as _inc
                txt = bpy.data.texts.get(props.include_text) if props.include_text else None
                if txt is None:
                    box.label(text="Pick or create an include text", icon="INFO")
                elif not txt.as_string().strip():
                    box.operator("og.include_template", text="Insert Template", icon="FILE_TEXT")
                    box.label(text="Empty — Insert Template shows every key", icon="INFO")
                else:
                    data, errs = _inc.parse(txt.as_string())
                    st = box.column(); st.scale_y = 0.8
                    st.label(text=_inc.summary(data), icon="CHECKMARK" if not errs else "INFO")
                    for e in errs[:4]:
                        w = st.row(); w.alert = True; w.label(text=e, icon="ERROR")


def _draw_sound(layout, props):
    """Level music + sound banks (was the Music panel)."""
    layout.prop(props, "music_bank", text="Music Bank")
    b1 = props.sound_bank_1
    b2 = props.sound_bank_2
    col2 = layout.column(align=True)
    col2.prop(props, "sound_bank_1", text="Sound Bank 1")
    col2.prop(props, "sound_bank_2", text="Sound Bank 2")
    if b1 != "none" and b1 == b2:
        layout.label(text="Bank 1 and Bank 2 are the same", icon="ERROR")
    n_common = len(SBK_SOUNDS.get("common", []))
    n_level  = len(set(SBK_SOUNDS.get(b1, [])) | set(SBK_SOUNDS.get(b2, [])))
    hint = layout.row(); hint.enabled = False
    hint.label(text=f"{n_common} common  +  {n_level} level  =  {n_common + n_level} sounds", icon="INFO")


def _draw_checkpoint_list(layout, scene):
    """The level's checkpoints; clicking one selects it."""
    from ..collections import _level_objects, spawn_uid
    cps = sorted((o for o in _level_objects(scene)
                  if o.name.startswith("CHECKPOINT_") and o.type == "EMPTY" and not o.name.endswith("_CAM")),
                 key=lambda o: (spawn_uid(o) != "start", o.name))
    head = layout.row(align=True)
    head.label(text=f"Checkpoints ({len(cps)})", icon="EMPTY_SINGLE_ARROW")
    head.operator("og.spawn_checkpoint", text="", icon="ADD")
    colm = layout.column(align=True)
    for o in cps:
        row = colm.row(align=True)
        op = row.operator("og.select_and_frame", text=spawn_uid(o) or o.name,
                          icon="RADIOBUT_ON" if o.select_get() else "RADIOBUT_OFF", depress=o.select_get())
        op.obj_name = o.name
    if not any(spawn_uid(o) == "start" for o in cps):
        w = layout.row(); w.alert = True
        w.label(text='No "start" checkpoint', icon="ERROR")


def _draw_tasks(layout, s):
    head = layout.row(align=True)
    head.label(text=f"Tasks ({len(s.tasks)})" if s.tasks else "Tasks")
    head.operator("og.level_task_add", text="", icon="ADD")
    colm = layout.column(align=True)
    for i, r in enumerate(s.tasks):
        row = colm.row(align=True)
        row.prop(r, "task", text="")
        row.operator("og.level_task_remove", text="", icon="REMOVE").index = i


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
                _draw_skip_tree(layout, col, 0)


_TREE_OPEN: set = set()   # Disable Export list: expanded collections (UI only)


def _draw_skip_tree(layout, c, depth):
    """One row per collection (its "skip_export" custom property), children
    under an arrow, at any depth."""
    row = layout.row(align=True)
    if depth:
        row.separator(factor=1.5 * depth)
    if c.children:
        op = row.operator("og.toggle_skip_tree", text="", emboss=False,
                          icon="DISCLOSURE_TRI_DOWN" if c.name in _TREE_OPEN else "DISCLOSURE_TRI_RIGHT")
        op.col_name = c.name
    else:
        row.label(text="", icon="BLANK1")
    on = bool(c.get("skip_export", False))
    op = row.operator("og.toggle_collection_no_export", text=c.name, emboss=False,
                      icon="CHECKBOX_HLT" if on else "CHECKBOX_DEHLT")
    op.col_name = c.name
    if c.name in _TREE_OPEN:
        for ch in sorted(c.children, key=lambda x: x.name):
            _draw_skip_tree(layout, ch, depth + 1)


class OG_OT_ToggleSkipTree(Operator):
    """Show / hide this collection's sub-collections"""
    bl_idname = "og.toggle_skip_tree"
    bl_label  = "Expand"
    bl_options = {"INTERNAL"}

    col_name: bpy.props.StringProperty()

    def execute(self, ctx):
        _TREE_OPEN.symmetric_difference_update({self.col_name})
        for area in ctx.screen.areas:
            area.tag_redraw()
        return {"FINISHED"}



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
        ]
        # .gd is named after the effective nick (override or auto) - remove any.
        if assets.exists():
            targets += sorted(assets.glob("*.gd"))

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
    OG_PT_LevelSettings,
    OG_PT_LevelManagerSub,
    OG_OT_SortLevelObjects,
    OG_PT_CollectionProperties,
    OG_PT_DisableExport,
    OG_OT_ToggleSkipTree,
    OG_PT_CleanSub,
    OG_OT_RunAudit,
    OG_OT_AuditSelectObject,
    OG_PT_LevelAudit,
    OG_OT_CleanLevelFiles,
)


def draw_text_editor_header(self, ctx):
    """Text Editor header: Insert Template button while editing a level's
    include text (Level > Settings > Always Include)."""
    space = ctx.space_data
    txt = getattr(space, "text", None)
    if txt is None:
        return
    for col in bpy.data.collections:
        if col.get("og_is_level") and col.get("og_include_text") == txt.name:
            op = self.layout.operator("og.include_template", text="Insert Template", icon="FILE_TEXT")
            op.text_name = txt.name
            return
