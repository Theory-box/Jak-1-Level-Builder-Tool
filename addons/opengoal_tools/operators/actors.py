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

# Search-popup enum items must stay referenced while the popup is open.
_SEARCH_ITEMS: list = []


def _link_target_items(self, ctx):
    """Every actor in the scene but the source, for the link search popup:
    types the slot accepts first, others marked "(unexpected type)"."""
    scene = ctx.scene if ctx else bpy.context.scene
    src = scene.objects.get(self.source_name)
    src_et = self.source_name.split("_", 2)[1] if self.source_name.count("_") >= 2 else ""
    acc = _db.link_slot(src_et, self.lump_key, self.slot_index).get("accepts")
    from ..data import _actor_multi_links
    have = ({e.target_name for e in _actor_multi_links(src, self.lump_key, self.slot_index)}
            if src and self.append else set())
    # nav-mesh-actor / path-actor: actors that have what the link borrows first
    has, what = {"nav-mesh-actor": (lambda o: bool(o.get("og_navmesh_link")), "navmesh"),
                 "path-actor": (lambda o: len(getattr(o, "og_waypoint_sources", ())) > 0, "path"),
                 }.get(self.lump_key, (None, ""))
    rows = []
    for o in scene.objects:
        if o is src or o.type != "EMPTY" or not o.name.startswith("ACTOR_") \
                or "_wp_" in o.name or "_wpb_" in o.name or o.name.count("_") < 2:
            continue
        ok = _db.link_accepts(acc, o.name.split("_", 2)[1])
        got = has(o) if has else None
        rows.append((got is False, not ok, _natural_key(o.name), o.name, ok, got))
    rows.sort()

    def _label(n, ok, got):
        s = n + ("" if ok else "  (unexpected type)")
        if got is not None:
            s += f"  (has a {what} connected)" if got else f"  (no {what} connected)"
        return s + ("  (linked)" if n in have else "")
    items = [(n, _label(n, ok, got), f"Link {n}", "LINKED" if ok and got is not False else "ERROR", i)
             for i, (_g, _bad, _k, n, ok, got) in enumerate(rows)]
    if not items:
        items = [("__none__", "(no other actors)", "", "ERROR", 0)]
    _SEARCH_ITEMS[:] = items
    return _SEARCH_ITEMS


class OG_OT_LinkActorSearch(Operator):
    """Search an actor by name and link it to this slot"""
    bl_idname   = "og.link_actor_search"
    bl_label    = "Search Actor"
    bl_options  = {"REGISTER", "UNDO"}
    bl_property = "target"

    source_name:  bpy.props.StringProperty()
    lump_key:     bpy.props.StringProperty()
    slot_index:   bpy.props.IntProperty(default=0)
    append:       bpy.props.BoolProperty(default=False)
    target:       bpy.props.EnumProperty(name="Actor", items=_link_target_items)

    def invoke(self, ctx, event):
        ctx.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, ctx):
        if self.target in ("", "__none__"):
            return {"CANCELLED"}
        return bpy.ops.og.set_actor_link(source_name=self.source_name, lump_key=self.lump_key,
                                         slot_index=self.slot_index, target_name=self.target,
                                         append=self.append)


# ─── Battlecontroller: intro camera picks + citadel camera position ─────────
_BC_ITEMS: list = []   # search-popup items must stay referenced


def _bc_camera_items(self, ctx):
    from ..export.battlecontroller import camera_anims
    items = [("custom", "Custom…", "Type a camera art group name")]
    items += [(ag, f"{ag}  ({len(an)} animations)", ag) for ag, an in sorted(camera_anims().items())]
    _BC_ITEMS[:] = [(a, b, c, i) for i, (a, b, c) in enumerate(items)]
    return _BC_ITEMS


def _bc_anim_items(self, ctx):
    from ..export.battlecontroller import camera_anims
    o = ctx.active_object if ctx else None
    ag = str(o.get("og_bc_cam", "") or "") if o else ""
    items = [("custom", "Custom…", "Type an animation name")]
    items += [(a, a, f"{ag}-{a}") for a in camera_anims().get(ag, [])]
    _BC_ITEMS[:] = [(a, b, c, i) for i, (a, b, c) in enumerate(items)]
    return _BC_ITEMS


class OG_OT_BCPickCamera(Operator):
    """Pick the camera art group the intro plays (search by name), or Custom to type one"""
    bl_idname   = "og.bc_pick_camera"
    bl_label    = "Pick Camera"
    bl_options  = {"REGISTER", "UNDO"}
    bl_property = "pick"
    pick: bpy.props.EnumProperty(name="Camera", items=_bc_camera_items)

    def invoke(self, ctx, event):
        ctx.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, ctx):
        from ..export.battlecontroller import camera_anims
        o = ctx.active_object
        if o is None:
            return {"CANCELLED"}
        o["og_bc_cam"] = self.pick
        anims = camera_anims().get(self.pick, [])
        if o.get("og_bc_anim", "") not in anims + ["custom"]:
            o["og_bc_anim"] = anims[-1] if anims else "custom"
        return {"FINISHED"}


class OG_OT_BCPickAnim(Operator):
    """Pick the camera animation (search by name), or Custom to type one"""
    bl_idname   = "og.bc_pick_anim"
    bl_label    = "Pick Camera Animation"
    bl_options  = {"REGISTER", "UNDO"}
    bl_property = "pick"
    pick: bpy.props.EnumProperty(name="Animation", items=_bc_anim_items)

    def invoke(self, ctx, event):
        ctx.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, ctx):
        o = ctx.active_object
        if o is None:
            return {"CANCELLED"}
        o["og_bc_anim"] = self.pick
        return {"FINISHED"}


class OG_OT_BCCamposAdd(Operator):
    """Spawn the camera-position empty the citadel camera plays from (at the
    3D cursor, or at the controller with At Actor Position on)"""
    bl_idname  = "og.bc_campos_add"
    bl_label   = "Add Camera Position"
    bl_options = {"REGISTER", "UNDO"}
    actor_name: bpy.props.StringProperty()

    def execute(self, ctx):
        actor = ctx.scene.objects.get(self.actor_name)
        if actor is None:
            return {"CANCELLED"}
        from ..collections import _link_object_to_sub_collection, _COL_PATH_WAYPOINTS
        base = "CAMPOS_" + actor.name[len("ACTOR_"):]
        name, n = base, 1
        while bpy.data.objects.get(name):
            name = f"{base}_{n}"; n += 1
        e = bpy.data.objects.new(name, None)
        e.empty_display_type = "CONE"; e.empty_display_size = 1.0
        e.location = actor.matrix_world.translation.copy() if ctx.scene.og_props.waypoint_spawn_at_actor \
            else ctx.scene.cursor.location.copy()
        ctx.scene.collection.objects.link(e)
        _link_object_to_sub_collection(ctx.scene, e, *_COL_PATH_WAYPOINTS)
        actor["og_bc_campos"] = e.name
        return {"FINISHED"}


class OG_OT_BCCamposLink(Operator):
    """Use this empty as the citadel camera position"""
    bl_idname  = "og.bc_campos_link"
    bl_label   = "Link Camera Position"
    bl_options = {"REGISTER", "UNDO"}
    actor_name:  bpy.props.StringProperty()
    target_name: bpy.props.StringProperty(options={"SKIP_SAVE"})

    def execute(self, ctx):
        actor = ctx.scene.objects.get(self.actor_name)
        if actor is None or self.target_name not in ctx.scene.objects:
            return {"CANCELLED"}
        actor["og_bc_campos"] = self.target_name
        return {"FINISHED"}


def _bc_lurker_items(self, ctx):
    from .. import db as _d
    o = ctx.active_object if ctx else None
    have = {e.etype for e in getattr(o, "og_bc_lurkers", [])} if o else set()
    items = [(et, (_d.find_actor(et) or {}).get("label", et) + ("  (added)" if et in have else ""), et)
             for et in sorted(_d.battlecontroller_lurkers())]
    _BC_ITEMS[:] = [(a, b, c, i) for i, (a, b, c) in enumerate(items)] or [("__none__", "(no jumping enemies)", "", 0)]
    return _BC_ITEMS


class OG_OT_BCLurkerAdd(Operator):
    """Add a lurker type to this battlecontroller (enemies that can jump, max 4)"""
    bl_idname   = "og.bc_lurker_add"
    bl_label    = "Add Lurker"
    bl_options  = {"REGISTER", "UNDO"}
    bl_property = "pick"
    pick: bpy.props.EnumProperty(name="Lurker", items=_bc_lurker_items)

    def invoke(self, ctx, event):
        ctx.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, ctx):
        o = ctx.active_object
        if o is None or self.pick == "__none__":
            return {"CANCELLED"}
        if len(o.og_bc_lurkers) >= 4:
            self.report({"WARNING"}, "A battlecontroller uses at most 4 lurker types"); return {"CANCELLED"}
        e = o.og_bc_lurkers.add()
        e.etype = self.pick
        e.percent = 1.0 if len(o.og_bc_lurkers) == 1 else 0.0
        return {"FINISHED"}


class OG_OT_BCLurkerRemove(Operator):
    """Remove this lurker type"""
    bl_idname  = "og.bc_lurker_remove"
    bl_label   = "Remove Lurker"
    bl_options = {"REGISTER", "UNDO"}
    index: bpy.props.IntProperty()

    def execute(self, ctx):
        o = ctx.active_object
        if o is None or not (0 <= self.index < len(o.og_bc_lurkers)):
            return {"CANCELLED"}
        o.og_bc_lurkers.remove(self.index)
        return {"FINISHED"}


class OG_OT_BCLurkerEven(Operator):
    """Split the spawn chance evenly between the lurkers (adds up to 1.0)"""
    bl_idname  = "og.bc_lurker_even"
    bl_label   = "Split Evenly"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, ctx):
        o = ctx.active_object
        ls = list(getattr(o, "og_bc_lurkers", []))[:4] if o else []
        for e in ls:
            e.percent = round(1.0 / len(ls), 4)
        if ls:   # absorb rounding in the last one
            ls[-1].percent = round(1.0 - sum(e.percent for e in ls[:-1]), 4)
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
    OG_OT_LinkActorSearch,
    OG_OT_BCPickCamera,
    OG_OT_BCPickAnim,
    OG_OT_BCCamposAdd,
    OG_OT_BCCamposLink,
    OG_OT_BCLurkerAdd,
    OG_OT_BCLurkerRemove,
    OG_OT_BCLurkerEven,
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
    OG_OT_TogglePlatformWrap,
    OG_OT_SetPlatformDefaults,
    OG_OT_SetVersionField,
)
