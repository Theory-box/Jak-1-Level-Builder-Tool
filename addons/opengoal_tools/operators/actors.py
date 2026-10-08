# ───────────────────────────────────────────────────────────────────────
# operators/actors.py — OpenGOAL Level Tools
#
# Per-actor property setters and toggles, plus generic og.set_actor_enum_field and og.toggle_actor_bool_field.
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
from .. import db as _db
import re as _re


class OG_OT_SetActorLink(Operator):
    """Set an entity link slot on an ACTOR_ empty.

    Called from the Actor Links panel when the user clicks 'Link →'.
    source_name = the ACTOR_ empty being edited.
    lump_key / slot_index = which slot to fill.
    target_name = the ACTOR_ empty to link to.
    """
    bl_idname   = "og.set_actor_link"
    bl_label    = "Set Actor Link"
    bl_options  = {"REGISTER", "UNDO"}

    source_name:  bpy.props.StringProperty()
    lump_key:     bpy.props.StringProperty()
    slot_index:   bpy.props.IntProperty(default=0)
    target_name:  bpy.props.StringProperty()
    append:       bpy.props.BoolProperty(default=False,
        description="Add to an allow-multiple slot instead of replacing it")

    def execute(self, ctx):
        from ..data import _actor_add_multi_link
        obj = ctx.scene.objects.get(self.source_name)
        if not obj:
            self.report({"ERROR"}, f"Source '{self.source_name}' not found")
            return {"CANCELLED"}
        target = ctx.scene.objects.get(self.target_name)
        if not target:
            self.report({"ERROR"}, f"Target '{self.target_name}' not found")
            return {"CANCELLED"}
        if self.append:
            if not _actor_add_multi_link(obj, self.lump_key, self.slot_index, self.target_name):
                self.report({"INFO"}, f"{self.target_name} is already linked")
                return {"CANCELLED"}
        else:
            _actor_set_link(obj, self.lump_key, self.slot_index, self.target_name)
        # Unexpected types are allowed, with a warning (they may not work in game).
        src_et = obj.name.split("_", 2)[1] if obj.name.count("_") >= 2 else ""
        tgt_et = target.name.split("_", 2)[1] if target.name.count("_") >= 2 else ""
        slot = _db.link_slot(src_et, self.lump_key, self.slot_index)
        if slot and not _db.link_accepts(slot.get("accepts"), tgt_et):
            self.report({"WARNING"}, f"Linked {self.target_name}, but '{self.lump_key}' expects "
                                     f"{', '.join(slot.get('accepts') or [])} — it may not work in game")
        else:
            self.report({"INFO"}, f"Linked {self.source_name} [{self.lump_key}] → {self.target_name}")
        return {"FINISHED"}

def _natural_key(name):
    """Outliner-style order: 'plat_2' before 'plat_10'."""
    import re as _re
    return [int(t) if t.isdigit() else t.lower() for t in _re.split(r"(\d+)", name)]


def _selected_actor_empties(ctx, exclude=None):
    return sorted((o for o in ctx.selected_objects
                   if o is not exclude and o.type == "EMPTY" and o.name.startswith("ACTOR_")
                   and "_wp_" not in o.name and "_wpb_" not in o.name),
                  key=lambda o: _natural_key(o.name))


class OG_OT_LinkAddSelected(Operator):
    """Add every shift-selected actor to an allow-multiple link slot, in
    outliner (name) order. Already-linked ones are skipped"""
    bl_idname  = "og.link_add_selected"
    bl_label   = "Add All Selected"
    bl_options = {"REGISTER", "UNDO"}

    source_name: bpy.props.StringProperty()
    lump_key:    bpy.props.StringProperty()
    slot_index:  bpy.props.IntProperty(default=0)

    def execute(self, ctx):
        from ..data import _actor_add_multi_link
        obj = ctx.scene.objects.get(self.source_name)
        if not obj:
            return {"CANCELLED"}
        added = [t.name for t in _selected_actor_empties(ctx, exclude=obj)
                 if _actor_add_multi_link(obj, self.lump_key, self.slot_index, t.name)]
        self.report({"INFO"}, f"Added {len(added)} actor(s) to {self.lump_key}")
        return {"FINISHED"} if added else {"CANCELLED"}


class OG_OT_LinkChainSelected(Operator):
    """Chain the selected actors (this one included) in outliner (name)
    order: each one's next-actor -> the following one, prev-actor -> the
    one before. Only sets the slots an actor type actually has"""
    bl_idname  = "og.link_chain_selected"
    bl_label   = "Chain Selected (prev / next)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        chain = _selected_actor_empties(ctx)
        if len(chain) < 2:
            self.report({"WARNING"}, "Select 2 or more actors to chain")
            return {"CANCELLED"}
        n = 0
        for i, o in enumerate(chain):
            et = o.name.split("_", 2)[1]
            keys = {(s["lump_key"], s.get("slot", 0)) for s in _db.link_slots(et)}
            if i + 1 < len(chain) and ("next-actor", 0) in keys:
                _actor_set_link(o, "next-actor", 0, chain[i + 1].name); n += 1
            if i > 0 and ("prev-actor", 0) in keys:
                _actor_set_link(o, "prev-actor", 0, chain[i - 1].name); n += 1
        self.report({"INFO"}, f"Chained {len(chain)} actors ({n} links): "
                              f"{chain[0].name} → … → {chain[-1].name}")
        return {"FINISHED"}


class OG_OT_ToggleDoorFlag(Operator):
    """Toggle an eco-door behaviour flag."""
    bl_idname  = "og.toggle_door_flag"
    bl_label   = "Toggle Door Flag"
    bl_options = {"REGISTER", "UNDO"}

    flag: bpy.props.StringProperty()

    def execute(self, ctx):
        o = ctx.active_object
        if not o: return {"CANCELLED"}
        prop = f"og_door_{self.flag}"
        o[prop] = 0 if bool(o.get(prop, False)) else 1
        return {"FINISHED"}

class OG_OT_SetDoorCP(Operator):
    """Set the continue-name for a launcherdoor from a scene checkpoint."""
    bl_idname  = "og.set_door_cp"
    bl_label   = "Set Door Continue Point"
    bl_options = {"REGISTER", "UNDO"}

    actor_name: bpy.props.StringProperty()
    cp_name:    bpy.props.StringProperty()

    def execute(self, ctx):
        o = bpy.data.objects.get(self.actor_name)
        if o:
            o["og_continue_name"] = self.cp_name
        return {"FINISHED"}

class OG_OT_ClearDoorCP(Operator):
    """Clear the continue-name from a launcherdoor."""
    bl_idname  = "og.clear_door_cp"
    bl_label   = "Clear Door Continue Point"
    bl_options = {"REGISTER", "UNDO"}

    actor_name: bpy.props.StringProperty()

    def execute(self, ctx):
        o = bpy.data.objects.get(self.actor_name)
        if o and "og_continue_name" in o:
            del o["og_continue_name"]
        return {"FINISHED"}

class OG_OT_SetWaterAttack(Operator):
    """Set the damage type for this water volume."""
    bl_idname  = "og.set_water_attack"
    bl_label   = "Set Water Attack"
    bl_options = {"REGISTER", "UNDO"}
    mesh_name:  bpy.props.StringProperty()
    attack_val: bpy.props.StringProperty()
    def execute(self, ctx):
        o = bpy.data.objects.get(self.mesh_name)
        if o: o["og_water_attack"] = self.attack_val
        return {"FINISHED"}

class OG_OT_SetCrateType(Operator):
    """Set the crate type (look/defense) on the selected crate actor."""
    bl_idname  = "og.set_crate_type"
    bl_label   = "Set Crate Type"
    bl_options = {"REGISTER", "UNDO"}

    crate_type: bpy.props.StringProperty()

    def execute(self, ctx):
        o = ctx.active_object
        if not o:
            return {"CANCELLED"}
        pickup = o.get("og_crate_pickup", "money")
        # Engine auto-upgrades wood→iron when a scout fly is inside.
        # Mirror that logic: if user picks wood and there's a buzzer, force iron.
        if self.crate_type == "wood" and pickup == "buzzer":
            o["og_crate_type"] = "iron"
            self.report({"WARNING"}, "Scout Fly requires Iron box — crate type set to Iron")
        else:
            o["og_crate_type"] = self.crate_type
        return {"FINISHED"}

class OG_OT_SetCratePickup(Operator):
    """Set what drops from this crate when broken."""
    bl_idname  = "og.set_crate_pickup"
    bl_label   = "Set Crate Pickup"
    bl_options = {"REGISTER", "UNDO"}

    pickup_id: bpy.props.StringProperty()

    def execute(self, ctx):
        o = ctx.active_object
        if not o:
            return {"CANCELLED"}
        o["og_crate_pickup"] = self.pickup_id
        # Scout fly always amount 1; reset amount to 1 when switching to buzzer
        if self.pickup_id == "buzzer":
            o["og_crate_pickup_amount"] = 1
            # Enforce iron/steel — wood can't hold a scout fly
            ct = o.get("og_crate_type", "steel")
            if ct == "wood":
                o["og_crate_type"] = "iron"
                self.report({"WARNING"}, "Scout Fly requires Iron box — crate type set to Iron")
        return {"FINISHED"}

class OG_OT_SetCrateAmount(Operator):
    """Set the pickup amount dropped by this crate."""
    bl_idname  = "og.set_crate_amount"
    bl_label   = "Set Crate Amount"
    bl_options = {"REGISTER", "UNDO"}

    delta: bpy.props.IntProperty(default=1)

    def execute(self, ctx):
        o = ctx.active_object
        if not o:
            return {"CANCELLED"}
        # Scout fly is always 1 — don't allow changes
        if o.get("og_crate_pickup", "money") == "buzzer":
            return {"CANCELLED"}
        current = int(o.get("og_crate_pickup_amount", 1))
        o["og_crate_pickup_amount"] = max(1, min(5, current + self.delta))
        return {"FINISHED"}

class OG_OT_ToggleCrystalUnderwater(Operator):
    """Toggle dark crystal underwater variant (mode=1 lump)."""
    bl_idname  = "og.toggle_crystal_underwater"
    bl_label   = "Toggle Crystal Underwater"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        o = ctx.active_object
        if o:
            o["og_crystal_underwater"] = 0 if bool(o.get("og_crystal_underwater", False)) else 1
        return {"FINISHED"}

class OG_OT_ToggleCellSkipJump(Operator):
    """Toggle skip-jump-anim fact-option on fuel-cell (options lump bit 2)."""
    bl_idname  = "og.toggle_cell_skip_jump"
    bl_label   = "Toggle Cell Skip Jump"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        o = ctx.active_object
        if o:
            o["og_cell_skip_jump"] = 0 if bool(o.get("og_cell_skip_jump", False)) else 1
        return {"FINISHED"}

class OG_OT_SetBridgeVariant(Operator):
    """Set the art-name (bridge variant) on a ropebridge actor."""
    bl_idname  = "og.set_bridge_variant"
    bl_label   = "Set Bridge Variant"
    bl_options = {"REGISTER", "UNDO"}

    variant: bpy.props.StringProperty()

    def execute(self, ctx):
        o = ctx.active_object
        if o:
            o["og_bridge_variant"] = self.variant
        return {"FINISHED"}

class OG_OT_ToggleTurbineParticles(Operator):
    """Toggle particle-select on windturbine actor."""
    bl_idname  = "og.toggle_turbine_particles"
    bl_label   = "Toggle Turbine Particles"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        o = ctx.active_object
        if o:
            o["og_turbine_particles"] = 0 if bool(o.get("og_turbine_particles", False)) else 1
        return {"FINISHED"}

class OG_OT_SetElevatorMode(Operator):
    """Set the mode lump on a cave elevator."""
    bl_idname  = "og.set_elevator_mode"
    bl_label   = "Set Elevator Mode"
    bl_options = {"REGISTER", "UNDO"}

    mode_val: bpy.props.IntProperty()

    def execute(self, ctx):
        o = ctx.active_object
        if o:
            o["og_elevator_mode"] = self.mode_val
        return {"FINISHED"}

class OG_OT_SetBoneBridgeAnim(Operator):
    """Set the animation-select lump on a mis-bone-bridge."""
    bl_idname  = "og.set_bone_bridge_anim"
    bl_label   = "Set Bone Bridge Anim"
    bl_options = {"REGISTER", "UNDO"}

    anim_val: bpy.props.IntProperty()

    def execute(self, ctx):
        o = ctx.active_object
        if o:
            o["og_bone_bridge_anim"] = self.anim_val
        return {"FINISHED"}

class OG_OT_SetAltTask(Operator):
    """Set the alt-task lump on oracle / pontoon actors."""
    bl_idname  = "og.set_alt_task"
    bl_label   = "Set Alt Task"
    bl_options = {"REGISTER", "UNDO"}

    task_name: bpy.props.StringProperty()

    def execute(self, ctx):
        o = ctx.active_object
        if o:
            o["og_alt_task"] = self.task_name
        return {"FINISHED"}

class OG_OT_TogglePlatformWrap(Operator):
    """Toggle wrap-phase (one-way loop vs ping-pong) on the selected platform."""
    bl_idname = "og.toggle_platform_wrap"
    bl_label  = "Toggle Wrap Phase"

    def execute(self, ctx):
        o = ctx.active_object
        if not o:
            return {"CANCELLED"}
        o["og_sync_wrap"] = 0 if bool(o.get("og_sync_wrap", 0)) else 1
        return {"FINISHED"}

class OG_OT_SetPlatformDefaults(Operator):
    """Reset sync values on the selected platform actor to defaults."""
    bl_idname = "og.set_platform_defaults"
    bl_label  = "Reset Sync Defaults"

    def execute(self, ctx):
        o = ctx.active_object
        if not o:
            return {"CANCELLED"}
        from ..utils import sync_defaults
        etype = o.name.split("_", 2)[1] if o.name.count("_") >= 2 else ""
        for k, v in sync_defaults(etype).items():
            o[k] = int(v) if isinstance(v, bool) else v
        return {"FINISHED"}

class OG_OT_SetVersionField(bpy.types.Operator):
    bl_idname   = "og.set_version_field"
    bl_label    = "Select"
    bl_description = "Set the active selection for this field"

    field: StringProperty()   # "og_active_version" or "og_active_data"
    value: StringProperty()

    def execute(self, ctx):
        prefs = ctx.preferences.addons.get("opengoal_tools")
        if prefs and self.field in ("og_active_version", "og_active_data"):
            setattr(prefs.preferences, self.field, self.value)
        return {"FINISHED"}


# ─── Classes to register ───────────────────────────────────────────────────
CLASSES = (
    OG_OT_SetActorLink,
    OG_OT_LinkAddSelected,
    OG_OT_LinkChainSelected,
    OG_OT_ToggleDoorFlag,
    OG_OT_SetDoorCP,
    OG_OT_ClearDoorCP,
    OG_OT_SetWaterAttack,
    OG_OT_SetCrateType,
    OG_OT_SetCratePickup,
    OG_OT_SetCrateAmount,
    OG_OT_ToggleCrystalUnderwater,
    OG_OT_ToggleCellSkipJump,
    OG_OT_SetBridgeVariant,
    OG_OT_ToggleTurbineParticles,
    OG_OT_SetElevatorMode,
    OG_OT_SetBoneBridgeAnim,
    OG_OT_SetAltTask,
    OG_OT_TogglePlatformWrap,
    OG_OT_SetPlatformDefaults,
    OG_OT_SetVersionField,
)
