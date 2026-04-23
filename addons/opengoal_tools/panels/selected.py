# ───────────────────────────────────────────────────────────────────────
# panels/selected.py — OpenGOAL Level Tools
#
# OG_PT_SelectedObject root panel + shared _draw_selected_* helpers + sub-tab panels for selected lumps and sub-categorized tabs.
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


def _entity_passes_filter(etype, props):
    """Return True if this entity should be visible given the current tpage filter.

    Always-visible cases:
      • Filter disabled
      • Entity has no tpage_group field (no heap cost — pickups, most platforms, etc.)
      • Entity's group is in GLOBAL_TPAGE_GROUPS (Village1/2/3, Training — always resident)
      • Both filter dropdowns are NONE (filter on but nothing selected → no restriction)
    """
    if not props.tpage_limit_enabled:
        return True
    info  = ENTITY_DEFS.get(etype, {})
    grp   = info.get("tpage_group")   # None = no tpage concern
    if grp is None:
        return True
    if grp in GLOBAL_TPAGE_GROUPS:
        return True
    g1 = props.tpage_filter_1
    g2 = props.tpage_filter_2
    allowed = {g for g in (g1, g2) if g != "NONE"}
    if not allowed:
        return True                   # filter on, nothing selected → show all
    return grp in allowed



def _og_managed_object(obj):
    """Return True if obj is any OpenGOAL-managed object or any mesh (for collision/bake)."""
    if obj is None:
        return False
    n = obj.name
    if any(n.startswith(p) for p in ("ACTOR_", "SPAWN_", "CHECKPOINT_",
                                      "AMBIENT_", "VOL_", "CAMERA_",
                                      "NAVMESH_")):
        return True
    if n.endswith("_CAM"):
        return True
    # Any mesh object gets collision/lightbake controls
    if obj.type == "MESH":
        return True
    return False



def _draw_selected_actor(layout, sel, scene):
    """Draw settings for a selected ACTOR_ object."""
    parts = sel.name.split("_", 2)
    if len(parts) < 3:
        layout.label(text=sel.name, icon="OBJECT_DATA")
        return
    etype = parts[1]
    einfo = ENTITY_DEFS.get(etype, {})
    label = einfo.get("label", etype)
    cat   = einfo.get("cat", "")

    # Header
    row = layout.row()
    row.label(text=label, icon="OBJECT_DATA")
    sub = row.row()
    sub.enabled = False
    sub.label(text=f"[{cat}]")

    # ── Enemy: Activation distance (idle-distance lump) ──────────────────
    # Per-instance override of the engine's 80m default. Below this distance
    # the enemy wakes up and starts noticing the player. Lower = stays asleep
    # longer. Reads og_idle_distance, emitted as 'idle-distance lump at build.
    if _actor_is_enemy(etype):
        box = layout.box()
        box.label(text="Activation", icon="RADIOBUT_ON")
        _prop_row(box, sel, "og_idle_distance", "Idle Distance (m):", 80.0)
        sub = box.row()
        sub.enabled = False
        sub.label(text="Player must be closer than this to wake the enemy", icon="INFO")

    # ── Nav-enemy: Trigger Behaviour (aggro / patrol / wait-for-cue) ─────
    # Lists every volume that links to this enemy. Each link has its own
    # behaviour dropdown. Only nav-enemies (those that respond to 'cue-chase)
    # get this UI; process-drawable enemies don't have the engine handler.
    if _actor_supports_aggro_trigger(etype):
        box = layout.box()
        box.label(text="Trigger Behaviour", icon="FORCE_FORCE")
        linked_vols = _vols_linking_to(scene, sel.name)
        if linked_vols:
            for v in linked_vols:
                # Find the link entry pointing to this enemy
                entry = _vol_get_link_to(v, sel.name)
                if not entry:
                    continue
                row = box.row(align=True)
                row.label(text=f"✓ {v.name}", icon="MESH_CUBE")
                row.prop(entry, "behaviour", text="")
                op = row.operator("og.select_and_frame", text="", icon="VIEWZOOM")
                op.obj_name = v.name
                op = row.operator("og.remove_vol_link", text="", icon="X")
                op.vol_name    = v.name
                op.target_name = sel.name
        else:
            sub = box.row()
            sub.enabled = False
            sub.label(text="No trigger volumes linked", icon="INFO")
        op = box.operator("og.spawn_aggro_trigger", text="Add Aggro Trigger", icon="ADD")
        op.target_name = sel.name

    # ── Nav-enemy: navmesh management ────────────────────────────────────
    if _actor_uses_navmesh(etype):
        box = layout.box()
        box.label(text="NavMesh", icon="MOD_MESHDEFORM")

        nm_name = sel.get("og_navmesh_link", "")
        nm_obj  = bpy.data.objects.get(nm_name) if nm_name else None

        if nm_obj:
            row = box.row(align=True)
            row.label(text=f"✓ {nm_obj.name}", icon="CHECKMARK")
            row.operator("og.unlink_navmesh", text="", icon="X")
            try:
                nm_obj.data.calc_loop_triangles()
                tc = len(nm_obj.data.loop_triangles)
                box.label(text=f"{tc} triangles", icon="MESH_DATA")
            except Exception:
                pass
        else:
            box.label(text="No mesh linked", icon="ERROR")
            # Only show Link button when a mesh is also selected
            sel_meshes = [o for o in bpy.context.selected_objects if o.type == "MESH"]
            if sel_meshes:
                box.label(text=f"Will link to: {sel_meshes[0].name}", icon="INFO")
                box.operator("og.link_navmesh", text="Link NavMesh", icon="LINKED")
            else:
                box.label(text="Shift-select a mesh to link", icon="INFO")

        nav_r = float(sel.get("og_nav_radius", 6.0))
        box.label(text=f"Fallback sphere radius: {nav_r:.1f}m", icon="SPHERE")

    # ── Platform: sync, path, notice-dist ────────────────────────────────
    elif _actor_is_platform(etype):
        _draw_platform_settings(layout, sel, scene)

    # ── Prop ─────────────────────────────────────────────────────────────
    elif einfo.get("is_prop"):
        box = layout.box()
        box.label(text="Prop — idle animation only", icon="INFO")
        box.label(text="No AI or combat")

    # ── Path requirements ────────────────────────────────────────────────
    else:
        if einfo.get("needs_pathb"):
            box = layout.box()
            box.label(text="Needs 2 path sets", icon="INFO")
            box.label(text="Waypoints: _wp_00... and _wpb_00...")
        elif einfo.get("needs_path"):
            box = layout.box()
            box.label(text="Needs waypoints to patrol", icon="INFO")

    # ── Crate type ───────────────────────────────────────────────────────
    if etype == "crate":
        ct     = sel.get("og_crate_type",          "steel")
        pickup = sel.get("og_crate_pickup",         "money")
        amount = int(sel.get("og_crate_pickup_amount", 1))
        box = layout.box()
        # Build readable summary
        _PICKUP_LABELS = {uid: lbl for (uid, lbl, _, _, _) in CRATE_PICKUP_ITEMS}
        pickup_label = _PICKUP_LABELS.get(pickup, pickup)
        if pickup == "none":
            summary = f"{ct.capitalize()}  —  Empty"
        elif pickup == "buzzer":
            summary = f"{ct.capitalize()}  —  Scout Fly"
        else:
            summary = f"{ct.capitalize()}  —  {pickup_label} ×{amount}"
        box.label(text=summary, icon="PACKAGE")

    # ── Waypoints (full list + add/delete) ───────────────────────────────
    if _actor_uses_waypoints(etype):
        layout.separator(factor=0.3)
        prefix = sel.name + "_wp_"
        wps = sorted(
            [o for o in _level_objects(scene) if o.name.startswith(prefix) and o.type == "EMPTY"],
            key=lambda o: o.name
        )
        box = layout.box()
        box.label(text=f"Path  ({len(wps)} point{'s' if len(wps) != 1 else ''})", icon="ANIM")
        if wps:
            col = box.column(align=True)
            for wp in wps:
                row = col.row(align=True)
                row.label(text=wp.name, icon="EMPTY_AXIS")
                op = row.operator("og.select_and_frame", text="", icon="VIEWZOOM")
                op.obj_name = wp.name
                op = row.operator("og.delete_waypoint", text="", icon="X")
                op.wp_name = wp.name

        row = box.row(align=True)
        row.operator("og.add_waypoint", text="Spawn Waypoint", icon="PLUS").enemy_name = sel.name
        row.prop(scene.og_props, "waypoint_spawn_at_actor", text="Spawn at Position", toggle=False)

        if einfo.get("needs_path") and len(wps) < 1:
            box.label(text="⚠ Needs ≥ 1 waypoint or will crash", icon="ERROR")

        # Path B (swamp-bat)
        if einfo.get("needs_pathb"):
            prefixb = sel.name + "_wpb_"
            wpsb = sorted(
                [o for o in _level_objects(scene) if o.name.startswith(prefixb) and o.type == "EMPTY"],
                key=lambda o: o.name
            )
            box2 = layout.box()
            box2.label(text=f"Path B  ({len(wpsb)} points)", icon="ANIM")
            if wpsb:
                col2 = box2.column(align=True)
                for wp in wpsb:
                    row = col2.row(align=True)
                    row.label(text=wp.name, icon="EMPTY_AXIS")
                    op = row.operator("og.select_and_frame", text="", icon="VIEWZOOM")
                    op.obj_name = wp.name
                    op = row.operator("og.delete_waypoint", text="", icon="X")
                    op.wp_name = wp.name

            row2 = box2.row(align=True)
            op2b = row2.operator("og.add_waypoint", text="Spawn Path B Waypoint", icon="PLUS")
            op2b.enemy_name = sel.name; op2b.pathb_mode = True
            row2.prop(scene.og_props, "waypoint_spawn_at_actor", text="Spawn at Position", toggle=False)

            if len(wpsb) < 1:
                box2.label(text="⚠ swamp-bat crashes without Path B", icon="ERROR")



def _draw_selected_spawn(layout, sel, scene):
    """Draw settings for a SPAWN_ object."""
    layout.label(text=sel.name, icon="EMPTY_ARROWS")
    cam_obj = scene.objects.get(sel.name + "_CAM")
    if cam_obj:
        row = layout.row()
        row.label(text=f"✓ {cam_obj.name}", icon="CAMERA_DATA")
        op = row.operator("og.select_and_frame", text="", icon="VIEWZOOM")
        op.obj_name = cam_obj.name
    else:
        layout.label(text="⚠ No camera anchor", icon="ERROR")
        layout.operator("og.spawn_cam_anchor", text="Add Camera", icon="CAMERA_DATA")



def _draw_selected_checkpoint(layout, sel, scene):
    """Draw settings for a CHECKPOINT_ object."""
    layout.label(text=sel.name, icon="EMPTY_SINGLE_ARROW")

    # Camera
    cam_obj = scene.objects.get(sel.name + "_CAM")
    if cam_obj:
        row = layout.row()
        row.label(text=f"✓ {cam_obj.name}", icon="CAMERA_DATA")
        op = row.operator("og.select_and_frame", text="", icon="VIEWZOOM")
        op.obj_name = cam_obj.name
    else:
        layout.label(text="⚠ No camera anchor", icon="ERROR")
        layout.operator("og.spawn_cam_anchor", text="Add Camera", icon="CAMERA_DATA")

    # Volume link
    layout.separator(factor=0.3)
    vol_list = _vols_linking_to(scene, sel.name)
    if vol_list:
        vol_linked = vol_list[0]
        row = layout.row(align=True)
        row.label(text=f"✓ {vol_linked.name}", icon="MESH_CUBE")
        op = row.operator("og.remove_vol_link", text="", icon="X")
        op.vol_name = vol_linked.name
        op.target_name = sel.name
    else:
        r = float(sel.get("og_checkpoint_radius", 3.0))
        layout.label(text=f"⚠ No trigger volume (fallback r={r:.1f}m)", icon="ERROR")
        op = layout.operator("og.spawn_volume_autolink", text="Add Trigger Volume", icon="MESH_CUBE")
        op.target_name = sel.name



def _draw_selected_emitter(layout, sel):
    """Draw editable settings for an AMBIENT_snd* sound emitter."""
    layout.label(text=sel.name, icon="SPEAKER")
    box = layout.box()
    snd = sel.get("og_sound_name", "?")
    box.label(text=f"Sound: {snd}", icon="PLAY")
    _prop_row(box, sel, "og_sound_radius", "Radius (m):", 15.0)



def _draw_selected_music_zone(layout, sel):
    """Draw editable settings for an AMBIENT_mus* music zone."""
    from ..data import MUSIC_FLAVA_TABLE
    layout.label(text=sel.name, icon="SOUND")

    box = layout.box()
    bank  = sel.get("og_music_bank",  "village1")
    flava = sel.get("og_music_flava", "default")
    flava_list = MUSIC_FLAVA_TABLE.get(bank, ["default"])

    # Bank picker
    row = box.row(align=True)
    row.label(text="Bank:")
    op = row.operator("og.set_music_zone_bank", text=bank, icon="SOUND")

    # Flava picker — button label shows current value
    row2 = box.row(align=True)
    row2.label(text="Flava:")
    flava_display = flava if flava in flava_list else f"{flava} ⚠"
    op2 = row2.operator("og.set_music_zone_flava", text=flava_display, icon="ALIGN_JUSTIFY")
    if flava not in flava_list:
        box.label(text=f"⚠ '{flava}' not in {bank} — exports as default", icon="ERROR")

    box.separator(factor=0.3)
    _prop_row(box, sel, "og_music_priority", "Priority:",  10.0)
    _prop_row(box, sel, "og_music_radius",   "Radius (m):", 40.0)



def _draw_selected_volume(layout, sel, scene):
    """Draw settings for a VOL_ trigger volume.
    Lists every link entry; per-link UI varies by target type:
      camera/checkpoint links → just name + unlink button
      nav-enemy links → name + behaviour dropdown + unlink button
    """
    layout.label(text=sel.name, icon="MESH_CUBE")

    links = _vol_links(sel)
    n = len(links)

    box = layout.box()
    box.label(text=f"Links ({n})", icon="LINKED")

    if n == 0:
        box.label(text="Not linked", icon="INFO")
    else:
        col = box.column(align=True)
        for entry in links:
            tname = entry.target_name
            target = scene.objects.get(tname)
            kind = _classify_target(tname)
            row = col.row(align=True)
            if not target:
                row.alert = True
                row.label(text=f"⚠ missing: {tname}", icon="ERROR")
            else:
                # Icon by target type
                icon = "MESH_CUBE"
                if kind == "camera":
                    icon = "CAMERA_DATA"
                elif kind == "checkpoint":
                    icon = "EMPTY_SINGLE_ARROW"
                elif kind == "enemy":
                    icon = "OUTLINER_OB_ARMATURE"
                row.label(text=tname, icon=icon)
                # Behaviour dropdown — only for nav-enemy targets
                if kind == "enemy":
                    row.prop(entry, "behaviour", text="")
                # Jump-to button
                op = row.operator("og.select_and_frame", text="", icon="VIEWZOOM")
                op.obj_name = tname
            # Per-link unlink button
            op = row.operator("og.remove_vol_link", text="", icon="X")
            op.vol_name = sel.name
            op.target_name = tname

    # Add-link button: enabled when exactly one other linkable object selected
    sel_targets = [o for o in bpy.context.selected_objects
                   if _is_linkable(o) and o != sel]
    if len(sel_targets) == 1:
        op = box.operator("og.add_link_from_selection", text=f"Link → {sel_targets[0].name}", icon="LINKED")
        op.vol_name = sel.name
        op.target_name = sel_targets[0].name
    else:
        box.label(text="Shift-select a target then click Link →", icon="INFO")

    if n > 0:
        layout.operator("og.unlink_volume", text="Clear All Links", icon="X")



def _draw_selected_camera(layout, sel, scene):
    """Draw full settings for a CAMERA_ object."""
    layout.label(text=sel.name, icon="CAMERA_DATA")

    mode   = sel.get("og_cam_mode",   "fixed")

    # ── Mode selector ────────────────────────────────────────────────────
    box = layout.box()
    box.label(text="Mode", icon="OUTLINER_DATA_CAMERA")
    mrow = box.row(align=True)
    for m, lbl in (("fixed","Fixed"),("standoff","Side-Scroll"),("orbit","Orbit")):
        op = mrow.operator("og.set_cam_prop", text=lbl, depress=(mode == m))
        op.cam_name = sel.name; op.prop_name = "og_cam_mode"; op.str_val = m

    # ── Blend time ───────────────────────────────────────────────────────
    _prop_row(box, sel, "og_cam_interp", "Blend (s):", 0.5)

    # ── FOV ──────────────────────────────────────────────────────────────
    _prop_row(box, sel, "og_cam_fov", "FOV (0=default):", 0.0)

    # ── Mode-specific helpers ────────────────────────────────────────────
    if mode == "standoff":
        align_name = sel.name + "_ALIGN"
        has_align = bool(scene.objects.get(align_name))
        arow = box.row()
        if has_align:
            arow.label(text=f"Anchor: {align_name}", icon="CHECKMARK")
            op = arow.operator("og.select_and_frame", text="", icon="VIEWZOOM")
            op.obj_name = align_name
        else:
            arow.label(text="No anchor", icon="ERROR")
            arow.operator("og.spawn_cam_align", text="Add Anchor")

    elif mode == "orbit":
        pivot_name = sel.name + "_PIVOT"
        has_pivot = bool(scene.objects.get(pivot_name))
        prow = box.row()
        if has_pivot:
            prow.label(text=f"Pivot: {pivot_name}", icon="CHECKMARK")
            op = prow.operator("og.select_and_frame", text="", icon="VIEWZOOM")
            op.obj_name = pivot_name
        else:
            prow.label(text="No pivot", icon="ERROR")
            prow.operator("og.spawn_cam_pivot", text="Add Pivot")

    # ── Look-at target ───────────────────────────────────────────────────
    look_at_name = sel.get("og_cam_look_at", "").strip()
    look_obj = scene.objects.get(look_at_name) if look_at_name else None

    lbox = layout.box()
    lbox.label(text="Look-At", icon="PIVOT_CURSOR")
    if look_obj:
        lrow = lbox.row(align=True)
        lrow.label(text=f"Target: {look_at_name}", icon="CHECKMARK")
        op = lrow.operator("og.select_and_frame", text="", icon="VIEWZOOM")
        op.obj_name = look_at_name
        op = lbox.operator("og.set_cam_prop", text="Clear Look-At", icon="X")
        op.cam_name = sel.name; op.prop_name = "og_cam_look_at"; op.str_val = ""
        lbox.label(text="Camera ignores rotation — aims at target", icon="INFO")
    else:
        lbox.label(text="None (uses camera rotation)", icon="DOT")
        lbox.operator("og.spawn_cam_look_at", text="Add Look-At Target", icon="PIVOT_CURSOR")

    # ── Rotation info ────────────────────────────────────────────────────
    try:
        q = sel.matrix_world.to_quaternion()
        rbox = layout.box()
        rbox.label(text=f"Rot (wxyz): {q.w:.2f} {q.x:.2f} {q.y:.2f} {q.z:.2f}", icon="ORIENTATION_GIMBAL")
        if abs(q.w) > 0.99 and not look_obj:
            rbox.label(text="⚠ Camera has no rotation!", icon="ERROR")
            rbox.label(text="Rotate it to aim, then export.")
    except Exception:
        pass

    # ── Linked trigger volumes ───────────────────────────────────────────
    vols = _vols_linking_to(scene, sel.name)
    vbox = layout.box()
    vbox.label(text="Trigger Volumes", icon="MESH_CUBE")
    if vols:
        for v in vols:
            row = vbox.row(align=True)
            row.label(text=v.name, icon="CHECKMARK")
            op = row.operator("og.select_and_frame", text="", icon="VIEWZOOM")
            op.obj_name = v.name
            op = row.operator("og.remove_vol_link", text="", icon="X")
            op.vol_name = v.name
            op.target_name = sel.name
    else:
        vbox.label(text="No trigger — always active", icon="INFO")
    op = vbox.operator("og.spawn_volume_autolink", text="Add Volume", icon="ADD")
    op.target_name = sel.name



def _draw_selected_cam_anchor(layout, sel, scene):
    """Draw settings for a camera anchor (*_CAM)."""
    layout.label(text=sel.name, icon="CAMERA_DATA")
    # Find parent
    parent_name = sel.name[:-4]  # strip _CAM
    parent = scene.objects.get(parent_name)
    if parent:
        row = layout.row(align=True)
        row.label(text=f"Anchored to: {parent_name}", icon="LINKED")
        op = row.operator("og.select_and_frame", text="", icon="VIEWZOOM")
        op.obj_name = parent_name
    else:
        layout.label(text=f"⚠ Parent '{parent_name}' not found", icon="ERROR")



def _draw_selected_navmesh(layout, sel):
    """Draw info for a mesh that is linked as navmesh."""
    layout.label(text=sel.name, icon="MOD_MESHDEFORM")

    # Find which actors reference this mesh
    linked_actors = []
    for o in bpy.data.objects:
        if o.get("og_navmesh_link") == sel.name:
            linked_actors.append(o.name)

    if linked_actors:
        box = layout.box()
        box.label(text=f"Used by {len(linked_actors)} actor(s):", icon="LINKED")
        for name in linked_actors[:6]:
            row = box.row(align=True)
            row.label(text=f"  {name}")
            op = row.operator("og.select_and_frame", text="", icon="VIEWZOOM")
            op.obj_name = name
        if len(linked_actors) > 6:
            box.label(text=f"  … and {len(linked_actors) - 6} more")
    else:
        layout.label(text="Not linked to any actor", icon="INFO")

    try:
        sel.data.calc_loop_triangles()
        tc = len(sel.data.loop_triangles)
        layout.label(text=f"{tc} triangles", icon="MESH_DATA")
    except Exception:
        pass



def _draw_selected_mesh_collision(layout, obj):
    """Draw collision properties for any mesh object."""
    box = layout.box()
    box.label(text="Collision", icon="MOD_PHYSICS")

    box.prop(obj, "set_collision")
    if obj.set_collision:
        col = box.column(align=True)
        col.prop(obj, "ignore")
        col.prop(obj, "collide_mode")
        col.prop(obj, "collide_material")
        col.prop(obj, "collide_event")
        r = col.row(align=True)
        r.prop(obj, "noedge");  r.prop(obj, "noentity")
        r2 = col.row(align=True)
        r2.prop(obj, "nolineofsight"); r2.prop(obj, "nocamera")



def _draw_selected_mesh_visibility(layout, obj):
    """Draw visibility and weight properties for any mesh object."""
    box = layout.box()
    box.label(text="Visibility & Weights", icon="HIDE_OFF")
    box.prop(obj, "set_invisible")
    box.prop(obj, "enable_custom_weights")
    box.prop(obj, "copy_eye_draws")
    box.prop(obj, "copy_mod_draws")



def _draw_selected_mesh_lightbake(layout, ctx):
    """Draw light bake controls for selected mesh(es)."""
    props = ctx.scene.og_props
    targets = [o for o in ctx.selected_objects if o.type == "MESH"]
    if not targets:
        return

    box = layout.box()
    box.label(text="Light Baking", icon="LIGHT")
    box.prop(props, "lightbake_samples")
    row = box.row()
    row.scale_y = 1.4
    row.operator("og.bake_lighting", text=f"Bake {len(targets)} mesh(es)", icon="RENDER_STILL")



def _draw_selected_mesh_navtag(layout, obj):
    """Draw navmesh mark/unmark controls for mesh objects."""
    is_tagged = obj.get("og_navmesh", False)
    box = layout.box()
    box.label(text="NavMesh Tag", icon="MOD_MESHDEFORM")
    if is_tagged:
        box.label(text="✓ Tagged as navmesh geometry", icon="CHECKMARK")
        box.operator("og.unmark_navmesh", text="Unmark as NavMesh", icon="X")
    else:
        box.label(text="Not tagged as navmesh", icon="DOT")
        box.operator("og.mark_navmesh", text="Mark as NavMesh", icon="CHECKMARK")



class OG_PT_SelectedObject(Panel):
    bl_label       = "🔍  Selected Object"
    bl_idname      = "OG_PT_selected_object"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"

    @classmethod
    def poll(cls, ctx):
        return True  # Always visible — draw handles empty/unmanaged selection

    def draw(self, ctx):
        layout = self.layout
        sel    = ctx.active_object

        if sel is None:
            layout.label(text="Select an object to inspect", icon="INFO")
            return

        if not _og_managed_object(sel):
            layout.label(text=sel.name, icon="OBJECT_DATA")
            layout.label(text="Not an OpenGOAL-managed object", icon="INFO")
            return

        # Name + type hint — sub-panels carry all the detail
        name = sel.name
        if name.startswith("ACTOR_") and "_wp_" not in name:
            parts = name.split("_", 2)
            etype = parts[1] if len(parts) >= 3 else ""
            einfo = ENTITY_DEFS.get(etype, {})
            label = einfo.get("label", etype)
            cat   = einfo.get("cat", "")
            row = layout.row()
            row.label(text=label, icon="OBJECT_DATA")
            sub = row.row(); sub.enabled = False
            sub.label(text=f"[{cat}]")
        elif name.startswith("SPAWN_") and not name.endswith("_CAM"):
            layout.label(text=name, icon="EMPTY_ARROWS")
        elif name.startswith("CHECKPOINT_") and not name.endswith("_CAM"):
            layout.label(text=name, icon="EMPTY_SINGLE_ARROW")
        elif name.startswith("AMBIENT_"):
            layout.label(text=name, icon="SPEAKER")
        elif name.startswith("CAMERA_") and sel.type == "CAMERA":
            layout.label(text=name, icon="CAMERA_DATA")
        elif name.startswith("VOL_"):
            layout.label(text=name, icon="MESH_CUBE")
        elif name.endswith("_CAM"):
            layout.label(text=name, icon="CAMERA_DATA")
        elif sel.type == "MESH":
            layout.label(text=name, icon="MOD_MESHDEFORM" if (sel.get("og_navmesh") or name.startswith("NAVMESH_")) else "MESH_DATA")
        else:
            layout.label(text=name, icon="OBJECT_DATA")

        # Universal actions
        layout.separator(factor=0.3)
        row = layout.row(align=True)
        op = row.operator("og.select_and_frame", text="Frame", icon="VIEWZOOM")
        op.obj_name = name
        if name.startswith("ACTOR_") and "_wp_" not in name:
            row.operator("og.duplicate_entity", text="Duplicate", icon="COPYDOWN")
        op = row.operator("og.delete_object", text="Delete", icon="TRASH")
        op.obj_name = name



class OG_PT_SelectedCollision(Panel):
    bl_label       = "Collision"
    bl_idname      = "OG_PT_selected_collision"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        return sel is not None and sel.type == "MESH"

    def draw(self, ctx):
        _draw_selected_mesh_collision(self.layout, ctx.active_object)
        self.layout.separator(factor=0.2)
        _draw_selected_mesh_visibility(self.layout, ctx.active_object)



class OG_PT_SelectedLightBaking(Panel):
    bl_label       = "Light Baking"
    bl_idname      = "OG_PT_selected_lightbaking"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        return sel is not None and sel.type == "MESH"

    def draw(self, ctx):
        _draw_selected_mesh_lightbake(self.layout, ctx)



class OG_PT_SelectedNavMeshTag(Panel):
    bl_label       = "NavMesh"
    bl_idname      = "OG_PT_selected_navmesh_tag"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        return sel is not None and sel.type == "MESH"

    def draw(self, ctx):
        _draw_selected_mesh_navtag(self.layout, ctx.active_object)



def _draw_actor_links(layout, obj, scene, etype):
    """Draw the Actor Links panel for an ACTOR_ empty.

    Shows each defined slot with:
    - Current linked target (name + jump-to button) or 'Not set'
    - A 'Link →' button when exactly one compatible ACTOR_ is shift-selected
    - An X (clear) button when a link is set
    """
    slots = _actor_link_slots(etype)
    if not slots:
        layout.label(text="No entity link slots for this actor type.", icon="INFO")
        return

    # Gather the currently shift-selected ACTOR_ empties (excluding this one)
    sel_actors = [
        o for o in bpy.context.selected_objects
        if o != obj
        and o.type == "EMPTY"
        and o.name.startswith("ACTOR_")
        and "_wp_" not in o.name
        and "_wpb_" not in o.name
    ]

    # Group slots by lump_key for display
    seen_keys = []
    for (lkey, sidx, label, accepted, required) in slots:
        if lkey not in seen_keys:
            seen_keys.append(lkey)

    for lkey in seen_keys:
        key_slots = [(sidx, lbl, acc, req) for (lk, sidx, lbl, acc, req) in slots if lk == lkey]

        box = layout.box()
        box.label(text=lkey, icon="LINKED")

        for (sidx, label, accepted, required) in key_slots:
            entry = _actor_get_link(obj, lkey, sidx)
            current_name = entry.target_name if entry else ""
            current_obj  = scene.objects.get(current_name) if current_name else None

            row = box.row(align=True)

            # Slot label
            req_mark = " *" if required else ""
            row.label(text=f"[{sidx}] {label}{req_mark}")

            if current_obj:
                # Linked — show name, jump-to, clear buttons
                row2 = box.row(align=True)
                row2.label(text=current_name, icon="CHECKMARK")
                op = row2.operator("og.select_and_frame", text="", icon="VIEWZOOM")
                op.obj_name = current_name
                op = row2.operator("og.clear_actor_link", text="", icon="X")
                op.source_name = obj.name
                op.lump_key    = lkey
                op.slot_index  = sidx
            elif current_name:
                # Name stored but object missing from scene
                row2 = box.row(align=True)
                row2.alert = True
                row2.label(text=f"⚠ missing: {current_name}", icon="ERROR")
                op = row2.operator("og.clear_actor_link", text="", icon="X")
                op.source_name = obj.name
                op.lump_key    = lkey
                op.slot_index  = sidx
            else:
                # Not set
                row2 = box.row(align=True)
                row2.enabled = False
                req_text = "Required — not set" if required else "Optional — not set"
                row2.label(text=req_text, icon="ERROR" if required else "DOT")

            # Link button: visible when one compatible actor is shift-selected
            compatible = [
                o for o in sel_actors
                if accepted == ["any"] or
                   (len(o.name.split("_", 2)) >= 3 and o.name.split("_", 2)[1] in accepted)
            ]
            if len(compatible) == 1:
                tgt = compatible[0]
                op = box.operator("og.set_actor_link",
                                  text=f"Link → {tgt.name}", icon="LINKED")
                op.source_name = obj.name
                op.lump_key    = lkey
                op.slot_index  = sidx
                op.target_name = tgt.name
            elif len(sel_actors) > 0 and len(compatible) == 0:
                hint = box.row()
                hint.enabled = False
                hint.label(text=f"Selected actor not valid for this slot", icon="INFO")
                hint2 = box.row()
                hint2.enabled = False
                hint2.label(text=f"  Accepted: {', '.join(accepted)}")
            else:
                hint = box.row()
                hint.enabled = False
                hint.label(text="Shift-select target then click Link →", icon="INFO")



class OG_PT_SpawnSettings(Panel):
    bl_label       = "Spawn Settings"
    bl_idname      = "OG_PT_spawn_settings"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        return (sel is not None
                and sel.name.startswith("SPAWN_")
                and not sel.name.endswith("_CAM"))

    def draw(self, ctx):
        _draw_selected_spawn(self.layout, ctx.active_object, ctx.scene)



def _draw_lump_panel(layout, obj):
    """Draw the Custom Lumps assisted-entry list for an ACTOR_ empty."""
    rows   = obj.og_lump_rows
    index  = obj.og_lump_rows_index

    # Column header labels
    hdr = layout.row(align=True)
    hdr.label(text="Key")
    hdr.label(text="Type")
    hdr.label(text="Value")

    # Scrollable UIList  — 5 rows visible, expandable
    layout.template_list(
        "OG_UL_LumpRows", "",
        obj, "og_lump_rows",
        obj, "og_lump_rows_index",
        rows=5,
    )

    # Add / Remove buttons
    row = layout.row(align=True)
    row.operator("og.add_lump_row",    text="Add",    icon="ADD")
    row.operator("og.remove_lump_row", text="Remove", icon="REMOVE")

    # Inline error detail for the currently selected row
    if rows and 0 <= index < len(rows):
        item = rows[index]
        _, err = _parse_lump_row(item.key, item.ltype, item.value)
        if err:
            box = layout.box()
            box.label(text=f"⚠ Row {index+1}: {err}", icon="ERROR")
        elif item.key.strip() in _LUMP_HARDCODED_KEYS:
            box = layout.box()
            box.label(text=f"'{item.key}' overrides addon default", icon="INFO")

    if not rows:
        sub = layout.row()
        sub.enabled = False
        sub.label(text="No custom lumps — click Add to start", icon="INFO")



class OG_PT_SelectedLumps(Panel):
    bl_label       = "Custom Lumps"
    bl_idname      = "OG_PT_selected_lumps"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        return (sel is not None
                and sel.name.startswith("ACTOR_")
                and "_wp_" not in sel.name)

    def draw(self, ctx):
        _draw_lump_panel(self.layout, ctx.active_object)



def _draw_lump_ref_section(layout, title, entries, icon="DOT"):
    """Draw a collapsible read-only reference section."""
    if not entries:
        return
    box = layout.box()
    box.label(text=title, icon=icon)
    col = box.column(align=True)
    for key, ltype, desc in entries:
        row = col.row(align=True)
        row.label(text=key, icon="KEYFRAME")
        sub = row.row(align=True)
        sub.enabled = False
        sub.label(text=ltype)
        op = row.operator("og.use_lump_ref", text="", icon="ADD")
        op.lump_key   = key
        op.lump_ltype = ltype
        # Description as a greyed-out label on the next line
        desc_row = col.row()
        desc_row.enabled = False
        desc_row.label(text=f"  {desc}")
        col.separator(factor=0.3)



class OG_PT_SelectedLumpReference(Panel):
    bl_label       = "Lump Reference"
    bl_idname      = "OG_PT_selected_lump_reference"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "OpenGOAL"
    bl_parent_id   = "OG_PT_selected_object"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, ctx):
        sel = ctx.active_object
        return (sel is not None
                and sel.name.startswith("ACTOR_")
                and "_wp_" not in sel.name)

    def draw(self, ctx):
        layout = self.layout
        sel    = ctx.active_object
        parts  = sel.name.split("_", 2)
        if len(parts) < 3:
            layout.label(text="Unknown actor type", icon="ERROR")
            return
        etype = parts[1]
        einfo = ENTITY_DEFS.get(etype, {})
        label = einfo.get("label", etype)

        universal, actor_specific = _lump_ref_for_etype(etype)

        layout.label(text=f"Available lumps for: {label}", icon="INFO")
        layout.label(text="Click + to add a pre-filled row to Custom Lumps")
        layout.separator(factor=0.4)

        _draw_lump_ref_section(layout, "Universal (all actors)", universal, icon="WORLD")
        if actor_specific:
            _draw_lump_ref_section(layout, f"Specific to {label}", actor_specific, icon="OBJECT_DATA")
        else:
            sub = layout.row()
            sub.enabled = False
            sub.label(text=f"No additional lumps documented for {label}", icon="INFO")




# ─── Classes to register ───────────────────────────────────────────────────
CLASSES = (
    OG_PT_SelectedObject,
    OG_PT_SelectedCollision,
    OG_PT_SelectedLightBaking,
    OG_PT_SelectedNavMeshTag,
    OG_PT_SpawnSettings,
    OG_PT_SelectedLumps,
    OG_PT_SelectedLumpReference,
)
