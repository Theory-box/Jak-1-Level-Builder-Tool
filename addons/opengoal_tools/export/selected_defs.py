"""Export selected definitions (Object Controls): the selected actors, cameras,
checkpoints and load boundaries as the level export writes them, in one text
file, to paste into a level made without the addon (or to share a setup).

- actors: the level .jsonc "actors" entries + what they need: "art_groups"
  (.jsonc), the .gd files (code .o, tpages, art groups)
- cameras: the .jsonc "cameras" entries (built-in camera system)
- checkpoints: the continue-points of level-info.gc (:continues)
- load boundaries: the static-load-boundary forms of load-boundary-data.gc
"""
from __future__ import annotations

import json

from .paths import log


def _level_name(scene):
    from ..collections import _active_level_col
    col = _active_level_col(scene)
    return str(col.get("og_level_name", col.name)) if col is not None else "level"


def _aid_entries(scene, mesh_names):
    """[(aid, mesh data)] of the actors linked to these meshes (current
    system: aid = base id + place in the export order, like the export)."""
    from ..collections import _level_objects, _get_level_prop
    from .predicates import _canonical_actor_objects
    from .navmesh import nav_compute, nav_tris
    base = int(_get_level_prop(scene, "og_base_id", 10000))
    out = []
    for i, o in enumerate(_canonical_actor_objects(scene, objects=_level_objects(scene))):
        nm = scene.objects.get(o.get("og_navmesh_link", "") or "")
        if nm is not None and nm.name in mesh_names:
            m = nav_compute(nav_tris(nm))
            if m is not None:
                out.append((base + i + 1, m))
    return out


def build(scene, depsgraph, objs):
    """(text, {kind: count}) for the selected objects."""
    from ..collections import actor_lump_name, spawn_uid
    from .actors import collect_actors
    from .levels import needed_ags, needed_extras_ags, needed_code
    from .scene import collect_spawns, collect_load_boundaries, collect_builtin_cameras, camera_system
    from .writers import _make_continues, _make_static_boundary, _dumps_with_raw_lumps, _INTERNAL_ACTOR_KEYS
    from ..data import needed_tpages
    name = _level_name(scene)
    names = {o.name for o in objs}
    out = [f";; OpenGOAL Level Tools: definitions of {len(objs)} selected object(s), level {name}", ""]
    counts = {}

    lumps = {actor_lump_name(n, scene) for n in names if n.startswith("ACTOR_") and "_wp_" not in n}
    actors = [a for a in collect_actors(scene, depsgraph) if a.get("lump", {}).get("name") in lumps] if lumps else []
    if actors:
        counts["actors"] = len(actors)
        ags = needed_ags(actors)
        code = [o for o, _g, _d in needed_code(actors)]
        extras = needed_extras_ags(actors)
        tpages = needed_tpages(actors)
        clean = [{k: v for k, v in a.items() if k not in _INTERNAL_ACTOR_KEYS} for a in actors]
        text = _dumps_with_raw_lumps({"actors": clean})
        body = text[text.index("["):text.rindex("]") + 1]
        lines = body.split("\n")          # the list sat inside {"actors": ...}: one level less indent
        body = "\n".join(l[2:] if l.startswith("  ") else l for l in lines)
        out += [";; ===== Actors: level .jsonc \"actors\" entries =====", body, "",
                ";; .jsonc \"art_groups\":", json.dumps([g.replace(".go", "") for g in ags]), "",
                ";; .gd files these actors need (code first, then tpages / art groups):"]
        out += [f'  "{f}"' for f in code + list(tpages) + ags + extras] or [";;   (none: everything is in GAME.CGO)"]
        out.append("")

    cams = [n for n in names if n.startswith("CAMERA_") and not n.endswith(("_ALIGN", "_PIVOT", "_LOOKAT"))]
    if cams and camera_system(scene) == "builtin":
        entries = [c for c in collect_builtin_cameras(scene)
                   if any(c.get("lump", {}).get("name") == n or str(c.get("lump", {}).get("name", "")).startswith(n + "-")
                          for n in cams)]
        if entries:
            counts["cameras"] = len(cams)
            body = json.dumps(entries, indent=2)
            out += [";; ===== Cameras: level .jsonc \"cameras\" entries =====", body, ""]

    uids = {spawn_uid(o) for o in objs if o.name.startswith("CHECKPOINT_") and not o.name.endswith("_CAM")}
    if uids:
        sp = [s for s in collect_spawns(scene) if s.get("name") in uids]
        if sp:
            counts["checkpoints"] = len(sp)
            out += [";; ===== Checkpoints: level-info.gc continue-points (inside :continues '( ... )) =====",
                    _make_continues(name, sp)[2:-1], ""]

    meshes = []
    for o in objs:
        nm = o if (o.type == "MESH" and (o.get("og_navmesh") or o.name.startswith("NAVMESH_"))) else \
            scene.objects.get(o.get("og_navmesh_link", "") or "")
        if nm is not None and nm not in meshes:
            meshes.append(nm)
    if meshes:
        from .navmesh import nav_system, nav_symbol, nav_compute, nav_tris, nav_mesh_static, _navmesh_to_goal
        counts["nav-meshes"] = len(meshes)
        if nav_system(scene) == "CUSTOM":
            out.append(";; ===== Nav-meshes (custom-nav): a level's <level>-nav.gc, or TFL's tfl-nav-mesh.gc =====")
            for nm in meshes:
                mesh = nav_compute(nav_tris(nm))
                if mesh is None:
                    continue
                sym = nav_symbol(name, nm)
                out += [f";; actors using it: \"custom-nav\": [\"symbol\", \"{sym}\"]",
                        f";; in tfl-nav-mesh.gc, add  ({sym} *nav-{sym}*)  to *custom-nav-list*",
                        f"(define *nav-{sym}*", "  " + nav_mesh_static(mesh, indent="    ").replace("\n", "\n  ") + ")",
                        ";; in a level's -nav.gc (joins the list when the level loads):",
                        f"(unless (custom-nav<-name '{sym})",
                        f"  (set! *custom-nav-list* (cons '({sym} *nav-{sym}*) *custom-nav-list*)))", ""]
        else:
            out.append(";; ===== Nav-meshes (current system): entries of the (case (-> this aid)) in entity.gc =====")
            entries = _aid_entries(scene, {nm.name for nm in meshes})
            out += [_navmesh_to_goal(m, aid) for aid, m in entries] or [";; (no actor linked to these meshes)"]
            out.append("")

    lbs = {n[8:] for n in names if n.startswith("LOADBND_")}
    if lbs:
        bs = [b for b in collect_load_boundaries(scene) if b.get("name") in lbs]
        if bs:
            counts["load boundaries"] = len(bs)
            out += [";; ===== Load boundaries: load-boundary-data.gc (inside a static-lb-list) ====="]
            out += [_make_static_boundary(b, name) for b in bs] + [""]
    log(f"[export selected] {counts or 'nothing exportable'}")
    return "\n".join(out) + "\n", counts
