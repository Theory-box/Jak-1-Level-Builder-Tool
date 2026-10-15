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
    ALL_SFX_ITEMS, SBK_SOUNDS, LEVEL_BANKS, ACTOR_LINK_DEFS,
    MUSIC_FLAVA_TABLE,
    ETYPE_AG, ETYPE_CODE,
    needed_tpages, _lump_ref_for_etype, _actor_link_slots, _actor_has_links,
    _actor_links, _actor_get_link, _actor_set_link, _actor_remove_link,
    _build_actor_link_lumps, _parse_lump_row, _LUMP_HARDCODED_KEYS,
    _aggro_event_id, AGGRO_EVENT_ENUM_ITEMS, LUMP_TYPE_ITEMS,
    _is_custom_type,
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
    _EXE, _BUILD_STATE, _PLAY_STATE, _QUICK_EXPORT_STATE, _BUILD_PLAY_STATE, _exe_root, _data_root, _data,
    _gk, _goalc, _user_dir, kill_gk, launch_gk, goalc_send, goalc_ok,
    launch_goalc, _bg_build, _bg_play, _bg_quick_export, _bg_build_and_play,
    write_level_files, patch_entity_gc, _bg_compile, _file_times,
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


def _boot_cp(ctx, cp=None):
    """mod-base: the spawn a build writes into mod-settings.gc (the Spawn
    dropdown, or cp), None when not used."""
    from ..versions import modbase_spawn_on
    cp = cp or getattr(ctx.scene.og_props, "og_launch_checkpoint", "none")
    return cp if cp and cp != "none" and modbase_spawn_on(ctx.scene) else None


def _booted_cp(ctx):
    """mod-base: the spawn the game currently boots into, None when not used."""
    from ..versions import modbase_spawn_on, debug_continue_point
    return debug_continue_point() if modbase_spawn_on(ctx.scene) else None


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
        threading.Thread(target=_bg_build, args=(name, ctx.scene, depsgraph, _boot_cp(ctx)), daemon=True).start()
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

def _check_name(op, name):
    if not name:
        op.report({"ERROR"}, "Enter a level name first"); return False
    if len(name) > 10:
        op.report({"ERROR"}, f"Level name '{name}' is {len(name)} chars — max 10"); return False
    return True


class OG_OT_ExportOnly(Operator):
    bl_idname = "og.export_only"
    bl_label  = "Only Export"
    bl_description = "Export the GLB and write all of this level's files, without compiling"

    def execute(self, ctx):
        name = _lname(ctx)
        if not _check_name(self, name):
            return {"CANCELLED"}
        try:
            export_glb(ctx, name)
            write_level_files(name, ctx.scene, ctx.evaluated_depsgraph_get())
        except Exception as e:
            self.report({"ERROR"}, f"Export failed: {e}"); return {"CANCELLED"}
        self.report({"INFO"}, f"Exported {name} (not compiled)")
        return {"FINISHED"}


class OG_OT_ExportBuildAll(OG_OT_ExportBuild):
    bl_idname = "og.export_build_all"
    bl_label  = "Export & Compile All Levels"
    bl_description = "Export every level in this .blend, then compile once with GOALC"

    def execute(self, ctx):
        from ..collections import _all_level_collections
        props = ctx.scene.og_props
        levels = _all_level_collections(ctx.scene)
        if not levels:
            self.report({"ERROR"}, "No level in this file"); return {"CANCELLED"}
        prev = props.active_level
        times = _file_times()
        navmesh, done = [], []
        try:
            # the collectors read the active level: make each one active in turn
            for col in levels:
                props.active_level = col.name
                name = _lname(ctx)
                if not _check_name(self, name):
                    return {"CANCELLED"}
                export_glb(ctx, name)
                navmesh += write_level_files(name, ctx.scene, ctx.evaluated_depsgraph_get(), navmesh=False)
                done.append(name)
            patch_entity_gc(navmesh)          # every level's nav-meshes, not only the last one's
        except Exception as e:
            self.report({"ERROR"}, f"Export of {col.name} failed: {e}"); return {"CANCELLED"}
        finally:
            if prev in {c.name for c in levels}:
                props.active_level = prev
        log(f"[build] exported {len(done)} level(s): {', '.join(done)}")
        _BUILD_STATE.clear()
        _BUILD_STATE.update({"done": False, "status": "Starting...", "error": None, "ok": False})
        threading.Thread(target=_bg_compile, args=(times, _boot_cp(ctx)), daemon=True).start()
        wm = ctx.window_manager
        self._timer = wm.event_timer_add(0.5, window=ctx.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}


class OG_OT_Play(Operator):
    """Launch the game.

    Reads scene.og_props.og_launch_checkpoint:
      "none"            → bare GK launch (debug mode). Navigate via debug menu.
      "<level>-<uid>"   → full flow: write startup.gc with (lt), relaunch
                          GOALC + GK, poll for *game-info* ready, send
                          (start 'play (get-continue-by-name *game-info* "<cp>")).
                          The continue-point has :lev0 baked in so this
                          single (start) call loads the level AND spawns Jak.
    """
    bl_idname      = "og.play"
    bl_label       = "Launch Game"
    bl_description = "Launch GK. If a continue-point is selected in the dropdown, also load the level and spawn there."
    _timer = None

    def execute(self, ctx):
        cp = getattr(ctx.scene.og_props, "og_launch_checkpoint", "none")

        # Bare-launch path: synchronous, no GOALC.
        if cp == "none":
            kill_gk()
            ok, msg = launch_gk()
            if not ok:
                self.report({"ERROR"}, msg); return {"CANCELLED"}
            self.report({"INFO"}, "Game launched in debug mode — select your level manually")
            return {"FINISHED"}

        # Spawn-at-checkpoint path: modal, runs _bg_play in a background thread.
        # Guard against double-click while a launch is already in flight —
        # without this, a second click during the cold-start window queues
        # another (start) that re-loads the level after the first one fires.
        if _PLAY_STATE.get("done") is False and _PLAY_STATE.get("status"):
            self.report({"INFO"}, "Launch already in progress — please wait")
            return {"CANCELLED"}

        name = _lname(ctx)
        if not name:
            self.report({"ERROR"}, "Enter a level name first"); return {"CANCELLED"}
        if len(name) > 10:
            self.report({"ERROR"}, f"Level name '{name}' is {len(name)} chars — max 10"); return {"CANCELLED"}
        _PLAY_STATE.clear()
        _PLAY_STATE.update({"done":False,"error":None,"status":"Starting..."})
        # Read tunables from properties (settable in Developer Tools).
        props = ctx.scene.og_props
        boot_wait = float(getattr(props, "og_launch_boot_wait", 4.0))
        listener_wait = float(getattr(props, "og_launch_listener_wait", 1.0))
        threading.Thread(
            target=_bg_play,
            args=(name, cp, boot_wait, listener_wait, _booted_cp(ctx)),
            daemon=True,
        ).start()
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

class OG_OT_QuickExport(Operator):
    """Export only this level's own files (GLB, .jsonc actors / cameras /
    settings, .gd, level code) and rebuild. Checkpoints, load boundaries,
    nav-mesh entries and game.gp (shared files) are left as they are"""
    bl_idname      = "og.quick_export"
    bl_label       = "Quick Level Export"
    bl_description = (
        "Export this level's GLB, .jsonc (actors, cameras, settings), .gd and level code, then rebuild. "
        "Doesn't touch checkpoints, load boundaries, nav-mesh entries or game.gp: "
        "use Export & Compile after changing those or adding a new actor type"
    )
    _timer = None

    def execute(self, ctx):
        name = _lname(ctx)
        if not name:
            self.report({"ERROR"}, "Enter a level name first"); return {"CANCELLED"}
        if len(name) > 10:
            self.report({"ERROR"}, f"Level name '{name}' is {len(name)} chars — max 10"); return {"CANCELLED"}
        try:
            export_glb(ctx, name)
        except Exception as e:
            self.report({"ERROR"}, f"GLB export failed: {e}"); return {"CANCELLED"}
        _QUICK_EXPORT_STATE.clear()
        _QUICK_EXPORT_STATE.update({"done": False, "status": "Starting...", "error": None, "ok": False})
        depsgraph = ctx.evaluated_depsgraph_get()  # fetch on main thread — unsafe from bg thread
        threading.Thread(target=_bg_quick_export, args=(name, ctx.scene, depsgraph, _boot_cp(ctx)), daemon=True).start()
        wm = ctx.window_manager
        self._timer = wm.event_timer_add(0.5, window=ctx.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, ctx, event):
        if event.type == "TIMER":
            ctx.workspace.status_text_set("OpenGOAL Quick Export: " + _QUICK_EXPORT_STATE.get("status", "Working..."))
            if _QUICK_EXPORT_STATE.get("done"):
                ctx.window_manager.event_timer_remove(self._timer)
                ctx.workspace.status_text_set(None)
                if _QUICK_EXPORT_STATE.get("error"):
                    self.report({"ERROR"}, _QUICK_EXPORT_STATE["error"]); return {"CANCELLED"}
                self.report({"INFO"}, "Quick export done — load your level in-game")
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
        threading.Thread(target=_bg_build_and_play, args=(name, ctx.scene, depsgraph, _boot_cp(ctx, f"{name}-start")), daemon=True).start()
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

def _bakeable_meshes(objects):
    """Return the subset of `objects` that can actually receive a vertex-color bake.

    Filters out:
      • non-MESH types (lights, curves, empties, etc.)
      • mesh objects whose data block has zero polygons (empty placeholder
        meshes — common when users add dummy/marker meshes to the scene)

    Used by both OG_OT_BakeLighting and the Lighting panel so the displayed
    count and the actual bake target list stay in sync.
    """
    return [o for o in objects
            if o.type == "MESH"
            and o.data is not None
            and len(o.data.polygons) > 0]


class OG_OT_BakeLighting(Operator):
    """Bake Cycles lighting to vertex colors on each selected mesh object."""
    bl_idname      = "og.bake_lighting"
    bl_label       = "Bake Lighting"
    bl_description = "Bake Cycles lighting to vertex colors on each selected mesh object"

    def execute(self, ctx):
        scene   = ctx.scene
        props   = scene.og_props
        samples = props.lightbake_samples

        # Filter selection to mesh objects with actual geometry.
        # Non-meshes (lights, empties, curves) and zero-polygon "empty" meshes
        # are silently skipped so users can do a quick Select-All -> Bake
        # without having to manually deselect non-bakeable items.
        sel = list(ctx.selected_objects)
        targets = _bakeable_meshes(sel)
        if not targets:
            self.report({"ERROR"}, "No bakeable meshes selected (nothing with polygons)")
            return {"CANCELLED"}
        skipped = len(sel) - len(targets)

        # Configure Cycles for the bake. We deliberately don't restore
        # these afterwards — the bake runs asynchronously as a modal job
        # (see INVOKE_DEFAULT below), so the execute method returns before
        # baking finishes. Restoring on exit would yank the render engine
        # out from under the in-flight job.
        scene.render.engine  = "CYCLES"
        scene.cycles.samples = samples

        # Deselect non-bakeable items first so the bake jobs never see them,
        # and make sure the active object is a bakeable mesh (Blender needs it).
        for o in sel:
            if o not in targets:
                o.select_set(False)
        if ctx.view_layer.objects.active not in targets:
            ctx.view_layer.objects.active = targets[0]

        # bake.py: light pass (+ emit pass), then the level's bake options
        # (emit blend, curve, blur). One Blender bake job per pass.
        from .. import bake as _bake
        from ..collections import _active_level_col
        if _bake.busy():
            self.report({"WARNING"}, "A bake is still running"); return {"CANCELLED"}
        passes = _bake.start(targets, _active_level_col(scene), blocking=bpy.app.background)
        modal = _bake.busy() and not bpy.app.background

        names = ", ".join(o.name for o in targets)
        msg = f"Baking {len(targets)} mesh(es) ({' + '.join(passes)}"
        if "emit" in passes:
            msg += f", emit on {len(_bake._JOB.get('emit_objs', []))}"
        msg += ")"
        if skipped:
            msg += f" (skipped {skipped} non-mesh / empty)"
        msg += f": {names}"
        self.report({"INFO"}, msg)
        if modal:
            # the next passes + post-processing run from this operator (modal,
            # timer events): Blender always allows data changes here
            wm = ctx.window_manager
            self._timer = wm.event_timer_add(0.5, window=ctx.window)
            wm.modal_handler_add(self)
            return {"RUNNING_MODAL"}
        return {"FINISHED"}

    def modal(self, ctx, event):
        if event.type == "TIMER":
            from .. import bake as _bake
            try:
                more = _bake.step()
            except Exception as e:
                import traceback
                print("[OpenGOAL] bake:", traceback.format_exc())
                _bake._JOB.clear()
                _bake._status(f"Bake error: {e}")
                more = False
            if not more:
                ctx.window_manager.event_timer_remove(self._timer)
                st = getattr(ctx.window_manager, "og_bake_status", "")
                self.report({"ERROR"} if st.startswith("Bake error") else {"INFO"}, st or "Bake finished")
                return {"FINISHED"}
        return {"PASS_THROUGH"}

    def cancel(self, ctx):
        if getattr(self, "_timer", None):
            ctx.window_manager.event_timer_remove(self._timer)


# ─── Classes to register ───────────────────────────────────────────────────
CLASSES = (
    OG_OT_ExportBuild,
    OG_OT_ExportOnly,
    OG_OT_ExportBuildAll,
    OG_OT_Play,
    OG_OT_OpenFolder,
    OG_OT_OpenFile,
    OG_OT_QuickExport,
    OG_OT_ExportBuildPlay,
    OG_OT_BakeLighting,
)
