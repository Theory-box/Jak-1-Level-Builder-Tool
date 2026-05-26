# ───────────────────────────────────────────────────────────────────────
# operators/links.py — OpenGOAL Level Tools
#
# Actor/volume/navmesh linking: set/clear links, mark navmesh groups, waypoints, clean orphaned links.
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


class OG_OT_MarkNavMesh(Operator):
    bl_idname = "og.mark_navmesh"
    bl_label  = "Mark as NavMesh"
    bl_description = "Tag selected mesh objects as navmesh geometry and move into NavMeshes sub-collection"
    def execute(self, ctx):
        count = 0
        for o in ctx.selected_objects:
            if o.type == "MESH":
                o["og_navmesh"] = True
                if not o.name.startswith("NAVMESH_"):
                    o.name = "NAVMESH_" + o.name
                _link_object_to_sub_collection(ctx.scene, o, *_COL_PATH_NAVMESHES)
                count += 1
        self.report({"INFO"}, f"Tagged {count} object(s) as navmesh geometry")
        return {"FINISHED"}

class OG_OT_UnmarkNavMesh(Operator):
    bl_idname = "og.unmark_navmesh"
    bl_label  = "Unmark NavMesh"
    bl_description = "Remove navmesh tag and move out of NavMeshes sub-collection into Geometry/Solid"
    def execute(self, ctx):
        count = 0
        for o in ctx.selected_objects:
            if "og_navmesh" in o:
                del o["og_navmesh"]
                # Strip NAVMESH_ prefix if present
                if o.name.startswith("NAVMESH_"):
                    o.name = o.name[len("NAVMESH_"):]
                # Move to Geometry/Solid
                _link_object_to_sub_collection(ctx.scene, o, *_COL_PATH_GEO_SOLID)
                count += 1
        self.report({"INFO"}, f"Untagged {count} object(s)")
        return {"FINISHED"}

class OG_OT_LinkNavMesh(Operator):
    """Link selected enemy actor(s) to the selected navmesh mesh.
    Select any combination of enemy empties + one mesh — order doesn't matter."""
    bl_idname = "og.link_navmesh"
    bl_label  = "Link to NavMesh"
    bl_description = "Select enemy actor(s) + navmesh mesh (any order), then click"

    def execute(self, ctx):
        selected = ctx.selected_objects

        # Find the mesh and the enemy empties from the full selection — order irrelevant
        meshes  = [o for o in selected if o.type == "MESH"]
        enemies = [o for o in selected if o.type == "EMPTY"
                   and o.name.startswith("ACTOR_") and "_wp_" not in o.name
                   and "_wpb_" not in o.name]

        if not meshes:
            self.report({"ERROR"}, "No mesh in selection — select a navmesh quad too")
            return {"CANCELLED"}
        if len(meshes) > 1:
            self.report({"ERROR"}, "Multiple meshes selected — select only one navmesh quad")
            return {"CANCELLED"}
        if not enemies:
            self.report({"ERROR"}, "No enemy actor in selection — select the enemy empty too")
            return {"CANCELLED"}

        nm = meshes[0]

        # Tag mesh as navmesh, prefix name if needed, route into NavMeshes sub-collection
        nm["og_navmesh"] = True
        if not nm.name.startswith("NAVMESH_"):
            nm.name = "NAVMESH_" + nm.name
        _link_object_to_sub_collection(ctx.scene, nm, *_COL_PATH_NAVMESHES)

        for enemy in enemies:
            enemy["og_navmesh_link"] = nm.name

        self.report({"INFO"}, f"Linked {len(enemies)} actor(s) to {nm.name}")
        return {"FINISHED"}

class OG_OT_UnlinkNavMesh(Operator):
    """Remove navmesh link from selected enemy actors.
    Also renames the mesh (strips NAVMESH_ prefix) and moves it to Geometry/Solid."""
    bl_idname = "og.unlink_navmesh"
    bl_label  = "Unlink NavMesh"
    bl_description = "Remove navmesh link from selected enemy actor(s)"

    def execute(self, ctx):
        count = 0
        for o in ctx.selected_objects:
            if "og_navmesh_link" in o:
                nm_name = o["og_navmesh_link"]
                del o["og_navmesh_link"]
                # Clean up the mesh itself if it still exists
                nm_obj = bpy.data.objects.get(nm_name)
                if nm_obj and nm_obj.type == "MESH":
                    # Remove navmesh tag
                    if "og_navmesh" in nm_obj:
                        del nm_obj["og_navmesh"]
                    # Strip NAVMESH_ prefix
                    if nm_obj.name.startswith("NAVMESH_"):
                        nm_obj.name = nm_obj.name[len("NAVMESH_"):]
                    # Move back to Geometry/Solid
                    _link_object_to_sub_collection(ctx.scene, nm_obj, *_COL_PATH_GEO_SOLID)
                count += 1
        self.report({"INFO"}, f"Unlinked {count} actor(s)")
        return {"FINISHED"}

class OG_OT_AddWaypoint(Operator):
    """Add a waypoint empty linked to the selected enemy. Spawns at the 3D cursor, or at the actor position if Spawn at Position is enabled."""
    bl_idname = "og.add_waypoint"
    bl_label  = "Add Waypoint"

    enemy_name: bpy.props.StringProperty()
    pathb_mode: bpy.props.BoolProperty(default=False,
        description="Add to secondary path (pathb) — swamp-bat only")

    def execute(self, ctx):
        if not self.enemy_name:
            self.report({"ERROR"}, "No enemy name provided")
            return {"CANCELLED"}

        # Find next available index for primary (_wp_) or secondary (_wpb_) path
        # Scope to level objects so multi-level .blends don't cross-count
        suffix = "_wpb_" if self.pathb_mode else "_wp_"
        prefix = self.enemy_name + suffix
        existing = {o.name for o in _level_objects(ctx.scene) if o.name.startswith(prefix)}
        idx = 0
        while f"{prefix}{idx:02d}" in existing:
            idx += 1

        wp_name = f"{prefix}{idx:02d}"

        # Create empty — at actor position or 3D cursor depending on user preference
        actor_obj = bpy.data.objects.get(self.enemy_name)
        use_actor_pos = ctx.scene.og_props.waypoint_spawn_at_actor and actor_obj is not None
        spawn_loc = actor_obj.location.copy() if use_actor_pos else ctx.scene.cursor.location.copy()

        empty = bpy.data.objects.new(wp_name, None)
        empty.empty_display_type = "PLAIN_AXES"
        empty.empty_display_size = 0.5
        empty.location = spawn_loc

        # Custom property to link back to enemy
        empty["og_waypoint_for"] = self.enemy_name

        # Link into scene first (required before collection routing)
        ctx.scene.collection.objects.link(empty)

        # Route into Waypoints sub-collection under the active level
        _link_object_to_sub_collection(ctx.scene, empty, *_COL_PATH_WAYPOINTS)

        # ---- Waypoint ghost preview ----------------------------------------
        # Parse the entity type from the actor name (ACTOR_<etype>_<uid>)
        # and attach a white, 50%-transparent ghost of its mesh so the user
        # can see where the entity will stand at each waypoint.
        _prefs = bpy.context.preferences.addons.get("opengoal_tools")
        if _prefs and _prefs.preferences.preview_models:
            parts = self.enemy_name.split("_")  # ["ACTOR", "<etype>", "<uid>"]
            etype = parts[1] if len(parts) >= 3 else ""
            if etype:
                try:
                    _mp.attach_waypoint_preview(ctx, etype, empty)
                except Exception as e:
                    log(f"waypoint model_preview: {e}")

        # Do NOT change active object — user needs to keep the actor selected
        # so they can quickly add more waypoints without re-selecting.
        loc_desc = "actor position" if use_actor_pos else "cursor"
        self.report({"INFO"}, f"Added {wp_name} at {loc_desc}")

        # New: also append this empty to the actor's reorderable waypoint
        # source list, so the new UI stays in sync with manual spawns.
        # Skip for Path B (swamp-bat) — it stays on the legacy name-grep
        # system for now.
        if not self.pathb_mode and actor_obj is not None:
            try:
                src = actor_obj.og_waypoint_sources.add()
                src.obj = empty
                actor_obj.og_waypoint_sources_index = len(actor_obj.og_waypoint_sources) - 1
            except AttributeError:
                # Actor doesn't have the new properties yet — possible if the
                # addon was registered without our properties registered, or
                # during a version mismatch. Fail silently; the legacy export
                # path will still find this empty by name.
                pass

        return {"FINISHED"}

class OG_OT_DeleteWaypoint(Operator):
    """Remove a waypoint empty."""
    bl_idname = "og.delete_waypoint"
    bl_label  = "Delete Waypoint"

    wp_name: bpy.props.StringProperty()

    def execute(self, ctx):
        ob = bpy.data.objects.get(self.wp_name)
        if ob:
            bpy.data.objects.remove(ob, do_unlink=True)
            self.report({"INFO"}, f"Deleted {self.wp_name}")
        return {"FINISHED"}


# ───────────────────────────────────────────────────────────────────────
# Waypoint-source list operators (the new reorderable list)
# These operate on the active ACTOR_ empty's og_waypoint_sources collection.
# ───────────────────────────────────────────────────────────────────────

def _get_actor_for_waypoint_ops(ctx):
    """Return the ACTOR_ empty whose waypoint list we're editing, or None.
    Used by the source-list operators below — they all need the same
    actor-object lookup."""
    sel = ctx.active_object
    if sel is None:
        return None
    # Must be an ACTOR_ empty (not a waypoint itself)
    if not sel.name.startswith("ACTOR_") or "_wp_" in sel.name or "_wpb_" in sel.name:
        return None
    return sel


class OG_OT_WaypointSourceRemove(Operator):
    """Remove the highlighted entry from the actor's waypoint source list.
    If the entry points to an addon-created _wp_NN empty, the empty is also
    deleted from the scene (it has no other use). Curves are never deleted
    — they may be reused or are user-authored data; only the list entry
    is removed."""
    bl_idname  = "og.waypoint_source_remove"
    bl_label   = "Remove Waypoint Source"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, ctx):
        actor = _get_actor_for_waypoint_ops(ctx)
        if actor is None:
            return False
        return 0 <= actor.og_waypoint_sources_index < len(actor.og_waypoint_sources)

    def execute(self, ctx):
        actor = _get_actor_for_waypoint_ops(ctx)
        idx = actor.og_waypoint_sources_index
        if not (0 <= idx < len(actor.og_waypoint_sources)):
            return {"CANCELLED"}
        src_obj = actor.og_waypoint_sources[idx].obj
        actor.og_waypoint_sources.remove(idx)
        actor.og_waypoint_sources_index = max(0, min(idx, len(actor.og_waypoint_sources) - 1))

        # Delete the underlying object IF it's an addon-created waypoint
        # empty (matches the ACTOR_*_wp_NN convention). Curves and other
        # user-linked objects are left alone — the user can delete them
        # via the normal viewport workflow if they want to.
        if (src_obj is not None
                and src_obj.type == "EMPTY"
                and src_obj.name.startswith("ACTOR_")
                and "_wp_" in src_obj.name):
            try:
                bpy.data.objects.remove(src_obj, do_unlink=True)
            except ReferenceError:
                pass  # already gone

        return {"FINISHED"}


class OG_OT_WaypointSourceMove(Operator):
    """Reorder the active waypoint source up or down in the list. The list
    order is the export order — moving a curve earlier means its points are
    emitted earlier in the actor's path."""
    bl_idname  = "og.waypoint_source_move"
    bl_label   = "Move Waypoint Source"
    bl_options = {"REGISTER", "UNDO"}

    direction: bpy.props.EnumProperty(
        items=[("UP", "Up", ""), ("DOWN", "Down", "")],
    )

    @classmethod
    def poll(cls, ctx):
        actor = _get_actor_for_waypoint_ops(ctx)
        if actor is None:
            return False
        return len(actor.og_waypoint_sources) > 1

    def execute(self, ctx):
        actor = _get_actor_for_waypoint_ops(ctx)
        sources = actor.og_waypoint_sources
        idx = actor.og_waypoint_sources_index
        if not (0 <= idx < len(sources)):
            return {"CANCELLED"}
        if self.direction == "UP" and idx > 0:
            sources.move(idx, idx - 1)
            actor.og_waypoint_sources_index = idx - 1
        elif self.direction == "DOWN" and idx < len(sources) - 1:
            sources.move(idx, idx + 1)
            actor.og_waypoint_sources_index = idx + 1
        return {"FINISHED"}


class OG_OT_WaypointSourceFrame(Operator):
    """Frame the active waypoint source's object in the viewport without
    losing the actor selection. Mirror of the 🔍 button on each existing
    waypoint row in the old layout."""
    bl_idname  = "og.waypoint_source_frame"
    bl_label   = "Frame Waypoint Source"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, ctx):
        actor = _get_actor_for_waypoint_ops(ctx)
        if actor is None:
            return False
        idx = actor.og_waypoint_sources_index
        sources = actor.og_waypoint_sources
        return (0 <= idx < len(sources)
                and sources[idx].obj is not None
                and sources[idx].obj.name in ctx.scene.objects)

    def execute(self, ctx):
        actor = _get_actor_for_waypoint_ops(ctx)
        src_obj = actor.og_waypoint_sources[actor.og_waypoint_sources_index].obj
        # Save the actor as active so it gets re-selected after the frame op
        actor_name = actor.name
        # Select only the source object, frame it, then restore actor selection
        for o in ctx.selected_objects:
            o.select_set(False)
        src_obj.select_set(True)
        ctx.view_layer.objects.active = src_obj
        # Frame in viewport via the standard op
        for area in ctx.screen.areas:
            if area.type == "VIEW_3D":
                with ctx.temp_override(area=area, region=area.regions[-1]):
                    bpy.ops.view3d.view_selected(use_all_regions=False)
                break
        # Restore selection on the actor
        src_obj.select_set(False)
        actor_back = bpy.data.objects.get(actor_name)
        if actor_back is not None:
            actor_back.select_set(True)
            ctx.view_layer.objects.active = actor_back
        return {"FINISHED"}


def _curve_items_in_scene(self, ctx):
    """EnumProperty items callback: every CURVE object in the file.
    Used by OG_OT_WaypointSourceLinkCurve's picker popup."""
    items = [(o.name, o.name, "") for o in bpy.data.objects if o.type == "CURVE"]
    if not items:
        items = [("__none__", "(no curves in scene)", "Add a curve via Add > Curve > Bezier first")]
    return items


class OG_OT_WaypointSourceLinkCurve(Operator):
    """Pick an existing curve in the scene and append it to this actor's
    waypoint list. At export time, each spline control point becomes one
    waypoint in the actor's path, in spline order."""
    bl_idname      = "og.waypoint_source_link_curve"
    bl_label       = "Link Curve"
    bl_description = "Pick an existing curve. Each control point becomes a waypoint at export"
    bl_options     = {"REGISTER", "UNDO"}

    actor_name: bpy.props.StringProperty()
    curve_name: bpy.props.EnumProperty(
        name="Curve",
        description="Which curve to link",
        items=_curve_items_in_scene,
    )

    def invoke(self, ctx, event):
        if not self.actor_name:
            self.report({"ERROR"}, "No actor specified")
            return {"CANCELLED"}
        return ctx.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, ctx):
        col = self.layout.column()
        col.prop(self, "curve_name", text="Curve")

    def execute(self, ctx):
        actor = bpy.data.objects.get(self.actor_name)
        if actor is None:
            self.report({"ERROR"}, f"Actor '{self.actor_name}' not found")
            return {"CANCELLED"}
        if self.curve_name in ("", "__none__"):
            self.report({"ERROR"}, "No curve selected — add a curve to the scene first")
            return {"CANCELLED"}
        curve = bpy.data.objects.get(self.curve_name)
        if curve is None or curve.type != "CURVE":
            self.report({"ERROR"}, f"'{self.curve_name}' is not a curve")
            return {"CANCELLED"}
        # Append a row pointing to the curve, make it the active row.
        src = actor.og_waypoint_sources.add()
        src.obj = curve
        actor.og_waypoint_sources_index = len(actor.og_waypoint_sources) - 1
        self.report({"INFO"}, f"Linked curve '{curve.name}' to {actor.name}")
        return {"FINISHED"}


class OG_OT_WaypointSourceMigrate(Operator):
    """One-time migration for actors with legacy _wp_NN empties but no
    og_waypoint_sources collection. Walks the empties in name order and
    adds each to the collection, so the user can then reorder them or
    interleave curves."""
    bl_idname      = "og.waypoint_source_migrate"
    bl_label       = "Migrate Waypoints to List"
    bl_description = "Populate the reorderable list from this actor's existing _wp_NN empties"
    bl_options     = {"REGISTER", "UNDO"}

    actor_name: bpy.props.StringProperty()

    def execute(self, ctx):
        actor = bpy.data.objects.get(self.actor_name)
        if actor is None:
            self.report({"ERROR"}, f"Actor '{self.actor_name}' not found")
            return {"CANCELLED"}
        if len(actor.og_waypoint_sources) > 0:
            self.report({"WARNING"}, "Waypoint list already has entries — not migrating")
            return {"CANCELLED"}
        prefix = actor.name + "_wp_"
        wps = sorted(
            [o for o in _level_objects(ctx.scene)
             if o.name.startswith(prefix) and o.type == "EMPTY"],
            key=lambda o: o.name
        )
        if not wps:
            self.report({"WARNING"}, "No legacy waypoints found to migrate")
            return {"CANCELLED"}
        for wp in wps:
            src = actor.og_waypoint_sources.add()
            src.obj = wp
        actor.og_waypoint_sources_index = 0
        self.report({"INFO"}, f"Migrated {len(wps)} waypoint{'s' if len(wps) != 1 else ''} for {actor.name}")
        return {"FINISHED"}


class OG_OT_LinkVolume(Operator):
    """Append a link from a VOL_ mesh to a camera, checkpoint, or nav-enemy.
    Select the VOL_ mesh first, then shift-click the target, then click Link.
    A volume can hold multiple links — each fires its own action on enter."""
    bl_idname   = "og.link_volume"
    bl_label    = "Link Volume"
    bl_description = "Select VOL_ mesh first, then shift-click the target (camera/checkpoint/enemy), then click"

    def execute(self, ctx):
        selected = ctx.selected_objects
        vols    = [o for o in selected if o.type == "MESH" and o.name.startswith("VOL_")]
        targets = [o for o in selected if _is_linkable(o)]

        if not vols:
            self.report({"ERROR"}, "No VOL_ mesh in selection")
            return {"CANCELLED"}
        if len(vols) > 1:
            self.report({"ERROR"}, "Multiple volumes selected — select exactly one")
            return {"CANCELLED"}
        if not targets:
            self.report({"ERROR"}, "No linkable target (camera, checkpoint, or nav-enemy) in selection")
            return {"CANCELLED"}
        if len(targets) > 1:
            self.report({"ERROR"}, "Multiple targets selected — select exactly one")
            return {"CANCELLED"}

        vol    = vols[0]
        target = targets[0]
        links  = _vol_links(vol)

        # Block duplicate link to the same camera/checkpoint on this vol
        # (Scenario B from design — pointless duplicate). Aggro enemy targets
        # are also blocked from exact duplicates: each link entry must have
        # a unique target_name on a given vol.
        if _vol_has_link_to(vol, target.name):
            self.report({"WARNING"}, f"{vol.name} is already linked to {target.name}")
            return {"CANCELLED"}

        # For cameras/checkpoints, also block the cross-volume duplicate
        # (one camera/checkpoint should have one trigger volume system-wide).
        if not _is_aggro_target(target):
            existing = _vol_for_target(ctx.scene, target.name)
            if existing and existing != vol:
                self.report({"WARNING"},
                    f"{target.name} already has {existing.name} linked — unlink first")
                return {"CANCELLED"}

        entry = links.add()
        entry.target_name = target.name
        entry.behaviour   = "cue-chase"
        _rename_vol_for_links(vol)
        self.report({"INFO"}, f"Linked {vol.name} → {target.name}  ({len(links)} link{'s' if len(links)!=1 else ''})")
        return {"FINISHED"}

class OG_OT_UnlinkVolume(Operator):
    """Unlink a VOL_ mesh from its target. Works on selected VOL_ meshes."""
    bl_idname   = "og.unlink_volume"
    bl_label    = "Unlink Volume"
    bl_description = "Remove the link from the selected VOL_ mesh and restore its generic name"

    def execute(self, ctx):
        count = 0
        for o in ctx.selected_objects:
            if o.type == "MESH" and o.name.startswith("VOL_"):
                links = _vol_links(o)
                if len(links) > 0:
                    links.clear()
                    _rename_vol_for_links(o)
                    count += 1
        if count:
            self.report({"INFO"}, f"Unlinked all entries from {count} volume(s)")
        else:
            self.report({"WARNING"}, "No linked VOL_ meshes in selection")
        return {"FINISHED"}

class OG_OT_CleanOrphanedLinks(Operator):
    """Remove link entries from VOL_ meshes whose targets have been deleted."""
    bl_idname   = "og.clean_orphaned_links"
    bl_label    = "Clean Orphaned Links"
    bl_description = "Remove links from volumes whose target (camera/checkpoint/enemy) has been deleted"

    def execute(self, ctx):
        cleaned = _clean_orphaned_vol_links(ctx.scene)
        if cleaned:
            msg = ", ".join(f"{v}→{t}" for v, t in cleaned)
            self.report({"INFO"}, f"Cleaned {len(cleaned)} orphaned link(s): {msg}")
        else:
            self.report({"INFO"}, "No orphaned links found")
        return {"FINISHED"}

class OG_OT_RemoveVolLink(Operator):
    """Remove a single link entry from a volume.
    Used by per-link X buttons in the volume / camera / checkpoint / enemy panels.
    Volume is renamed automatically based on remaining link count.
    Removing the last link leaves the volume orphaned (per design — user
    can re-link or delete it manually).
    """
    bl_idname   = "og.remove_vol_link"
    bl_label    = "Remove Link"
    bl_options  = {"REGISTER", "UNDO"}
    bl_description = "Remove this single link from the volume"

    vol_name:    bpy.props.StringProperty()
    target_name: bpy.props.StringProperty()

    def execute(self, ctx):
        vol = ctx.scene.objects.get(self.vol_name)
        if not vol:
            self.report({"ERROR"}, f"Volume '{self.vol_name}' not found")
            return {"CANCELLED"}
        if _vol_remove_link_to(vol, self.target_name):
            self.report({"INFO"}, f"Removed link {self.vol_name} → {self.target_name}")
        else:
            self.report({"WARNING"}, f"No link to {self.target_name} on {self.vol_name}")
        return {"FINISHED"}

class OG_OT_AddLinkFromSelection(Operator):
    """Append a link from a volume to a target (specified by name).
    Used by panel buttons that have both objects in scope.
    """
    bl_idname   = "og.add_link_from_selection"
    bl_label    = "Link"
    bl_options  = {"REGISTER", "UNDO"}
    bl_description = "Append a link from this volume to the named target"

    vol_name:    bpy.props.StringProperty()
    target_name: bpy.props.StringProperty()

    def execute(self, ctx):
        vol    = ctx.scene.objects.get(self.vol_name)
        target = ctx.scene.objects.get(self.target_name)
        if not vol:
            self.report({"ERROR"}, f"Volume '{self.vol_name}' not found")
            return {"CANCELLED"}
        if not target:
            self.report({"ERROR"}, f"Target '{self.target_name}' not found")
            return {"CANCELLED"}
        if not _is_linkable(target):
            self.report({"ERROR"}, f"{self.target_name} is not linkable")
            return {"CANCELLED"}
        if _vol_has_link_to(vol, self.target_name):
            self.report({"WARNING"}, f"{self.vol_name} already linked to {self.target_name}")
            return {"CANCELLED"}
        # Cross-volume duplicate check for camera/checkpoint
        if not _is_aggro_target(target):
            existing = _vol_for_target(ctx.scene, self.target_name)
            if existing and existing != vol:
                self.report({"WARNING"},
                    f"{self.target_name} already linked to {existing.name} — unlink first")
                return {"CANCELLED"}
        links = _vol_links(vol)
        entry = links.add()
        entry.target_name = self.target_name
        entry.behaviour   = "cue-chase"
        _rename_vol_for_links(vol)
        self.report({"INFO"}, f"Linked {vol.name} → {self.target_name}")
        return {"FINISHED"}

class OG_OT_ClearActorLink(Operator):
    """Remove an entity link slot from an ACTOR_ empty."""
    bl_idname   = "og.clear_actor_link"
    bl_label    = "Clear Actor Link"
    bl_options  = {"REGISTER", "UNDO"}

    source_name: bpy.props.StringProperty()
    lump_key:    bpy.props.StringProperty()
    slot_index:  bpy.props.IntProperty(default=0)

    def execute(self, ctx):
        obj = ctx.scene.objects.get(self.source_name)
        if not obj:
            self.report({"ERROR"}, f"Source '{self.source_name}' not found")
            return {"CANCELLED"}
        _actor_remove_link(obj, self.lump_key, self.slot_index)
        self.report({"INFO"}, f"Cleared {self.source_name} [{self.lump_key}[{self.slot_index}]]")
        return {"FINISHED"}


# ─── Classes to register ───────────────────────────────────────────────────
CLASSES = (
    OG_OT_MarkNavMesh,
    OG_OT_UnmarkNavMesh,
    OG_OT_LinkNavMesh,
    OG_OT_UnlinkNavMesh,
    OG_OT_AddWaypoint,
    OG_OT_DeleteWaypoint,
    OG_OT_WaypointSourceRemove,
    OG_OT_WaypointSourceMove,
    OG_OT_WaypointSourceFrame,
    OG_OT_WaypointSourceLinkCurve,
    OG_OT_WaypointSourceMigrate,
    OG_OT_LinkVolume,
    OG_OT_UnlinkVolume,
    OG_OT_CleanOrphanedLinks,
    OG_OT_RemoveVolLink,
    OG_OT_AddLinkFromSelection,
    OG_OT_ClearActorLink,
)
