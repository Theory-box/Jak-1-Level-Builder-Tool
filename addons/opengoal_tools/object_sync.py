"""Blender's own Delete (X) and Duplicate (Shift+D) on the addon's objects.

A depsgraph handler that only works when the number of objects changes
(moving / editing costs one len() per update). Then, in a timer (data can't
change inside the handler):
- deleted objects: their previews, helper empties (_CAM, _ALIGN, _PIVOT,
  _LOOKAT) and the volume links pointing at them go too
- duplicated objects ("<name>.001"): renamed with the addon's scheme
  (ACTOR_babak_3, CHECKPOINT_<nick>_cp2, CAMERA_4, AMBIENT_snd005), their
  duplicated helpers follow, and actors get their own preview
Objects are tracked by pointer, so a renamed object isn't seen as deleted.
"""
from __future__ import annotations

import re

import bpy

_PREFIXES = ("ACTOR_", "CHECKPOINT_", "CAMERA_", "AMBIENT_")
HELPERS = ("_CAM", "_ALIGN", "_PIVOT", "_LOOKAT")
_DUP_RE = re.compile(r"^(.*)\.\d{3,}$")

_STATE = {"count": -1, "objs": {}}      # pointer -> name of the tracked objects


def _tracked():
    return {o.as_pointer(): o.name for o in bpy.data.objects
            if o.name.startswith(_PREFIXES) and o.library is None}


def _helper_suffix(name):
    return next((s for s in HELPERS if name.endswith(s)), None)


def _free(prefix, width=0):
    n = 0
    while f"{prefix}{n:0{width}d}" in bpy.data.objects:
        n += 1
    return f"{prefix}{n:0{width}d}"


def _new_name(base, o):
    """The addon name for a copy of the object named `base`, or None."""
    if "_wp_" in base or _helper_suffix(base):
        return None
    if base.startswith("ACTOR_"):
        parts = base.split("_", 2)
        return _free(f"ACTOR_{parts[1]}_") if len(parts) == 3 else None
    if base.startswith("CHECKPOINT_"):
        from .collections import spawn_uid
        src = bpy.data.objects.get(base)
        uid = spawn_uid(src) if src is not None else None
        head = base[:len(base) - len(uid)] if uid and base.endswith(uid) else "CHECKPOINT_"
        n = 1
        while f"{head}cp{n}" in bpy.data.objects:
            n += 1
        return f"{head}cp{n}"
    if base.startswith("CAMERA_") and o.type == "CAMERA":
        return _free("CAMERA_")
    m = re.match(r"^(AMBIENT_[a-z]+?)(\d+)$", base)
    if m:
        return _free(m.group(1), len(m.group(2)))
    return None


def _on_deleted(names):
    from .export.volumes import _vol_remove_link_to
    from .model_preview import _is_any_preview
    for o in [o for o in bpy.data.objects if _is_any_preview(o) and o.parent is None]:
        bpy.data.objects.remove(o, do_unlink=True)
    vols = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("VOL_")]
    for name in names:
        if _helper_suffix(name):
            continue
        for suf in HELPERS:
            h = bpy.data.objects.get(name + suf)
            if h is not None:
                bpy.data.objects.remove(h, do_unlink=True)
        for v in vols:
            _vol_remove_link_to(v, name)


def _on_added(objs):
    """Rename Blender's copies; helpers follow their owner's new name."""
    renamed = {}                     # old base name -> new name
    later = []
    for o in objs:
        m = _DUP_RE.match(o.name)
        if not m:
            continue
        base = m.group(1)
        if _helper_suffix(base):
            later.append((o, base))
            continue
        new = _new_name(base, o)
        if new is None:
            continue
        o.name = new
        renamed.setdefault(base, new)
        if new.startswith("ACTOR_"):
            _ensure_preview(o)
    for o, base in later:
        suf = _helper_suffix(base)
        owner = o.parent.name if o.parent is not None and o.parent.name in renamed.values() else renamed.get(base[:-len(suf)])
        if owner and (owner + suf) not in bpy.data.objects:
            o.name = owner + suf
            src = bpy.data.objects.get(owner)
            if suf == "_LOOKAT" and src is not None and src.get("og_cam_look_at"):
                src["og_cam_look_at"] = o.name


def _ensure_preview(o):
    from .model_preview import _is_any_preview, attach_preview
    if any(_is_any_preview(c) for c in o.children):
        return
    try:
        prefs = bpy.context.preferences.addons[__package__].preferences
        if not getattr(prefs, "preview_models", False):
            return
    except KeyError:
        return
    etype = o.name.split("_", 2)[1]
    try:
        attach_preview(bpy.context, etype, o)
    except Exception as e:          # a preview failing must not break the duplicate
        print(f"[og] preview for {o.name}: {e}")


def _sync():
    before = _STATE["objs"]
    now = _tracked()
    gone = [n for p, n in before.items() if p not in now and n not in bpy.data.objects]
    added = [bpy.data.objects.get(n) for p, n in now.items() if p not in before]
    if gone:
        _on_deleted(gone)
    if added:
        _on_added([o for o in added if o is not None])
    _STATE["objs"] = _tracked()
    _STATE["count"] = len(bpy.data.objects)
    return None


@bpy.app.handlers.persistent
def _on_depsgraph(scene, depsgraph):
    n = len(bpy.data.objects)
    if n == _STATE["count"]:
        return
    if _STATE["count"] < 0:
        _STATE["objs"] = _tracked()
        _STATE["count"] = n
        return
    _STATE["count"] = n
    if not bpy.app.timers.is_registered(_sync):
        bpy.app.timers.register(_sync, first_interval=0.0)


@bpy.app.handlers.persistent
def _on_load(*_a):
    """File load / undo / redo: every object is new; track again from scratch."""
    _STATE["count"] = -1
    _STATE["objs"] = {}


def register():
    if _on_depsgraph not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)
    for h in (bpy.app.handlers.load_post, bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        if _on_load not in h:
            h.append(_on_load)


def unregister():
    if _on_depsgraph in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph)
    for h in (bpy.app.handlers.load_post, bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        if _on_load in h:
            h.remove(_on_load)
