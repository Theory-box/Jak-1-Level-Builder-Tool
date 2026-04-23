# ───────────────────────────────────────────────────────────────────────
# operators/build.py — OpenGOAL Level Tools
#
# Build pipeline: export, goalc compile, play the level, bake lighting, open output files/folders.
# ───────────────────────────────────────────────────────────────────────

from __future__ import annotations

import bpy, os, re, json, subprocess, threading, time, math, mathutils
from pathlib import Path
from bpy.props import (StringProperty, BoolProperty, IntProperty,
                       EnumProperty, FloatProperty, CollectionProperty)
from bpy.types import Operator
from ..data import (
    ENTITY_DEFS, ENTITY_ENUM_ITEMS, ENEMY_ENUM_ITEMS, PROP_ENUM_ITEMS,
    NPC_ENUM_ITEMS, PICKUP_ENUM_ITEMS, PLATFORM_ENUM_ITEMS, CRATE_ITEMS, CRATE_PICKUP_ITEMS,
    ALL_SFX_ITEMS, SBK_SOUNDS, LEVEL_BANKS, LUMP_REFERENCE, ACTOR_LINK_DEFS,
    MUSIC_FLAVA_TABLE,
    NAV_UNSAFE_TYPES, NEEDS_PATH_TYPES, NEEDS_PATHB_TYPES, IS_PROP_TYPES,
    ETYPE_AG, ETYPE_CODE,
    needed_tpages, _lump_ref_for_etype, _actor_link_slots, _actor_has_links,
    _actor_links, _actor_get_link, _actor_set_link, _actor_remove_link,
    _build_actor_link_lumps, _parse_lump_row, _LUMP_HARDCODED_KEYS,
    _aggro_event_id, AGGRO_EVENT_ENUM_ITEMS, LUMP_TYPE_ITEMS,
    UNIVERSAL_LUMPS, _is_custom_type,
)
from ..collections import (
    _get_level_prop, _set_level_prop, _level_objects, _active_level_col,
    _all_level_collections, _ensure_sub_collection, _classify_object,
    _col_path_for_entity, _link_object_to_sub_collection,
    _recursive_col_objects, _COL_PATH_WAYPOINTS, _COL_PATH_NAVMESHES,
    _COL_PATH_TRIGGERS, _COL_PATH_CAMERAS, _COL_PATH_SPAWNS,
    _COL_PATH_SOUND_EMITTERS, _COL_PATH_SPAWNABLE_ENEMIES,
    _COL_PATH_SPAWNABLE_PLATFORMS, _COL_PATH_SPAWNABLE_PROPS,
    _COL_PATH_SPAWNABLE_NPCS, _COL_PATH_SPAWNABLE_PICKUPS,
    _COL_PATH_GEO_SOLID, _COL_PATH_WATER,
    _set_blender_active_collection, _LEVEL_COL_DEFAULTS,
)
from ..export import (
    _nick, _iso, _lname, _ldir, _goal_src, _level_info, _game_gp,
    _levels_dir, _entity_gc, _actor_uses_waypoints, _actor_uses_navmesh,
    _actor_is_platform, _actor_is_launcher, _actor_is_spawner,
    _actor_is_enemy, _actor_supports_aggro_trigger,
    _vol_links, _vol_link_targets, _vol_has_link_to, _rename_vol_for_links,
    _vols_linking_to, _vol_get_link_to, _vol_remove_link_to,
    _classify_target, _clean_orphaned_vol_links, log, collect_actors,
    collect_spawns, collect_ambients, needed_ags, needed_code,
    patch_level_info, patch_game_gp, discover_custom_levels, remove_level,
    export_glb,
)
from ..build import (
    _EXE, _BUILD_STATE, _PLAY_STATE, _GEO_REBUILD_STATE, _BUILD_PLAY_STATE, _exe_root, _data_root, _data,
    _gk, _goalc, _user_dir, kill_gk, launch_gk, goalc_send, goalc_ok,
    launch_goalc, _bg_build, _bg_play, _bg_geo_rebuild, _bg_build_and_play,
)
from ..properties import OGLumpRow, OGActorLink, OGVolLink, OGProperties
from ..utils import (
    _is_linkable, _is_aggro_target, _vol_for_target,
    _ENEMY_CATS, _NPC_CATS, _PICKUP_CATS, _PROP_CATS,
    _draw_platform_settings, _header_sep, _draw_entity_sub,
    _draw_wiki_preview,
)
from .. import model_preview as _mp
import re as _re


class OG_OT_ExportBuild(Operator):
    bl_idname = "og.export_build"
    bl_label  = "Export & Build"
    bl_description = "Export GLB, write all level files, compile with GOALC"
    _timer = None

    def execute(self, ctx):
        name = _lname(ctx)
        if not name:
            self.report({"ERROR"}, "Enter a level name first"); return {"CANCELLED"}
        if len(name) > 10:
            self.report({"ERROR"}, f"Level name '{name}' is {len(name)} chars — max 10"); return {"CANCELLED"}
        if len(name) > 10:
            self.report({"ERROR"}, f"Level name '{name}' is {len(name)} chars — max is 10. Shorten it in Level Settings.")
            return {"CANCELLED"}
        try:
            export_glb(ctx, name)
        except Exception as e:
            self.report({"ERROR"}, f"GLB export failed: {e}"); return {"CANCELLED"}
        _BUILD_STATE.clear()
        _BUILD_STATE.update({"done":False,"status":"Starting...","error":None,"ok":False})
        depsgraph = ctx.evaluated_depsgraph_get()  # fetch on main thread — unsafe from bg thread
        threading.Thread(target=_bg_build, args=(name, ctx.scene, depsgraph), daemon=True).start()
        wm = ctx.window_manager
        self._timer = wm.event_timer_add(0.5, window=ctx.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, ctx, event):
        if event.type == "TIMER":
            ctx.workspace.status_text_set("OpenGOAL: " + _BUILD_STATE.get("status","Working..."))
            if _BUILD_STATE.get("done"):
                ctx.window_manager.event_timer_remove(self._timer)
                ctx.workspace.status_text_set(None)
                if _BUILD_STATE.get("error"):
                    self.report({"ERROR"}, _BUILD_STATE["error"]); return {"CANCELLED"}
                self.report({"INFO"}, "Build complete!"); return {"FINISHED"}
        return {"PASS_THROUGH"}

    def cancel(self, ctx):
        ctx.window_manager.event_timer_remove(self._timer)
        ctx.workspace.status_text_set(None)

class OG_OT_Play(Operator):
    """Launch GK in debug mode. No GOALC, no auto-load — just opens the game
    so you can navigate to your level manually via the debug menu."""
    bl_idname      = "og.play"
    bl_label       = "Launch Game (Debug)"
    bl_description = "Kill existing GK, launch fresh in debug mode. Navigate to your level manually."

    def execute(self, ctx):
        kill_gk()
        ok, msg = launch_gk()
        if not ok:
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}
        self.report({"INFO"}, "Game launched in debug mode — select your level manually")
        return {"FINISHED"}

class OG_OT_PlayAutoLoad(Operator):
    """Kill GK+GOALC, relaunch, and auto-load the level via nREPL.
    Slower (~30-60s) but fully automated."""
    bl_idname      = "og.play_autoload"
    bl_label       = "Launch & Auto-Load Level"
    bl_description = "Kill GK/GOALC, relaunch, and automatically load your level via nREPL (slower)"
    _timer = None

    def execute(self, ctx):
        name = _lname(ctx)
        if not name:
            self.report({"ERROR"}, "Enter a level name first"); return {"CANCELLED"}
        if len(name) > 10:
            self.report({"ERROR"}, f"Level name '{name}' is {len(name)} chars — max 10"); return {"CANCELLED"}
        _PLAY_STATE.clear()
        _PLAY_STATE.update({"done":False,"error":None,"status":"Starting..."})
        threading.Thread(target=_bg_play, args=(name,), daemon=True).start()
        wm = ctx.window_manager
        self._timer = wm.event_timer_add(0.5, window=ctx.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, ctx, event):
        if event.type == "TIMER":
            ctx.workspace.status_text_set("OpenGOAL: " + _PLAY_STATE.get("status","..."))
            if _PLAY_STATE.get("done"):
                ctx.window_manager.event_timer_remove(self._timer)
                ctx.workspace.status_text_set(None)
                if _PLAY_STATE.get("error"):
                    self.report({"ERROR"}, _PLAY_STATE["error"]); return {"CANCELLED"}
                self.report({"INFO"}, "Game launched!")
                return {"FINISHED"}
        return {"PASS_THROUGH"}

    def cancel(self, ctx):
        ctx.window_manager.event_timer_remove(self._timer)
        ctx.workspace.status_text_set(None)

class OG_OT_OpenFolder(Operator):
    """Open a folder in the system file explorer."""
    bl_idname  = "og.open_folder"
    bl_label   = "Open Folder"
    bl_description = "Open folder in system file explorer"

    folder: bpy.props.StringProperty()

    def execute(self, ctx):
        p = Path(self.folder)
        if not p.exists():
            try:
                p.mkdir(parents=True, exist_ok=True)
            except Exception:
                self.report({"WARNING"}, f"Folder not found: {p}")
                return {"CANCELLED"}
        try:
            if os.name == "nt":
                os.startfile(str(p))
            elif os.uname().sysname == "Darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
        except Exception as e:
            self.report({"ERROR"}, f"Could not open folder: {e}")
            return {"CANCELLED"}
        return {"FINISHED"}

class OG_OT_OpenFile(Operator):
    """Open a specific file in the default system editor."""
    bl_idname  = "og.open_file"
    bl_label   = "Open File"
    bl_description = "Open file in default editor"

    filepath: bpy.props.StringProperty()

    def execute(self, ctx):
        p = Path(self.filepath)
        if not p.exists():
            self.report({"WARNING"}, f"File not found: {p}")
            return {"CANCELLED"}
        try:
            if os.name == "nt":
                os.startfile(str(p))
            elif os.uname().sysname == "Darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
        except Exception as e:
            self.report({"ERROR"}, f"Could not open file: {e}")
            return {"CANCELLED"}
        return {"FINISHED"}

class OG_OT_GeoRebuild(Operator):
    """Re-export geometry and actor placement, repack DGO, relaunch game.
    Skips GOAL compilation — fastest loop for geo and enemy placement changes."""
    bl_idname      = "og.geo_rebuild"
    bl_label       = "Quick Geo Rebuild"
    bl_description = (
        "Re-export geo + actor placement, repack DGO, relaunch game. "
        "No GOAL recompile. Use when only geometry or placement changed."
    )
    _timer = None

    def execute(self, ctx):
        name = _lname(ctx)
        if not name:
            self.report({"ERROR"}, "Enter a level name first"); return {"CANCELLED"}
        if len(name) > 10:
            self.report({"ERROR"}, f"Level name '{name}' is {len(name)} chars — max 10"); return {"CANCELLED"}
        if len(name) > 10:
            self.report({"ERROR"}, f"Level name '{name}' is {len(name)} chars — max is 10. Shorten it in Level Settings.")
            return {"CANCELLED"}
        try:
            export_glb(ctx, name)
        except Exception as e:
            self.report({"ERROR"}, f"GLB export failed: {e}"); return {"CANCELLED"}
        _GEO_REBUILD_STATE.clear()
        _GEO_REBUILD_STATE.update({"done": False, "status": "Starting...", "error": None, "ok": False})
        depsgraph = ctx.evaluated_depsgraph_get()  # fetch on main thread — unsafe from bg thread
        threading.Thread(target=_bg_geo_rebuild, args=(name, ctx.scene, depsgraph), daemon=True).start()
        wm = ctx.window_manager
        self._timer = wm.event_timer_add(0.5, window=ctx.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, ctx, event):
        if event.type == "TIMER":
            ctx.workspace.status_text_set("OpenGOAL Geo: " + _GEO_REBUILD_STATE.get("status", "Working..."))
            if _GEO_REBUILD_STATE.get("done"):
                ctx.window_manager.event_timer_remove(self._timer)
                ctx.workspace.status_text_set(None)
                if _GEO_REBUILD_STATE.get("error"):
                    self.report({"ERROR"}, _GEO_REBUILD_STATE["error"]); return {"CANCELLED"}
                self.report({"INFO"}, "Geo rebuild done — load your level in-game")
                return {"FINISHED"}
        return {"PASS_THROUGH"}

    def cancel(self, ctx):
        ctx.window_manager.event_timer_remove(self._timer)
        ctx.workspace.status_text_set(None)

class OG_OT_ExportBuildPlay(Operator):
    bl_idname      = "og.export_build_play"
    bl_label       = "Export, Build & Play"
    bl_description = "Export GLB, write level files, compile with GOALC, then launch the game"
    _timer = None

    def execute(self, ctx):
        name = _lname(ctx)
        if not name:
            self.report({"ERROR"}, "Enter a level name first")
            return {"CANCELLED"}
        try:
            export_glb(ctx, name)
        except Exception as e:
            self.report({"ERROR"}, f"GLB export failed: {e}")
            return {"CANCELLED"}

        _BUILD_PLAY_STATE.clear()
        _BUILD_PLAY_STATE.update({"done": False, "status": "Starting...", "error": None, "ok": False})
        depsgraph = ctx.evaluated_depsgraph_get()  # fetch on main thread — unsafe from bg thread
        threading.Thread(target=_bg_build_and_play, args=(name, ctx.scene, depsgraph), daemon=True).start()
        wm = ctx.window_manager
        self._timer = wm.event_timer_add(0.5, window=ctx.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, ctx, event):
        if event.type == "TIMER":
            ctx.workspace.status_text_set("OpenGOAL: " + _BUILD_PLAY_STATE.get("status", "Working..."))
            if _BUILD_PLAY_STATE.get("done"):
                ctx.window_manager.event_timer_remove(self._timer)
                ctx.workspace.status_text_set(None)
                if _BUILD_PLAY_STATE.get("error"):
                    self.report({"ERROR"}, _BUILD_PLAY_STATE["error"])
                    return {"CANCELLED"}
                self.report({"INFO"}, "Build & launch complete!")
                return {"FINISHED"}
        return {"PASS_THROUGH"}

    def cancel(self, ctx):
        ctx.window_manager.event_timer_remove(self._timer)
        ctx.workspace.status_text_set(None)

class OG_OT_BakeLighting(Operator):
    """Bake Cycles lighting to vertex colors on each selected mesh object."""
    bl_idname      = "og.bake_lighting"
    bl_label       = "Bake Lighting"
    bl_description = "Bake Cycles lighting to vertex colors on each selected mesh object"

    def execute(self, ctx):
        scene   = ctx.scene
        props   = scene.og_props
        samples = props.lightbake_samples

        # Collect only MESH objects from the selection
        targets = [o for o in ctx.selected_objects if o.type == "MESH"]
        if not targets:
            self.report({"ERROR"}, "No mesh objects selected")
            return {"CANCELLED"}

        # Store previous render settings
        prev_engine  = scene.render.engine
        prev_samples = scene.cycles.samples
        prev_device  = scene.cycles.device

        scene.render.engine  = "CYCLES"
        scene.cycles.samples = samples

        baked = []
        failed = []

        for obj in targets:
            try:
                # Ensure vertex color layer exists (named "BakedLight")
                vc_name = "BakedLight"
                mesh = obj.data
                if vc_name not in mesh.color_attributes:
                    mesh.color_attributes.new(name=vc_name, type="BYTE_COLOR", domain="CORNER")

                # Set as active render and active display layer
                attr = mesh.color_attributes[vc_name]
                mesh.color_attributes.active_color = attr

                # Deselect all, select only this object, make it active
                bpy.ops.object.select_all(action="DESELECT")
                obj.select_set(True)
                ctx.view_layer.objects.active = obj

                # Run Cycles bake — diffuse pass (combined colour + indirect)
                # INVOKE_DEFAULT makes it non-blocking (runs as a modal job,
                # like the UI button) so Blender's interface stays responsive
                # during the bake instead of freezing until each mesh finishes.
                bpy.ops.object.bake(
                    'INVOKE_DEFAULT',
                    type="DIFFUSE",
                    pass_filter={"COLOR", "DIRECT", "INDIRECT"},
                    target="VERTEX_COLORS",
                    save_mode="INTERNAL",
                )
                baked.append(obj.name)

            except Exception as exc:
                failed.append(f"{obj.name}: {exc}")

        # Restore render settings
        scene.render.engine  = prev_engine
        scene.cycles.samples = prev_samples

        # Restore original selection
        bpy.ops.object.select_all(action="DESELECT")
        for obj in targets:
            obj.select_set(True)
        if targets:
            ctx.view_layer.objects.active = targets[0]

        if failed:
            self.report({"WARNING"}, f"Baked {len(baked)}, failed: {'; '.join(failed)}")
        else:
            self.report({"INFO"}, f"Baked lighting to vertex colors on: {', '.join(baked)}")

        return {"FINISHED"}


# ─── Classes to register ───────────────────────────────────────────────────
CLASSES = (
    OG_OT_ExportBuild,
    OG_OT_Play,
    OG_OT_PlayAutoLoad,
    OG_OT_OpenFolder,
    OG_OT_OpenFile,
    OG_OT_GeoRebuild,
    OG_OT_ExportBuildPlay,
    OG_OT_BakeLighting,
)
