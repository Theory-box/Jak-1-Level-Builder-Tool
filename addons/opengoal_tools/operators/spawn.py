# ───────────────────────────────────────────────────────────────────────
# operators/spawn.py — OpenGOAL Level Tools
#
# Spawn operators: create new entities, volumes, cameras, cutscene triggers, sound emitters, music zones, waypoints.
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

# ─── Rescued module-level symbols (from original operators.py) ────────────
_VALID_ETYPE_RE = _re.compile(r'^[a-z][a-z0-9\-]*$')



class OG_OT_SpawnPlayer(Operator):
    bl_idname = "og.spawn_player"
    bl_label  = "Add Player Spawn"
    bl_description = "Place a player spawn empty at the 3D cursor"
    def execute(self, ctx):
        n   = len([o for o in _level_objects(ctx.scene) if o.name.startswith("SPAWN_") and not o.name.endswith("_CAM")])
        uid = "start" if n == 0 else f"spawn{n}"
        bpy.ops.object.empty_add(type="CONE", location=ctx.scene.cursor.location)
        o = ctx.active_object
        o.name = f"SPAWN_{uid}"; o.show_name = True
        o.empty_display_size = 1.0; o.color = (0.0,1.0,0.0,1.0)
        o.rotation_euler[2] = math.pi  # cone tip points +Y by default; flip to -Y (game forward)
        _link_object_to_sub_collection(ctx.scene, o, *_COL_PATH_SPAWNS)
        self.report({"INFO"}, f"Added {o.name}")
        return {"FINISHED"}

class OG_OT_SpawnCheckpoint(Operator):
    bl_idname = "og.spawn_checkpoint"
    bl_label  = "Add Checkpoint"
    bl_description = (
        "Place a mid-level checkpoint empty at the 3D cursor. "
        "The engine auto-assigns the nearest zero-flag checkpoint as the player "
        "moves around, so these act as silent progress saves without any trigger actors."
    )
    def execute(self, ctx):
        n   = len([o for o in _level_objects(ctx.scene) if o.name.startswith("CHECKPOINT_") and not o.name.endswith("_CAM")])
        uid = f"cp{n}"
        bpy.ops.object.empty_add(type="CONE", location=ctx.scene.cursor.location)
        o = ctx.active_object
        o.name = f"CHECKPOINT_{uid}"; o.show_name = True
        o.empty_display_size = 1.2; o.color = (1.0, 0.85, 0.0, 1.0)
        o.rotation_euler[2] = math.pi  # cone tip points +Y by default; flip to -Y (game forward)
        o["og_checkpoint_radius"] = 3.0
        _link_object_to_sub_collection(ctx.scene, o, *_COL_PATH_SPAWNS)
        self.report({"INFO"}, f"Added {o.name}")
        return {"FINISHED"}

class OG_OT_SpawnCamAnchor(Operator):
    bl_idname = "og.spawn_cam_anchor"
    bl_label  = "Add Spawn Camera"
    bl_description = (
        "Place a camera-anchor empty linked to the selected SPAWN_ or CHECKPOINT_ empty. "
        "This sets the camera position and orientation used when the player respawns at that point."
    )
    def execute(self, ctx):
        sel = ctx.active_object
        if sel is None or sel.type != "EMPTY":
            self.report({"ERROR"}, "Select a SPAWN_ or CHECKPOINT_ empty first")
            return {"CANCELLED"}
        is_spawn = sel.name.startswith("SPAWN_") or sel.name.startswith("CHECKPOINT_")
        if not is_spawn:
            self.report({"ERROR"}, "Selected object must be a SPAWN_ or CHECKPOINT_ empty")
            return {"CANCELLED"}
        cam_name = sel.name + "_CAM"
        if ctx.scene.objects.get(cam_name):
            self.report({"WARNING"}, f"{cam_name} already exists")
            return {"CANCELLED"}
        # Place camera 6m behind and 3m above spawn in Blender space
        offset = mathutils.Vector((0.0, -6.0, 3.0))
        loc    = sel.matrix_world.translation + sel.matrix_world.to_3x3() @ offset
        bpy.ops.object.empty_add(type="ARROWS", location=loc)
        o = ctx.active_object
        o.name = cam_name; o.show_name = True
        o.empty_display_size = 0.8; o.color = (0.2, 0.6, 1.0, 1.0)
        # Point it toward the spawn (face -Z toward spawn so camera looks at it)
        direction = sel.matrix_world.translation - loc
        if direction.length > 1e-4:
            rot_quat = direction.to_track_quat('-Z', 'Y')
            o.rotation_euler = rot_quat.to_euler()
        # Parent to the spawn/checkpoint so it moves with it
        o.parent = sel
        o.matrix_parent_inverse = sel.matrix_world.inverted()
        _link_object_to_sub_collection(ctx.scene, o, *_COL_PATH_SPAWNS)
        self.report({"INFO"}, f"Added {cam_name}")
        return {"FINISHED"}

class OG_OT_SpawnEntity(Operator):
    bl_idname = "og.spawn_entity"
    bl_label  = "Add Entity"
    bl_description = "Place selected entity at the 3D cursor"
    # Which OGProperties prop holds the selected type. Sub-panels set this
    # so the operator reads from the correct per-category dropdown.
    source_prop: bpy.props.StringProperty(default="entity_type")

    def execute(self, ctx):
        props = ctx.scene.og_props
        # Read from the per-category prop if specified, else fall back to entity_type
        etype = getattr(props, self.source_prop, None) or props.entity_type
        # Keep entity_type in sync so export / wiki preview stay consistent
        if hasattr(props, "entity_type"):
            try: props.entity_type = etype
            except Exception: pass
        info  = ENTITY_DEFS.get(etype, {})
        shape = info.get("shape", "SPHERE")
        color = info.get("color", (1.0,0.5,0.1,1.0))
        n     = len([o for o in _level_objects(ctx.scene) if o.name.startswith(f"ACTOR_{etype}_")])
        bpy.ops.object.empty_add(type=shape, location=ctx.scene.cursor.location)
        o = ctx.active_object
        o.name = f"ACTOR_{etype}_{n}"
        o.show_name = True
        o.empty_display_size = 0.6
        o.color = color
        _link_object_to_sub_collection(ctx.scene, o, *_col_path_for_entity(etype))
        if etype == "crate":
            o["og_crate_type"]          = ctx.scene.og_props.crate_type
            o["og_crate_pickup"]        = "money"
            o["og_crate_pickup_amount"] = 1
        if etype in NAV_UNSAFE_TYPES:
            o["og_nav_radius"] = ctx.scene.og_props.nav_radius
            self.report({"WARNING"},
                f"Added {o.name}  —  nav-mesh workaround will be applied on export. "
                f"Enemy will idle/notice but won't pathfind without a real navmesh.")
        elif etype in NEEDS_PATHB_TYPES:
            self.report({"WARNING"},
                f"Added {o.name}  —  swamp-bat needs TWO path sets: "
                f"waypoints named _wp_00/_wp_01... AND _wpb_00/_wpb_01... (second patrol route).")
        elif etype in NEEDS_PATH_TYPES:
            self.report({"WARNING"},
                f"Added {o.name}  —  this entity requires at least 1 waypoint (_wp_00). "
                f"It will crash or error at runtime without a path.")
        elif etype in IS_PROP_TYPES:
            self.report({"INFO"}, f"Added {o.name}  (prop — idle animation only, no AI/combat)")
        else:
            self.report({"INFO"}, f"Added {o.name}")

        # ---- Set default custom props so UI fields render immediately ------
        if _actor_is_enemy(etype):
            o["og_idle_distance"] = 80.0
            o["og_vis_dist"]      = 200.0
        if _actor_is_spawner(etype):
            o["og_num_lurkers"] = -1
        if etype == "orb-cache-top":
            o["og_orb_count"] = 20
        if etype == "sunkenfisha":
            o["og_fish_count"] = 1
        if etype in {"lavaballoon", "darkecobarrel"}:
            o["og_move_speed"] = 3.0 if etype == "lavaballoon" else 15.0

        # ---- Model preview ------------------------------------------------
        _prefs = bpy.context.preferences.addons.get("opengoal_tools")
        if _prefs and _prefs.preferences.preview_models:
            try:
                attached = _mp.attach_preview(ctx, etype, o)
                if not attached and ENTITY_DEFS.get(etype, {}).get("glb"):
                    self.report({"WARNING"}, f"No GLB for {etype} — delete decompiler_out/jak1/ and re-run extractor")
            except Exception as e:
                # Never crash the spawn operator over a preview failure
                log(f"model_preview: {e}")

        return {"FINISHED"}

class OG_OT_DuplicateEntity(Operator):
    """Duplicate the selected ACTOR empty and re-attach its preview mesh."""
    bl_idname   = "og.duplicate_entity"
    bl_label    = "Duplicate Entity"
    bl_description = "Duplicate this entity and carry its preview mesh to the copy"
    bl_options  = {"UNDO"}

    def execute(self, ctx):
        src = ctx.active_object
        if src is None or not src.name.startswith("ACTOR_"):
            self.report({"ERROR"}, "Select an ACTOR_ empty first")
            return {"CANCELLED"}

        # Parse entity type from name: ACTOR_<etype>_<uid>
        parts = src.name.split("_", 2)
        if len(parts) < 3:
            self.report({"ERROR"}, f"Cannot parse entity type from {src.name!r}")
            return {"CANCELLED"}
        etype = parts[1]

        # --- Duplicate just the empty (no children) via ops ---
        # Deselect all, select only the source, then duplicate
        bpy.ops.object.select_all(action="DESELECT")
        src.select_set(True)
        ctx.view_layer.objects.active = src
        bpy.ops.object.duplicate(linked=False, mode="TRANSLATION")
        new_empty = ctx.active_object

        # Give it a fresh unique name (Blender appends .001 etc automatically,
        # but we want to follow the ACTOR_<etype>_<n> convention)
        prefix = f"ACTOR_{etype}_"
        # Use bpy.data.objects (not just level objects) so we avoid collisions
        # with the freshly duplicated object which may not yet be in the level col
        existing = {o.name for o in bpy.data.objects}
        n = 0
        while f"{prefix}{n}" in existing:
            n += 1
        new_empty.name = f"{prefix}{n}"

        # --- Strip any preview children the duplicate inherited ---
        # bpy.ops.object.duplicate copies children too; remove them so we
        # can attach a fresh independent preview below.
        _mp.remove_preview(new_empty)

        # Also unlink any child objects Blender may have copied
        for child in list(new_empty.children):
            if child.get(_mp._PREVIEW_PROP) or child.get(_mp._WAYPOINT_PREVIEW_PROP):
                bpy.data.objects.remove(child, do_unlink=True)

        # --- Re-attach a fresh preview mesh ---
        _prefs = bpy.context.preferences.addons.get("opengoal_tools")
        if _prefs and _prefs.preferences.preview_models:
            try:
                _mp.attach_preview(ctx, etype, new_empty)
            except Exception as e:
                log(f"duplicate_entity model_preview: {e}")

        self.report({"INFO"}, f"Duplicated as {new_empty.name}")
        return {"FINISHED"}

class OG_OT_ClearPreviews(Operator):
    bl_idname   = "og.clear_previews"
    bl_label    = "Clear Preview Models"
    bl_description = "Remove all enemy preview meshes from the scene"

    def execute(self, ctx):
        n = _mp.remove_all_previews(ctx.scene)
        self.report({"INFO"}, f"Removed {n} preview mesh{'es' if n != 1 else ''}")
        return {"FINISHED"}

class OG_OT_PickSound(Operator):
    """Open sound picker — choose a sound then click OK to place an emitter"""
    bl_idname   = "og.pick_sound"
    bl_label    = "Pick Sound"
    bl_property = "sfx_sound"

    sfx_sound: bpy.props.EnumProperty(
        name="Sound",
        description="Select a sound to place",
        items=ALL_SFX_ITEMS,
    )

    def execute(self, ctx):
        # Just store the selected sound — emitter is placed separately via Add Emitter
        ctx.scene.og_props.sfx_sound = self.sfx_sound
        snd = self.sfx_sound.split("__")[0] if "__" in self.sfx_sound else self.sfx_sound
        self.report({"INFO"}, f"Sound selected: {snd}")
        return {"FINISHED"}

    def invoke(self, ctx, event):
        self.sfx_sound = ctx.scene.og_props.sfx_sound
        ctx.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

class OG_OT_AddSoundEmitter(Operator):
    """Add a sound emitter empty at the 3D cursor"""
    bl_idname  = "og.add_sound_emitter"
    bl_label   = "Add Sound Emitter"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        props = ctx.scene.og_props
        snd   = props.sfx_sound.split("__")[0] if "__" in props.sfx_sound else props.sfx_sound
        if not snd:
            snd = "waterfall"
        existing = [o for o in _level_objects(ctx.scene) if o.name.startswith("AMBIENT_snd")]
        idx  = len(existing) + 1
        name = f"AMBIENT_snd{idx:03d}"

        bpy.ops.object.empty_add(type="SPHERE", location=ctx.scene.cursor.location)
        o = ctx.active_object
        o.name = name
        o.show_name = True
        o.empty_display_size = max(0.3, props.ambient_default_radius * 0.05)
        o.color = (0.2, 0.8, 1.0, 1.0)

        # Stamp editable custom props
        o["og_sound_name"]   = snd
        o["og_sound_radius"] = props.ambient_default_radius
        o["og_sound_mode"]   = "loop"

        _link_object_to_sub_collection(ctx.scene, o, *_COL_PATH_SOUND_EMITTERS)
        self.report({"INFO"}, f"Added '{name}' → {snd}")
        return {"FINISHED"}

class OG_OT_AddMusicZone(Operator):
    """Add a music ambient zone (sphere) at the 3D cursor.
    When the player enters the bsphere the engine calls set-setting! 'music.
    One large zone covering the whole level is the standard setup."""
    bl_idname  = "og.add_music_zone"
    bl_label   = "Add Music Zone"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        props = ctx.scene.og_props
        bank     = props.og_music_amb_bank
        flava    = props.og_music_amb_flava
        priority = props.og_music_amb_priority
        radius   = props.og_music_amb_radius

        existing = [o for o in _level_objects(ctx.scene) if o.name.startswith("AMBIENT_mus")]
        idx  = len(existing) + 1
        name = f"AMBIENT_mus{idx:03d}"

        bpy.ops.object.empty_add(type="SPHERE", location=ctx.scene.cursor.location)
        o = ctx.active_object
        o.name = name
        o.show_name = True
        o.empty_display_size = max(0.3, radius * 0.04)
        o.color = (1.0, 0.85, 0.1, 1.0)   # gold — distinct from sound emitters (cyan)

        o["og_music_bank"]     = bank
        o["og_music_flava"]    = flava
        o["og_music_priority"] = priority
        o["og_music_radius"]   = radius

        _link_object_to_sub_collection(ctx.scene, o, *_COL_PATH_SOUND_EMITTERS)
        self.report({"INFO"}, f"Added '{name}' → music:{bank} flava:{flava}")
        return {"FINISHED"}

class OG_OT_SpawnCamera(Operator):
    bl_idname = "og.spawn_camera"
    bl_label  = "Add Camera"
    bl_description = (
        "Place a Blender camera at the 3D cursor.\n"
        "Named CAMERA_0, CAMERA_1 etc.\n"
        "Look through it with Numpad-0 to preview the game view.\n"
        "Link a trigger volume mesh with 'Link Trigger Volume'."
    )
    def execute(self, ctx):
        n = len([o for o in _level_objects(ctx.scene)
                 if o.name.startswith("CAMERA_") and o.type == "CAMERA"])
        cam_name = f"CAMERA_{n}"
        bpy.ops.object.camera_add(location=ctx.scene.cursor.location)
        o = ctx.active_object
        # Set name twice: Blender resolves duplicate data-block names after the
        # first assignment, so the second set lands the exact name we want.
        o.name      = cam_name
        o.name      = cam_name
        o.data.name = cam_name
        o.show_name = True
        o.color = (0.0, 0.8, 0.9, 1.0)
        # Default custom properties
        o["og_cam_mode"]   = "fixed"
        o["og_cam_interp"] = 1.0
        o["og_cam_fov"]    = 0.0
        o["og_cam_look_at"] = ""
        _link_object_to_sub_collection(ctx.scene, o, *_COL_PATH_CAMERAS)
        self.report({"INFO"}, f"Added {o.name}  |  Numpad-0 to look through it")
        return {"FINISHED"}

class OG_OT_SpawnVolume(Operator):
    """Spawn a generic trigger volume (VOL_N wireframe cube).
    If the active object is a linkable target (CAMERA_, SPAWN_, CHECKPOINT_),
    the volume is auto-linked to it immediately on spawn."""
    bl_idname = "og.spawn_volume"
    bl_label  = "Add Trigger Volume"
    bl_description = (
        "Add a box mesh trigger volume at the 3D cursor. "
        "If a camera, spawn, or checkpoint is selected, it auto-links."
    )
    def execute(self, ctx):
        n = len([o for o in _level_objects(ctx.scene)
                 if o.type == "MESH" and o.name.startswith("VOL_")])
        bpy.ops.mesh.primitive_cube_add(size=4.0, location=ctx.scene.cursor.location)
        vol = ctx.active_object
        vol.name = f"VOL_{n}"
        vol["og_vol_id"] = n          # numeric id used for naming when 0 or 2+ links
        vol.show_name = True
        vol.display_type = "WIRE"
        vol.color = (0.0, 0.9, 0.3, 0.4)
        vol.set_invisible = True
        vol.set_collision = True
        vol.ignore        = True

        # Auto-link if a target name was stamped on the scene by invoke()
        target_name = ctx.scene.get("_pending_vol_target", "")
        if target_name:
            target = ctx.scene.objects.get(target_name)
            if target:
                links = _vol_links(vol)
                entry = links.add()
                entry.target_name = target_name
                entry.behaviour   = "cue-chase"
                _rename_vol_for_links(vol)
                ctx.scene["_pending_vol_target"] = ""
                _link_object_to_sub_collection(ctx.scene, vol, *_COL_PATH_TRIGGERS)
                self.report({"INFO"}, f"Added and linked {vol.name} → {target_name}")
                return {"FINISHED"}

        ctx.scene["_pending_vol_target"] = ""
        _link_object_to_sub_collection(ctx.scene, vol, *_COL_PATH_TRIGGERS)
        self.report({"INFO"}, f"Added {vol.name}  —  select volume + target → Link in Triggers panel")
        return {"FINISHED"}

    def invoke(self, ctx, event):
        # Store active object name before adding geometry changes active
        sel = ctx.active_object
        if sel and _is_linkable(sel):
            # Block duplicate camera/checkpoint links; aggro targets allow multiple
            if not _is_aggro_target(sel):
                existing = _vol_for_target(ctx.scene, sel.name)
                if existing:
                    self.report({"WARNING"}, f"{sel.name} already has {existing.name} linked — unlink first")
                    return {"CANCELLED"}
            ctx.scene["_pending_vol_target"] = sel.name
        else:
            ctx.scene["_pending_vol_target"] = ""
        return self.execute(ctx)

class OG_OT_SpawnVolumeAutoLink(Operator):
    """Internal: spawn a volume and auto-link to the given target."""
    bl_idname = "og.spawn_volume_autolink"
    bl_label  = "Add & Link Trigger Volume"
    bl_description = "Spawn a trigger volume and immediately link it to the active object"

    target_name: bpy.props.StringProperty()

    def execute(self, ctx):
        target = ctx.scene.objects.get(self.target_name)
        if not target:
            self.report({"ERROR"}, f"Target {self.target_name} not found")
            return {"CANCELLED"}
        # Cameras / checkpoints: 1:1 (block duplicate). Aggro enemies: allow multiple.
        if not _is_aggro_target(target):
            existing = _vol_for_target(ctx.scene, self.target_name)
            if existing:
                self.report({"WARNING"}, f"{self.target_name} already linked to {existing.name} — unlink first")
                return {"CANCELLED"}
        n = len([o for o in _level_objects(ctx.scene) if o.type == "MESH" and o.name.startswith("VOL_")])
        # Place at target location
        bpy.ops.mesh.primitive_cube_add(size=4.0, location=target.location)
        vol = ctx.active_object
        vol.name = f"VOL_{n}"   # interim — _rename_vol_for_links replaces this
        vol["og_vol_id"] = n
        vol.show_name = True
        vol.display_type = "WIRE"
        vol.set_invisible = True
        vol.set_collision = True
        vol.ignore        = True
        if target.type == "CAMERA":
            vol.color = (0.0, 0.9, 0.3, 0.4)   # green — camera
        elif _is_aggro_target(target):
            vol.color = (1.0, 0.3, 0.0, 0.4)   # red-orange — aggro
        else:
            vol.color = (1.0, 0.85, 0.0, 0.4)  # yellow — checkpoint
        links = _vol_links(vol)
        entry = links.add()
        entry.target_name = self.target_name
        entry.behaviour   = "cue-chase"
        _rename_vol_for_links(vol)
        _link_object_to_sub_collection(ctx.scene, vol, *_COL_PATH_TRIGGERS)
        self.report({"INFO"}, f"Added {vol.name} → {self.target_name}")
        return {"FINISHED"}

class OG_OT_SpawnAggroTrigger(Operator):
    """Spawn a new trigger volume at an enemy's location and link it as aggro.
    Used by the per-enemy 'Add Aggro Trigger' button in the selected-actor panel.
    Multiple aggro triggers per enemy are allowed.
    """
    bl_idname   = "og.spawn_aggro_trigger"
    bl_label    = "Add Aggro Trigger"
    bl_options  = {"REGISTER", "UNDO"}
    bl_description = "Spawn a new trigger volume at this enemy and link it as aggro"

    target_name: bpy.props.StringProperty()

    def execute(self, ctx):
        target = ctx.scene.objects.get(self.target_name)
        if not target:
            self.report({"ERROR"}, f"Target '{self.target_name}' not found")
            return {"CANCELLED"}
        if not _is_aggro_target(target):
            self.report({"ERROR"}, f"{self.target_name} is not a nav-enemy")
            return {"CANCELLED"}
        n = len([o for o in _level_objects(ctx.scene)
                 if o.type == "MESH" and o.name.startswith("VOL_")])
        bpy.ops.mesh.primitive_cube_add(size=4.0, location=target.location)
        vol = ctx.active_object
        vol.name = f"VOL_{n}"
        vol["og_vol_id"] = n
        vol.show_name = True
        vol.display_type = "WIRE"
        vol.color = (1.0, 0.3, 0.0, 0.4)   # red-orange aggro
        vol.set_invisible = True
        vol.set_collision = True
        vol.ignore        = True
        links = _vol_links(vol)
        entry = links.add()
        entry.target_name = self.target_name
        entry.behaviour   = "cue-chase"
        _rename_vol_for_links(vol)
        _link_object_to_sub_collection(ctx.scene, vol, *_COL_PATH_TRIGGERS)
        self.report({"INFO"}, f"Added {vol.name} → {self.target_name}")
        return {"FINISHED"}

class OG_OT_SpawnCamAlign(Operator):
    bl_idname = "og.spawn_cam_align"
    bl_label  = "Add Player Anchor"
    bl_description = (
        "Add a CAMERA_N_ALIGN empty for standoff (side-scroller) mode.\n"
        "Place this at the player position the camera tracks.\n"
        "The camera stays at a fixed offset from this anchor."
    )
    def execute(self, ctx):
        sel = ctx.active_object
        if not sel or not sel.name.startswith("CAMERA_") or sel.type != "CAMERA":
            self.report({"ERROR"}, "Select a CAMERA_N camera first")
            return {"CANCELLED"}
        align_name = sel.name + "_ALIGN"
        if ctx.scene.objects.get(align_name):
            self.report({"WARNING"}, f"{align_name} already exists")
            return {"CANCELLED"}
        bpy.ops.object.empty_add(type="PLAIN_AXES", location=ctx.scene.cursor.location)
        o = ctx.active_object
        o.name = align_name
        o.show_name = True
        o.empty_display_size = 0.5
        o.color = (1.0, 0.6, 0.0, 1.0)
        self.report({"INFO"}, f"Added {align_name}  —  place at player anchor position")
        return {"FINISHED"}

class OG_OT_SpawnCamPivot(Operator):
    bl_idname = "og.spawn_cam_pivot"
    bl_label  = "Add Orbit Pivot"
    bl_description = (
        "Add a CAMERA_N_PIVOT empty for orbit mode.\n"
        "The camera orbits around this world position following the player angle."
    )
    def execute(self, ctx):
        sel = ctx.active_object
        if not sel or not sel.name.startswith("CAMERA_") or sel.type != "CAMERA":
            self.report({"ERROR"}, "Select a CAMERA_N camera first")
            return {"CANCELLED"}
        pivot_name = sel.name + "_PIVOT"
        if ctx.scene.objects.get(pivot_name):
            self.report({"WARNING"}, f"{pivot_name} already exists")
            return {"CANCELLED"}
        bpy.ops.object.empty_add(type="SPHERE", location=ctx.scene.cursor.location)
        o = ctx.active_object
        o.name = pivot_name
        o.show_name = True
        o.empty_display_size = 0.5
        o.color = (1.0, 0.2, 0.8, 1.0)
        self.report({"INFO"}, f"Added {pivot_name}  —  place at orbit center point")
        return {"FINISHED"}

class OG_OT_SpawnCamLookAt(Operator):
    bl_idname = "og.spawn_cam_look_at"
    bl_label  = "Add Look-At Target"
    bl_description = (
        "Add an empty that the camera will always face.\n"
        "Bypasses quaternion export — just point the camera at a world position.\n"
        "Place the empty on the object / area you want the camera to look at."
    )
    def execute(self, ctx):
        sel = ctx.active_object
        if not sel or not sel.name.startswith("CAMERA_") or sel.type != "CAMERA":
            self.report({"ERROR"}, "Select a CAMERA_N camera first")
            return {"CANCELLED"}
        look_name = sel.name + "_LOOKAT"
        bpy.ops.object.empty_add(type="ARROWS", location=ctx.scene.cursor.location)
        o = ctx.active_object
        o.name = look_name
        o.show_name = True
        o.empty_display_size = 0.4
        o.color = (1.0, 0.8, 0.0, 1.0)
        sel["og_cam_look_at"] = look_name
        self.report({"INFO"}, f"Added {look_name}  —  move it to where the camera should look")
        return {"FINISHED"}

class OG_OT_AddLauncherDest(Operator):
    """Add a DEST_ empty at the 3D cursor and link it to this launcher."""
    bl_idname  = "og.add_launcher_dest"
    bl_label   = "Add Launcher Destination"
    bl_options = {"REGISTER", "UNDO"}

    launcher_name: bpy.props.StringProperty()

    def execute(self, ctx):
        launcher = bpy.data.objects.get(self.launcher_name)
        if not launcher:
            return {"CANCELLED"}
        uid = self.launcher_name.split("_", 2)[-1] if "_" in self.launcher_name else "0"
        bpy.ops.object.empty_add(type="ARROWS", location=ctx.scene.cursor.location)
        dest = ctx.active_object
        dest.name = f"DEST_{uid}"
        dest.show_name = True
        dest.empty_display_size = 0.5
        dest.color = (1.0, 0.5, 0.0, 1.0)
        launcher["og_launcher_dest"] = dest.name
        self.report({"INFO"}, f"Added {dest.name} and linked to {self.launcher_name}")
        return {"FINISHED"}

class OG_OT_AddWaterVolume(Operator):
    """Add a water volume mesh at the 3D cursor.
Place and scale it to cover your water area — rotation is supported."""
    bl_idname  = "og.add_water_volume"
    bl_label   = "Add Water Volume"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        scene = ctx.scene

        # Name: WATER_0, WATER_1, etc. Count only in current level objects.
        existing = [o for o in _level_objects(scene) if o.name.startswith("WATER_")]
        idx  = len(existing)
        name = f"WATER_{idx}"

        # Create a cube mesh — primitive_cube_add sets it as the active object
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=ctx.scene.cursor.location)
        o      = ctx.active_object
        # Set name twice: Blender resolves data-block name conflicts after first set
        o.name = name
        o.name = name

        # Style: wireframe blue so it doesn't obscure the level
        o.display_type   = "WIRE"
        o.color          = (0.1, 0.4, 1.0, 0.5)
        o.show_name      = True
        # set_invisible tells the level builder to skip this mesh entirely —
        # it exports via extras in the GLB but generates no geometry or collision
        o.set_invisible  = True

        # Lock rotation — water-vol uses an AABB, rotation has no effect in-game
        o.lock_rotation[0] = True
        o.lock_rotation[1] = True
        o.lock_rotation[2] = True

        # Set default water properties from cursor Z (game Y)
        surface_y = round(ctx.scene.cursor.location.z, 4)
        o["og_water_surface"] = surface_y
        o["og_water_wade"]    = 0.5   # depth below surface in meters
        o["og_water_swim"]    = 1.0   # depth below surface in meters
        o["og_water_bottom"]  = round(surface_y - 5.0, 4)  # absolute Y of kill floor
        o["og_water_attack"]  = "drown"

        # Link into the level collection
        _link_object_to_sub_collection(scene, o, *_COL_PATH_WATER)

        self.report({"INFO"}, f"Added {name} — scale to cover your water area, then export")
        return {"FINISHED"}

class OG_OT_SpawnPlatform(Operator):
    """Place a platform actor empty at the 3D cursor."""
    bl_idname     = "og.spawn_platform"
    bl_label      = "Add Platform"
    bl_description = "Place a platform actor at the 3D cursor"

    def execute(self, ctx):
        etype = ctx.scene.og_props.platform_type
        einfo = ENTITY_DEFS.get(etype, {})

        # Use count of existing same-type actors as uid, matching OG_OT_SpawnEntity pattern
        n   = len([o for o in _level_objects(ctx.scene) if o.name.startswith(f"ACTOR_{etype}_")])
        uid = f"{n:04d}"

        bpy.ops.object.empty_add(type=einfo.get("shape", "CUBE"),
                                 location=ctx.scene.cursor.location)
        o = ctx.active_object
        o.name               = f"ACTOR_{etype}_{uid}"
        o.show_name          = True
        o.empty_display_size = 0.5
        o.color              = einfo.get("color", (0.5, 0.5, 0.8, 1.0))
        if hasattr(o, "show_in_front"):
            o.show_in_front = True
        _link_object_to_sub_collection(ctx.scene, o, *_COL_PATH_SPAWNABLE_PLATFORMS)

        # ---- Set default custom props so UI fields render immediately ------
        if einfo.get("needs_sync"):
            o["og_sync_period"]   = 4.0
            o["og_sync_phase"]    = 0.0
            o["og_sync_ease_out"] = 0.15
            o["og_sync_ease_in"]  = 0.15
            o["og_sync_wrap"]     = 0
        if einfo.get("needs_notice_dist"):
            o["og_notice_dist"] = -1.0

        self.report({"INFO"}, f"Added {o.name}")

        # ---- Model preview ------------------------------------------------
        _prefs = bpy.context.preferences.addons.get("opengoal_tools")
        if _prefs and _prefs.preferences.preview_models:
            try:
                attached = _mp.attach_preview(ctx, etype, o)
                if not attached and ENTITY_DEFS.get(etype, {}).get("glb"):
                    self.report({"WARNING"}, f"No GLB for {etype} — delete decompiler_out/jak1/ and re-run extractor")
            except Exception as e:
                log(f"model_preview: {e}")

        return {"FINISHED"}

class OG_OT_PickNavMesh(Operator):
    """Link the active mesh object as the navmesh for the selected enemy actor.
    Select the enemy, then shift-click the navmesh quad, then click this button."""
    bl_idname      = "og.pick_navmesh"
    bl_label       = "Pick NavMesh Mesh"
    bl_description = "Select enemy actor(s) + navmesh mesh (active), then click"

    actor_name: bpy.props.StringProperty()

    def execute(self, ctx):
        actor = bpy.data.objects.get(self.actor_name)
        if not actor:
            self.report({"ERROR"}, f"Actor not found: {self.actor_name}")
            return {"CANCELLED"}

        # Active object must be a mesh to use as navmesh
        active = ctx.active_object
        if not active or active.type != "MESH":
            self.report({"ERROR"}, "Make the navmesh quad the active object (shift-click it last)")
            return {"CANCELLED"}

        if active == actor:
            self.report({"ERROR"}, "Active object must be the navmesh mesh, not the enemy")
            return {"CANCELLED"}

        # Mark it as a navmesh object
        active["og_navmesh"] = True

        # Link actor to this mesh
        actor["og_navmesh_link"] = active.name
        self.report({"INFO"}, f"Linked {actor.name} → {active.name}")
        return {"FINISHED"}

class OG_OT_SpawnCustomType(bpy.types.Operator):
    """Spawn an ACTOR_ empty for a user-defined GOAL type.

    The type name must:
      • be lowercase letters, digits, and hyphens only
      • not already exist in the addon's built-in entity list
      • match the deftype name written in your GOAL code block exactly

    The empty is placed at the 3D cursor and named ACTOR_<typename>_<n>.
    Attach a GOAL code block via the GOAL Code sub-panel to define its behaviour.
    """
    bl_idname  = "og.spawn_custom_type"
    bl_label   = "Spawn Custom Type"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, ctx):
        name = (ctx.scene.og_props.custom_type_name or "").strip()
        return bool(name)

    def execute(self, ctx):
        etype = (ctx.scene.og_props.custom_type_name or "").strip().lower()

        if not etype:
            self.report({"ERROR"}, "Enter a type name first")
            return {"CANCELLED"}

        if not _VALID_ETYPE_RE.match(etype):
            self.report({"ERROR"},
                f"'{etype}' is not a valid type name. "
                "Use lowercase letters, digits, and hyphens only (e.g. 'spin-prop').")
            return {"CANCELLED"}

        if not _is_custom_type(etype):
            self.report({"ERROR"},
                f"'{etype}' is already a built-in entity type. "
                "Use the normal Spawn sub-panels to place it, or choose a different name.")
            return {"CANCELLED"}

        n = len([o for o in _level_objects(ctx.scene)
                 if o.name.startswith(f"ACTOR_{etype}_")])

        bpy.ops.object.empty_add(type="SPHERE", location=ctx.scene.cursor.location)
        o = ctx.active_object
        o.name               = f"ACTOR_{etype}_{n}"
        o.show_name          = True
        o.empty_display_size = 0.5
        # Distinctive yellow-green colour so custom types stand out from built-ins
        o.color = (0.6, 1.0, 0.2, 1.0)

        # Link into the level collection (Props sub-collection is the best fit
        # for a generic unknown type — no AI, no navmesh assumed)
        _link_object_to_sub_collection(
            ctx.scene, o, *_col_path_for_entity("evilplant"))  # reuse Props path

        self.report({"INFO"},
            f"Spawned '{o.name}' — open the GOAL Code panel to assign a code block, "
            f"then define 'deftype {etype}' in that block.")
        return {"FINISHED"}


# ─── Classes to register ───────────────────────────────────────────────────
CLASSES = (
    OG_OT_SpawnPlayer,
    OG_OT_SpawnCheckpoint,
    OG_OT_SpawnCamAnchor,
    OG_OT_SpawnEntity,
    OG_OT_DuplicateEntity,
    OG_OT_ClearPreviews,
    OG_OT_PickSound,
    OG_OT_AddSoundEmitter,
    OG_OT_AddMusicZone,
    OG_OT_SpawnCamera,
    OG_OT_SpawnVolume,
    OG_OT_SpawnVolumeAutoLink,
    OG_OT_SpawnAggroTrigger,
    OG_OT_SpawnCamAlign,
    OG_OT_SpawnCamPivot,
    OG_OT_SpawnCamLookAt,
    OG_OT_AddLauncherDest,
    OG_OT_AddWaterVolume,
    OG_OT_SpawnPlatform,
    OG_OT_PickNavMesh,
    OG_OT_SpawnCustomType,
)
