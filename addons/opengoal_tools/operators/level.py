# ───────────────────────────────────────────────────────────────────────
# operators/level.py — OpenGOAL Level Tools
#
# Level and collection management: create/assign/delete levels, sort objects, music-zone properties, GOAL code, lump rows.
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
    _next_free_level_index, _level_index_in_use,
    _vis_nick_in_use, _suggest_unique_vis_nick, _resolve_vis_nick,
    _ensure_level_index, _migrate_all_level_indices,
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

from .misc import _flava_items_for_active

# ─── Rescued module-level symbols (from original operators.py) ────────────
_MUSIC_BANK_ITEMS = [(b[0], b[1], b[2], b[3]) for b in LEVEL_BANKS if b[0] != "none"]
_GOAL_BOILERPLATE = """\
;;-*-Lisp-*-
(in-package goal)
;; {name}-obs.gc custom code — injected by OpenGOAL Level Tools
;; Entity type: {etype}
;;
;; Replace this with your deftype + defstate + init-from-entity!
;; See knowledge-base/opengoal/goal-scripting.md for reference.
;;
;; IMPORTANT:
;;   • First field starts at offset-assert 176 (end of process-drawable base)
;;   • Each state :code loop must call (suspend) or the game will freeze
;;   • Compile errors appear in the goalc build log, not in Blender
;;   • The entity type name in your deftype must match what you put in ACTOR_<n>_<uid>
;;     i.e. ACTOR_{etype}_0 expects a (deftype {etype} (process-drawable) ...)

(deftype {etype} (process-drawable)
  ()   ;; add fields here starting at :offset-assert 176
  (:states {etype}-idle))

(defstate {etype}-idle ({etype})
  :code
    (behavior ()
      (loop (suspend))))

(defmethod init-from-entity! ((this {etype}) (arg0 entity-actor))
  (set! (-> this root) (new 'process 'trsqv))
  (process-drawable-from-entity! this arg0)
  (go {etype}-idle)
  (none))
"""



class OG_OT_CreateLevel(Operator):
    """Create a new level collection with default settings."""
    bl_idname   = "og.create_level"
    bl_label    = "Add Level"
    bl_options  = {"REGISTER", "UNDO"}

    level_name: StringProperty(name="Level Name", default="my-level",
                               description="Name for the new level (lowercase, dashes)")
    base_id:    IntProperty(name="Base Actor ID", default=10000, min=1000, max=60000,
                            description="Starting actor ID — must be unique per level")
    level_index: IntProperty(name="Level Index", default=100, min=1, max=10000,
                             description="Unique level-load-info :index. Must not collide with vanilla or other custom levels. Safe range: 100+")
    vis_nick:   StringProperty(name="Vis Nickname", default="",
                               description="3-letter nickname used for DGO/vis files. Auto-suggested from name; must be unique across levels")

    def invoke(self, ctx, event):
        levels = _all_level_collections(ctx.scene)
        if levels:
            max_id = max(c.get("og_base_id", 10000) for c in levels)
            self.base_id = max_id + 1000
            self.level_name = "new-level"
        self.level_index = _next_free_level_index(ctx.scene)
        self.vis_nick = _suggest_unique_vis_nick(ctx.scene, self.level_name)
        return ctx.window_manager.invoke_props_dialog(self)

    def execute(self, ctx):
        name = self.level_name.strip().lower().replace(" ", "-")
        if not name:
            self.report({"ERROR"}, "Level name cannot be empty")
            return {"CANCELLED"}
        if len(name) > 10:
            self.report({"ERROR"}, f"Level name '{name}' is {len(name)} chars — max 10")
            return {"CANCELLED"}

        # Check for duplicate names
        for col in _all_level_collections(ctx.scene):
            if col.get("og_level_name", "") == name:
                self.report({"ERROR"}, f"A level named '{name}' already exists")
                return {"CANCELLED"}

        # Check for duplicate level index
        if _level_index_in_use(ctx.scene, self.level_index):
            self.report({"ERROR"}, f"Level index {self.level_index} is already in use by another level")
            return {"CANCELLED"}

        # Validate + check vis nickname uniqueness
        nick_clean = self.vis_nick.strip().lower()
        if not nick_clean:
            nick_clean = _suggest_unique_vis_nick(ctx.scene, name)
        if len(nick_clean) > 3:
            self.report({"ERROR"}, f"Vis nickname '{nick_clean}' must be 3 characters or fewer")
            return {"CANCELLED"}
        if _vis_nick_in_use(ctx.scene, nick_clean):
            self.report({"ERROR"}, f"Vis nickname '{nick_clean}' is already used by another level")
            return {"CANCELLED"}

        # Create the level collection
        col = bpy.data.collections.new(name)
        ctx.scene.collection.children.link(col)

        # Set level properties
        col["og_is_level"]          = True
        col["og_level_name"]        = name
        col["og_base_id"]           = self.base_id
        col["og_level_index"]       = self.level_index
        col["og_bottom_height"]     = -20.0
        col["og_vis_nick_override"] = nick_clean
        col["og_sound_bank_1"]      = "none"
        col["og_sound_bank_2"]      = "none"
        col["og_music_bank"]        = "none"

        # Set as active level
        ctx.scene.og_props.active_level = col.name
        _set_blender_active_collection(ctx, col)

        self.report({"INFO"}, f"Created level '{name}' (base ID {self.base_id}, index {self.level_index}, nick '{nick_clean}')")
        log(f"[collections] Created level collection '{name}' base_id={self.base_id} index={self.level_index} nick={nick_clean}")
        return {"FINISHED"}

class OG_OT_AssignCollectionAsLevel(Operator):
    """Assign an existing Blender collection as a level."""
    bl_idname   = "og.assign_collection_as_level"
    bl_label    = "Assign Collection as Level"
    bl_options  = {"REGISTER", "UNDO"}

    col_name:   StringProperty(name="Collection",
                               description="Existing collection to designate as a level")
    level_name: StringProperty(name="Level Name", default="my-level",
                               description="Level name (max 10 chars, lowercase with dashes)")
    base_id:    IntProperty(name="Base Actor ID", default=10000, min=1000, max=60000)
    level_index: IntProperty(name="Level Index", default=100, min=1, max=10000,
                             description="Unique level-load-info :index. Must not collide with vanilla or other custom levels. Safe range: 100+")
    vis_nick:   StringProperty(name="Vis Nickname", default="",
                               description="3-letter nickname used for DGO/vis files. Auto-suggested from name; must be unique across levels")

    def invoke(self, ctx, event):
        levels = _all_level_collections(ctx.scene)
        if levels:
            max_id = max(c.get("og_base_id", 10000) for c in levels)
            self.base_id = max_id + 1000
        self.level_index = _next_free_level_index(ctx.scene)
        self.vis_nick = _suggest_unique_vis_nick(ctx.scene, self.level_name)
        return ctx.window_manager.invoke_props_dialog(self)

    def draw(self, ctx):
        layout = self.layout
        layout.prop_search(self, "col_name", bpy.data, "collections", text="Collection")
        layout.prop(self, "level_name")
        layout.prop(self, "base_id")
        layout.prop(self, "level_index")
        layout.prop(self, "vis_nick")

    def execute(self, ctx):
        if not self.col_name:
            self.report({"ERROR"}, "No collection selected"); return {"CANCELLED"}
        col = bpy.data.collections.get(self.col_name)
        if col is None:
            self.report({"ERROR"}, f"Collection '{self.col_name}' not found"); return {"CANCELLED"}
        if col.get("og_is_level", False):
            self.report({"ERROR"}, f"'{self.col_name}' is already a level"); return {"CANCELLED"}

        name = self.level_name.strip().lower().replace(" ", "-")
        if not name:
            self.report({"ERROR"}, "Level name cannot be empty"); return {"CANCELLED"}
        if len(name) > 10:
            self.report({"ERROR"}, f"Name '{name}' is {len(name)} chars — max 10"); return {"CANCELLED"}

        # Check for duplicate level names
        for c in _all_level_collections(ctx.scene):
            if c.get("og_level_name", "") == name:
                self.report({"ERROR"}, f"A level named '{name}' already exists"); return {"CANCELLED"}

        # Check for duplicate level index
        if _level_index_in_use(ctx.scene, self.level_index):
            self.report({"ERROR"}, f"Level index {self.level_index} is already in use by another level")
            return {"CANCELLED"}

        # Validate + check vis nickname uniqueness
        nick_clean = self.vis_nick.strip().lower()
        if not nick_clean:
            nick_clean = _suggest_unique_vis_nick(ctx.scene, name)
        if len(nick_clean) > 3:
            self.report({"ERROR"}, f"Vis nickname '{nick_clean}' must be 3 characters or fewer")
            return {"CANCELLED"}
        if _vis_nick_in_use(ctx.scene, nick_clean):
            self.report({"ERROR"}, f"Vis nickname '{nick_clean}' is already used by another level")
            return {"CANCELLED"}

        # Ensure collection is a direct child of the scene collection
        if col.name not in [c.name for c in ctx.scene.collection.children]:
            # It might be nested — link to scene root
            ctx.scene.collection.children.link(col)

        # Set level properties
        col["og_is_level"]          = True
        col["og_level_name"]        = name
        col["og_base_id"]           = self.base_id
        col["og_level_index"]       = self.level_index
        col["og_bottom_height"]     = -20.0
        col["og_vis_nick_override"] = nick_clean
        col["og_sound_bank_1"]      = "none"
        col["og_sound_bank_2"]      = "none"
        col["og_music_bank"]        = "none"

        # Set as active level
        ctx.scene.og_props.active_level = col.name
        _set_blender_active_collection(ctx, col)

        self.report({"INFO"}, f"Assigned '{self.col_name}' as level '{name}' (index {self.level_index}, nick '{nick_clean}')")
        log(f"[collections] Assigned existing collection '{self.col_name}' as level '{name}' index={self.level_index} nick={nick_clean}")
        return {"FINISHED"}

class OG_OT_SetActiveLevel(Operator):
    """Set a level collection as the active level."""
    bl_idname   = "og.set_active_level"
    bl_label    = "Set Active Level"
    bl_options  = {"REGISTER", "UNDO"}

    col_name: StringProperty(name="Collection Name")

    def execute(self, ctx):
        col = None
        for c in _all_level_collections(ctx.scene):
            if c.name == self.col_name:
                col = c
                break
        if col is None:
            self.report({"ERROR"}, f"Level collection '{self.col_name}' not found")
            return {"CANCELLED"}
        ctx.scene.og_props.active_level = col.name
        _set_blender_active_collection(ctx, col)
        lname = col.get("og_level_name", col.name)
        self.report({"INFO"}, f"Active level: {lname}")
        return {"FINISHED"}

class OG_OT_NudgeLevelProp(Operator):
    """Nudge a numeric property on the active level collection."""
    bl_idname   = "og.nudge_level_prop"
    bl_label    = "Nudge Level Property"
    bl_options  = {"REGISTER", "UNDO"}

    prop_name: StringProperty()
    delta:     FloatProperty()
    val_min:   FloatProperty(default=-999999.0)
    val_max:   FloatProperty(default=999999.0)

    def execute(self, ctx):
        col = _active_level_col(ctx.scene)
        if col is None:
            self.report({"ERROR"}, "No active level"); return {"CANCELLED"}
        cur = float(col.get(self.prop_name, 0.0))
        col[self.prop_name] = max(self.val_min, min(self.val_max, cur + self.delta))
        return {"FINISHED"}

class OG_OT_DeleteLevel(Operator):
    """Remove a collection from the level list (does not delete the collection)."""
    bl_idname   = "og.delete_level"
    bl_label    = "Remove Level"
    bl_options  = {"REGISTER", "UNDO"}

    col_name: StringProperty(name="Collection Name")

    def execute(self, ctx):
        target = None
        for c in _all_level_collections(ctx.scene):
            if c.name == self.col_name:
                target = c
                break
        if target is None:
            self.report({"ERROR"}, f"Level '{self.col_name}' not found")
            return {"CANCELLED"}

        lname = target.get("og_level_name", target.name)

        # Just remove the level marker — collection stays intact
        if "og_is_level" in target:
            del target["og_is_level"]
        for key in list(target.keys()):
            if key.startswith("og_"):
                del target[key]

        self.report({"INFO"}, f"Removed '{lname}' from levels (collection preserved)")
        return {"FINISHED"}

class OG_OT_AddCollectionToLevel(Operator):
    """Search for and add a collection from inside the level to the managed list."""
    bl_idname   = "og.add_collection_to_level"
    bl_label    = "Add Collection"
    bl_options  = {"REGISTER", "UNDO"}

    col_name: StringProperty(name="Collection",
                             description="Name of the collection to add")

    def invoke(self, ctx, event):
        self.col_name = ""
        return ctx.window_manager.invoke_props_dialog(self)

    def draw(self, ctx):
        level_col = _active_level_col(ctx.scene)
        if level_col is not None:
            self.layout.prop_search(self, "col_name", level_col, "children",
                                    text="Collection")
        else:
            self.layout.label(text="No active level", icon="ERROR")

    def execute(self, ctx):
        level_col = _active_level_col(ctx.scene)
        if level_col is None:
            self.report({"ERROR"}, "No active level"); return {"CANCELLED"}
        if not self.col_name:
            self.report({"ERROR"}, "No collection selected"); return {"CANCELLED"}
        # Verify the collection is actually a child of the level
        found = False
        for c in level_col.children:
            if c.name == self.col_name:
                found = True
                break
        if not found:
            self.report({"ERROR"}, f"'{self.col_name}' is not inside this level"); return {"CANCELLED"}
        # Select it in the panel
        ctx.scene.og_props.selected_collection = self.col_name
        self.report({"INFO"}, f"Selected '{self.col_name}'")
        return {"FINISHED"}

class OG_OT_RemoveCollectionFromLevel(Operator):
    """Remove a collection from the active level (moves it back to scene root)."""
    bl_idname   = "og.remove_collection_from_level"
    bl_label    = "Remove Collection"
    bl_options  = {"REGISTER", "UNDO"}

    col_name: StringProperty(name="Collection Name")

    def execute(self, ctx):
        level_col = _active_level_col(ctx.scene)
        if level_col is None:
            self.report({"ERROR"}, "No active level"); return {"CANCELLED"}
        col = None
        for c in level_col.children:
            if c.name == self.col_name:
                col = c
                break
        if col is None:
            self.report({"ERROR"}, f"Collection '{self.col_name}' not in this level"); return {"CANCELLED"}
        level_col.children.unlink(col)
        # Re-link to scene root so it doesn't vanish
        ctx.scene.collection.children.link(col)
        self.report({"INFO"}, f"Removed '{self.col_name}' from level")
        return {"FINISHED"}

class OG_OT_RemoveCollectionFromLevelActive(Operator):
    """Remove the selected collection from the active level."""
    bl_idname   = "og.remove_collection_from_level_active"
    bl_label    = "Remove Selected Collection"
    bl_options  = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        props = ctx.scene.og_props
        level_col = _active_level_col(ctx.scene)
        if level_col is None:
            self.report({"ERROR"}, "No active level"); return {"CANCELLED"}
        if not props.col_list or props.col_list_index >= len(props.col_list):
            self.report({"ERROR"}, "No collection selected"); return {"CANCELLED"}
        col_name = props.col_list[props.col_list_index].name
        col = None
        for c in level_col.children:
            if c.name == col_name:
                col = c
                break
        if col is None:
            self.report({"ERROR"}, f"'{col_name}' not found"); return {"CANCELLED"}
        level_col.children.unlink(col)
        ctx.scene.collection.children.link(col)
        # Remove from UIList
        props.col_list.remove(props.col_list_index)
        if props.col_list_index >= len(props.col_list):
            props.col_list_index = max(0, len(props.col_list) - 1)
        self.report({"INFO"}, f"Removed '{col_name}' from level")
        return {"FINISHED"}

class OG_OT_ToggleCollectionNoExport(Operator):
    """Toggle the no-export flag on a collection."""
    bl_idname   = "og.toggle_collection_no_export"
    bl_label    = "Toggle Exclude from Export"
    bl_options  = {"REGISTER", "UNDO"}

    col_name: StringProperty(name="Collection Name")

    def execute(self, ctx):
        col = bpy.data.collections.get(self.col_name)
        if col is None:
            self.report({"ERROR"}, f"Collection '{self.col_name}' not found"); return {"CANCELLED"}
        cur = bool(col.get("og_no_export", False))
        col["og_no_export"] = not cur
        state = "excluded" if not cur else "included"
        self.report({"INFO"}, f"'{self.col_name}' now {state} from export")
        return {"FINISHED"}

class OG_OT_SelectLevelCollection(Operator):
    """Select a sub-collection in the Collection Properties panel."""
    bl_idname   = "og.select_level_collection"
    bl_label    = "Select Collection"

    col_name: StringProperty(name="Collection Name")

    def execute(self, ctx):
        props = ctx.scene.og_props
        # Toggle: clicking the already-selected collection deselects it
        if props.selected_collection == self.col_name:
            props.selected_collection = ""
        else:
            props.selected_collection = self.col_name
        return {"FINISHED"}

class OG_OT_EditLevel(Operator):
    """Edit the active level's name, base actor ID, level index, nickname, and death plane."""
    bl_idname   = "og.edit_level"
    bl_label    = "Edit Level Settings"
    bl_options  = {"REGISTER", "UNDO"}

    level_name:   StringProperty(name="Level Name", default="")
    base_id:      IntProperty(name="Base Actor ID", default=10000, min=1000, max=60000)
    level_index:  IntProperty(name="Level Index", default=100, min=1, max=10000,
                              description="Unique level-load-info :index. Must not collide with vanilla or other custom levels. Safe range: 100+")
    vis_nick:     StringProperty(name="Vis Nickname", default="",
                                 description="3-letter nickname used for DGO/vis files. Must be unique across levels")
    bottom_height: FloatProperty(name="Death Plane (m)", default=-20.0, min=-500.0, max=-1.0,
                                 description="Y height below which the player gets an endlessfall death")

    def invoke(self, ctx, event):
        col = _active_level_col(ctx.scene)
        if col is None:
            self.report({"ERROR"}, "No active level"); return {"CANCELLED"}
        # Lazy-migrate every level missing og_level_index so collision checks see real values
        _migrate_all_level_indices(ctx.scene)
        self.level_name    = str(col.get("og_level_name", col.name))
        self.base_id       = int(col.get("og_base_id", 10000))
        self.level_index   = int(col.get("og_level_index", 100))
        self.vis_nick      = str(col.get("og_vis_nick_override", "") or "")
        self.bottom_height = float(col.get("og_bottom_height", -20.0))
        return ctx.window_manager.invoke_props_dialog(self)

    def execute(self, ctx):
        col = _active_level_col(ctx.scene)
        if col is None:
            self.report({"ERROR"}, "No active level"); return {"CANCELLED"}
        name = self.level_name.strip().lower().replace(" ", "-")
        if not name:
            self.report({"ERROR"}, "Level name cannot be empty"); return {"CANCELLED"}
        if len(name) > 10:
            self.report({"ERROR"}, f"Name '{name}' is {len(name)} chars — max 10"); return {"CANCELLED"}
        # Check for duplicate names (excluding self)
        for c in _all_level_collections(ctx.scene):
            if c.name != col.name and c.get("og_level_name", "") == name:
                self.report({"ERROR"}, f"A level named '{name}' already exists"); return {"CANCELLED"}

        # Check for duplicate level index (excluding self)
        if _level_index_in_use(ctx.scene, self.level_index, exclude_col=col):
            self.report({"ERROR"}, f"Level index {self.level_index} is already in use by another level")
            return {"CANCELLED"}

        # Validate + check vis nickname uniqueness (excluding self)
        nick_clean = self.vis_nick.strip().lower()
        if not nick_clean:
            nick_clean = _suggest_unique_vis_nick(ctx.scene, name, exclude_col=col)
        if len(nick_clean) > 3:
            self.report({"ERROR"}, f"Vis nickname '{nick_clean}' must be 3 characters or fewer")
            return {"CANCELLED"}
        if _vis_nick_in_use(ctx.scene, nick_clean, exclude_col=col):
            self.report({"ERROR"}, f"Vis nickname '{nick_clean}' is already used by another level")
            return {"CANCELLED"}

        col["og_level_name"]        = name
        col["og_base_id"]           = self.base_id
        col["og_level_index"]       = self.level_index
        col["og_vis_nick_override"] = nick_clean
        col["og_bottom_height"]     = max(-500.0, min(-1.0, self.bottom_height))
        col.name = name  # Keep collection name in sync
        # Update active_level reference since collection name changed
        ctx.scene.og_props.active_level = col.name
        self.report({"INFO"}, f"Level updated: '{name}' (ID {self.base_id}, index {self.level_index}, nick '{nick_clean}')")
        return {"FINISHED"}

class OG_OT_SetMusicZoneBank(bpy.types.Operator):
    """Pick a music bank for the selected music zone"""
    bl_idname   = "og.set_music_zone_bank"
    bl_label    = "Set Music Bank"
    bl_property = "bank"

    bank: bpy.props.EnumProperty(
        name="Music Bank",
        description="Select music bank for this zone",
        items=_MUSIC_BANK_ITEMS,
    )

    def execute(self, ctx):
        sel = ctx.active_object
        if sel and sel.name.startswith("AMBIENT_mus"):
            sel["og_music_bank"]  = self.bank
            sel["og_music_flava"] = "default"   # reset flava when bank changes
        return {"FINISHED"}

    def invoke(self, ctx, event):
        sel = ctx.active_object
        cur = sel.get("og_music_bank", "village1") if sel else "village1"
        if cur in [b[0] for b in _MUSIC_BANK_ITEMS]:
            self.bank = cur
        ctx.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

class OG_OT_SetMusicZoneFlava(bpy.types.Operator):
    """Pick a flava variant for the selected music zone"""
    bl_idname   = "og.set_music_zone_flava"
    bl_label    = "Set Music Flava"
    bl_property = "flava"

    flava: bpy.props.EnumProperty(
        name="Flava",
        description="Select music variant for this zone",
        items=_flava_items_for_active,
    )

    def execute(self, ctx):
        sel = ctx.active_object
        if sel and sel.name.startswith("AMBIENT_mus"):
            sel["og_music_flava"] = self.flava
        return {"FINISHED"}

    def invoke(self, ctx, event):
        ctx.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

class OG_OT_RemoveLevel(Operator):
    """Remove a custom level and all its files from the project."""
    bl_idname   = "og.remove_level"
    bl_label    = "Remove Level"
    bl_options  = {"REGISTER", "UNDO"}
    level_name: bpy.props.StringProperty()

    def invoke(self, ctx, event):
        return ctx.window_manager.invoke_confirm(self, event)

    def execute(self, ctx):
        if not self.level_name:
            self.report({"ERROR"}, "No level name given")
            return {"CANCELLED"}
        msgs = remove_level(self.level_name)
        for m in msgs:
            log(m)
        self.report({"INFO"}, f"Removed level '{self.level_name}'")
        return {"FINISHED"}

class OG_OT_RefreshLevels(Operator):
    """Refresh the custom levels list."""
    bl_idname = "og.refresh_levels"
    bl_label  = "Refresh"
    def execute(self, ctx):
        return {"FINISHED"}

class OG_OT_CreateGoalCodeBlock(bpy.types.Operator):
    """Create a new Blender text block pre-filled with GOAL boilerplate and assign it to this actor"""
    bl_idname = "og.create_goal_code_block"
    bl_label  = "Create GOAL Code Block"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        if not sel or sel.type != "EMPTY":
            return False
        parts = sel.name.split("_", 2)
        return (len(parts) >= 3 and parts[0] == "ACTOR"
                and "_wp_" not in sel.name and "_wpb_" not in sel.name)

    def execute(self, ctx):
        sel   = ctx.active_object
        parts = sel.name.split("_", 2)
        etype = parts[1]
        uid   = parts[2] if len(parts) >= 3 else "0"

        # Generate a unique text block name
        block_name = f"{etype}-goal-code"
        counter    = 0
        base_name  = block_name
        while block_name in bpy.data.texts:
            counter   += 1
            block_name = f"{base_name}-{counter}"

        # Create and fill the text block
        txt = bpy.data.texts.new(block_name)
        txt.write(_GOAL_BOILERPLATE.format(name=etype, etype=etype, uid=uid))
        txt.cursor_set(0)

        # Assign to this object
        sel.og_goal_code_ref.text_block = txt
        sel.og_goal_code_ref.enabled    = True

        self.report({"INFO"}, f"Created GOAL code block '{block_name}' — open it in the Text Editor to edit")
        return {"FINISHED"}

class OG_OT_ClearGoalCodeBlock(bpy.types.Operator):
    """Disconnect the GOAL code block from this actor (does not delete the text block)"""
    bl_idname  = "og.clear_goal_code_block"
    bl_label   = "Disconnect GOAL Code"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        return (sel is not None
                and sel.type == "EMPTY"
                and hasattr(sel, "og_goal_code_ref")
                and sel.og_goal_code_ref.text_block is not None)

    def execute(self, ctx):
        ctx.active_object.og_goal_code_ref.text_block = None
        return {"FINISHED"}

class OG_OT_OpenGoalCodeInEditor(bpy.types.Operator):
    """Switch an open Text Editor area to show this actor's GOAL code block, or report instructions if none is open"""
    bl_idname  = "og.open_goal_code_in_editor"
    bl_label   = "Open in Text Editor"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        return (sel is not None
                and hasattr(sel, "og_goal_code_ref")
                and sel.og_goal_code_ref.text_block is not None)

    def execute(self, ctx):
        txt = ctx.active_object.og_goal_code_ref.text_block
        for window in ctx.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "TEXT_EDITOR":
                    area.spaces.active.text = txt
                    self.report({"INFO"}, f"Showing '{txt.name}' in Text Editor")
                    return {"FINISHED"}
        self.report({"INFO"},
                    f"Open a Text Editor area (Shift+F11) then re-click. "
                    f"Block name: '{txt.name}'")
        return {"FINISHED"}

class OG_OT_ScanPaths(bpy.types.Operator):
    bl_idname   = "og.scan_paths"
    bl_label    = "Find Files"
    bl_description = "Recursively scan the root folder for OpenGOAL executables and game source folders"

    def execute(self, ctx):
        import re
        from pathlib import Path
        from ..build import _scan_for_installs
        prefs = ctx.preferences.addons.get("opengoal_tools")
        if not prefs:
            self.report({"ERROR"}, "Addon preferences not found"); return {"CANCELLED"}
        p = prefs.preferences
        raw = p.og_root_path.strip().rstrip("\\/")
        if not raw:
            self.report({"WARNING"}, "Set the OpenGOAL Root folder first"); return {"CANCELLED"}
        root = Path(raw)
        if not root.exists():
            self.report({"WARNING"}, f"Folder not found: {root}"); return {"CANCELLED"}

        exe_folders, data_folders = _scan_for_installs(root)

        def _rel(d: Path) -> str:
            try:
                return str(d.relative_to(root)).replace("\\", "/")
            except ValueError:
                return str(d)

        if not exe_folders and not data_folders:
            self.report({"WARNING"},
                "Nothing found — no exe folders (gk+goalc) or data folders (goal_src) "
                "under the root. Use Manual path overrides below.")
            return {"CANCELLED"}

        # Auto-select best exe version (highest semver, else last sorted)
        if exe_folders:
            def _ver_key(d: Path):
                m = re.search(r"(\d+)[._-](\d+)[._-](\d+)", d.name)
                return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)
            exe_folders.sort(key=_ver_key, reverse=True)
            p.og_active_version = _rel(exe_folders[0])

        # Auto-select data folder (prefer one named "active", else first found)
        if data_folders:
            active_pref = next(
                (d for d in data_folders if "active" in str(d).lower()), data_folders[0]
            )
            p.og_active_data = _rel(active_pref)

        parts = []
        if exe_folders:
            parts.append(f"{len(exe_folders)} exe folder(s) — selected: {p.og_active_version}")
        if data_folders:
            parts.append(f"{len(data_folders)} data folder(s) — selected: {p.og_active_data}")
        self.report({"INFO"}, "Found " + " | ".join(parts))
        return {"FINISHED"}


# ─── Classes to register ───────────────────────────────────────────────────
CLASSES = (
    OG_OT_CreateLevel,
    OG_OT_AssignCollectionAsLevel,
    OG_OT_SetActiveLevel,
    OG_OT_NudgeLevelProp,
    OG_OT_DeleteLevel,
    OG_OT_AddCollectionToLevel,
    OG_OT_RemoveCollectionFromLevel,
    OG_OT_RemoveCollectionFromLevelActive,
    OG_OT_ToggleCollectionNoExport,
    OG_OT_SelectLevelCollection,
    OG_OT_EditLevel,
    OG_OT_SetMusicZoneBank,
    OG_OT_SetMusicZoneFlava,
    OG_OT_RemoveLevel,
    OG_OT_RefreshLevels,
    OG_OT_CreateGoalCodeBlock,
    OG_OT_ClearGoalCodeBlock,
    OG_OT_OpenGoalCodeInEditor,
    OG_OT_ScanPaths,
)
