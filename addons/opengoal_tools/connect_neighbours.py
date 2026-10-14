# ---------------------------------------------------------------------------
# connect_neighbours.py — OpenGOAL Level Tools
# Link slot option "connect": {"max": N} (DB actor-link slots, e.g. the dark
# plant's neighbour list): with several of these actors selected, the Entity
# Links panel offers "Connect all": each selected actor's slot gets its
# closest selected neighbours, within Max distance, up to Max connections
# (never more than the slot's "max", what the game reads). The active
# actor's game task is copied to all of them.
# ---------------------------------------------------------------------------
from __future__ import annotations

import bpy

from . import db as _db


def selected_of(ctx, etype):
    return [o for o in ctx.selected_objects
            if o.type == "EMPTY" and o.name.startswith(f"ACTOR_{etype}_") and "_wp_" not in o.name]


def plan(objs, max_dist, max_conn):
    """{name: [neighbour names, closest first]} and the names left alone."""
    out, lonely = {}, []
    for o in objs:
        p = o.matrix_world.translation
        near = sorted(((q.matrix_world.translation - p).length, q.name) for q in objs if q is not o)
        pick = [n for d, n in near if d <= max_dist][:max_conn]
        out[o.name] = pick
        if not pick:
            lonely.append(o.name)
    return out, lonely


def draw(layout, ctx, obj, etype, lkey, sidx, label, opt):
    sel = selected_of(ctx, etype)
    if len(sel) < 2:
        r = layout.row(); r.enabled = False
        r.label(text=f"Select several to connect them all ({label})", icon="INFO")
        return
    box = layout.box()
    box.label(text=f"Connect the {len(sel)} selected", icon="LINKED")
    row = box.row(align=True)
    row.prop(ctx.scene.og_props, "og_connect_max_dist", text="Max distance")
    row.prop(ctx.scene.og_props, "og_connect_max", text="Max links")
    cap = int(opt.get("max", 4))
    if ctx.scene.og_props.og_connect_max > cap:
        w = box.row(); w.alert = True
        w.label(text=f"The game reads {cap} at most", icon="ERROR")
    if _db.has_panel(etype, "game-task"):
        n = box.row(); n.enabled = False
        n.label(text=f"Also gives all of them {obj.name}'s game task", icon="INFO")
    op = box.operator("og.connect_neighbours", text="Connect all", icon="AUTOMERGE_ON")
    op.etype = etype; op.lump_key = lkey; op.slot_index = sidx


class OG_OT_ConnectNeighbours(bpy.types.Operator):
    """Link each selected actor to its closest selected neighbours (within Max
    distance, up to Max links), replacing their current links in this slot,
    and give them all the active actor's game task"""
    bl_idname  = "og.connect_neighbours"
    bl_label   = "Connect All"
    bl_options = {"REGISTER", "UNDO"}

    etype: bpy.props.StringProperty()
    lump_key: bpy.props.StringProperty()
    slot_index: bpy.props.IntProperty()

    def execute(self, ctx):
        from .data import _actor_multi_links, _actor_remove_link, _actor_add_multi_link
        opt = _db.link_slot(self.etype, self.lump_key, self.slot_index).get("connect") or {}
        cap = int(opt.get("max", 4))
        props = ctx.scene.og_props
        objs = selected_of(ctx, self.etype)
        links, lonely = plan(objs, props.og_connect_max_dist, min(props.og_connect_max, cap))
        for o in objs:
            for e in list(_actor_multi_links(o, self.lump_key, self.slot_index)):
                _actor_remove_link(o, self.lump_key, e.slot_index)
            for n in links[o.name]:
                _actor_add_multi_link(o, self.lump_key, self.slot_index, n)
        # the active actor's game task goes to all of them
        task_note = ""
        src = ctx.active_object
        if _db.has_panel(self.etype, "game-task") and src in objs:
            for o in objs:
                for k in ("og_game_task", "og_game_task_custom"):
                    if k in src:
                        o[k] = src[k]
                    elif k in o:
                        del o[k]
            task_note = f", game task {src.get('og_game_task', 'none')} on all"
        n = sum(len(v) for v in links.values())
        if lonely:
            self.report({"WARNING"}, f"Made {n} links{task_note}. No neighbour within {props.og_connect_max_dist:g} m: "
                                     + ", ".join(lonely[:6]) + (" ..." if len(lonely) > 6 else ""))
        else:
            self.report({"INFO"}, f"Made {n} links between {len(objs)} actors{task_note}")
        return {"FINISHED"}


CLASSES = (OG_OT_ConnectNeighbours,)

