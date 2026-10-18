# ───────────────────────────────────────────────────────────────────────
# export/navmesh.py — OpenGOAL Level Tools
#
# Navmesh processing: mesh → path-grid computation, GOAL-source emission, scene scan for navmesh actors + associated meshes.
# ───────────────────────────────────────────────────────────────────────

from __future__ import annotations

import bpy, os, re, json, math, mathutils
from pathlib import Path
from ..data import (
    ENTITY_DEFS, ETYPE_CODE, ETYPE_TPAGES, ETYPE_AG, VERTEX_EXPORT_TYPES,
    needed_tpages, ACTOR_LINK_DEFS,
    _lump_ref_for_etype, _actor_link_slots, _actor_has_links,
    _actor_links, _actor_get_link, _actor_set_link,
    _actor_remove_link, _build_actor_link_lumps,
    _parse_lump_row, _aggro_event_id, AGGRO_TRIGGER_EVENTS,
    _LUMP_HARDCODED_KEYS, _is_custom_type,
)
from ..collections import (
    _get_level_prop, _level_objects,
    _active_level_col, _classify_object, _col_path_for_entity,
    _ensure_sub_collection, _recursive_col_objects,
    _COL_PATH_WAYPOINTS, _COL_PATH_NAVMESHES,
)
from ..collections import (
    _COL_PATH_SPAWNABLE_ENEMIES, _COL_PATH_SPAWNABLE_PLATFORMS,
    _COL_PATH_SPAWNABLE_PROPS, _COL_PATH_SPAWNABLE_NPCS,
    _COL_PATH_SPAWNABLE_PICKUPS, _COL_PATH_TRIGGERS, _COL_PATH_CAMERAS,
    _COL_PATH_SPAWNS, _COL_PATH_SOUND_EMITTERS, _COL_PATH_GEO_SOLID,
    _COL_PATH_GEO_COLLISION, _COL_PATH_GEO_VISUAL, _COL_PATH_GEO_REFERENCE,
    _COL_PATH_WAYPOINTS, _COL_PATH_NAVMESHES,
    _ENTITY_CAT_TO_COL_PATH, _LEVEL_COL_DEFAULTS,
    _all_level_collections, _active_level_col, _col_is_no_export,
    _recursive_col_objects, _level_objects, _ensure_sub_collection,
    _link_object_to_sub_collection, _col_path_for_entity, _classify_object,
    _get_level_prop, _set_level_prop, _active_level_items,
    _set_blender_active_collection, _get_death_plane, _set_death_plane,
    _on_active_level_changed,
)

# Cross-module imports (siblings in the export package)
from .paths import (
    log,
)
from .predicates import (
    _canonical_actor_objects,
)


# Cross-module imports (siblings in the export package)


# ── nav-mesh core (shared by both nav-mesh systems) ──────────────────────────
# (appended to export/navmesh.py by patch_nav1.py)

NAV_MATERIALS = (                      # (name, pat bits, colour of the game's nav viewer)
    ("NAV Walk", 0, "#0080FF"),
    ("NAV Jump", 1, "#1B7679"),
    ("NAV Special", 2, "#199459"),
)
_NAV_PAT = {n: p for n, p, _c in NAV_MATERIALS}
NAV_LIMIT = 255                        # u8 indices, #xff = no neighbour


def nav_tris(obj):
    """[((p0, p1, p2), pat)] of a nav-mesh object, game coords (x, z, -y), metres.
    The face's material picks pat: NAV Jump = 1 (gap: nav-enemies jump it),
    NAV Special = 2 (sharkey water / yakow pen), anything else 0."""
    me = obj.data
    me.calc_loop_triangles()
    mat = obj.matrix_world
    mats = [s.material.name if s.material else "" for s in obj.material_slots]
    out = []
    for tri in me.loop_triangles:
        pts = []
        for vi in tri.vertices:
            co = mat @ me.vertices[vi].co
            pts.append((round(co.x, 4), round(co.z, 4), round(-co.y, 4)))
        base = mats[tri.material_index].split(".")[0] if tri.material_index < len(mats) else ""
        out.append((tuple(pts), _NAV_PAT.get(base, 0)))
    return out


def _cross_y(a, b, c):
    """y of (b-a) x (c-a): the engine's facing test (vector-3pt-cross!)."""
    ux, uz = b[0] - a[0], b[2] - a[2]
    vx, vz = c[0] - a[0], c[2] - a[2]
    return uz * vx - ux * vz


def _bvh(polys, rel, pad_xz=1.0, pad_y=5.0):
    """nav-node tree for find-poly-fast: [(center, radius, type, left, right, tris)].
    Node 0 is the root; branch nodes (type 0) give byte offsets of their two
    children (48-byte nodes), leaves (type 1) hold up to 8 triangles."""
    nodes = []

    def bounds(ids):
        pts = [rel[v] for i in ids for v in polys[i]]
        lo = [min(p[k] for p in pts) for k in range(3)]
        hi = [max(p[k] for p in pts) for k in range(3)]
        c = tuple((lo[k] + hi[k]) / 2 for k in range(3))
        r = ((hi[0] - lo[0]) / 2 + pad_xz, (hi[1] - lo[1]) / 2 + pad_y, (hi[2] - lo[2]) / 2 + pad_xz)
        return c, r, lo, hi

    def build(ids):
        me = len(nodes)
        nodes.append(None)
        c, r, lo, hi = bounds(ids)
        if len(ids) <= 8:
            nodes[me] = (c, r, 1, 0, 0, list(ids))
            return me
        axis = 0 if (hi[0] - lo[0]) >= (hi[2] - lo[2]) else 2
        cent = lambda i: sum(rel[v][axis] for v in polys[i]) / 3
        s = sorted(ids, key=cent)
        half = len(s) // 2
        left = build(s[:half])
        right = build(s[half:])
        nodes[me] = (c, r, 0, left * 48, right * 48, [])
        return me

    build(list(range(len(polys))))
    return nodes


def nav_compute(tris, full=True):
    """Merged vertices, triangles (facing up), adjacency, route table, node tree
    and problems for a nav-mesh. tris: nav_tris() output. full=False stops
    after the checks (no route table / nodes: cheap, for the warnings)."""
    EPS = 0.01
    verts, problems = [], []
    grid = {}

    def find_or_add(pt):
        key = (round(pt[0] / EPS), round(pt[1] / EPS), round(pt[2] / EPS))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    i = grid.get((key[0] + dx, key[1] + dy, key[2] + dz))
                    if i is not None and all(abs(verts[i][k] - pt[k]) < EPS for k in range(3)):
                        return i
        verts.append(pt)
        grid[key] = len(verts) - 1
        return len(verts) - 1

    polys, pats = [], []
    flipped = degenerate = 0
    for (a, b, c), pat in tris:
        i0, i1, i2 = find_or_add(a), find_or_add(b), find_or_add(c)
        if len({i0, i1, i2}) < 3:
            degenerate += 1
            continue
        y = _cross_y(verts[i0], verts[i1], verts[i2])
        if abs(y) < 1e-9:
            degenerate += 1
            continue
        if y < 0:                                  # facing down in game: flip it
            i1, i2 = i2, i1
            flipped += 1
        polys.append((i0, i1, i2))
        pats.append(pat)
    N, V = len(polys), len(verts)
    if N == 0:
        return None
    if degenerate:
        problems.append(f"{degenerate} triangle(s) with no area or standing up (skipped)")
    if N > NAV_LIMIT:
        problems.append(f"{N} triangles: the game allows {NAV_LIMIT} at most")
    if V > NAV_LIMIT:
        problems.append(f"{V} vertices: the game allows {NAV_LIMIT} at most")
    if all(p & 1 for p in pats):
        problems.append("only jump (gap) triangles: needs walkable ones")

    ox, oy, oz = (sum(v[k] for v in verts) / V for k in range(3))
    rel = [(v[0] - ox, v[1] - oy, v[2] - oz) for v in verts]
    bounds_r = max(math.sqrt(x * x + y * y + z * z) for x, y, z in rel) + 5.0

    edge_to = {}
    for pi, (v0, v1, v2) in enumerate(polys):
        for ea, eb in ((v0, v1), (v1, v2), (v2, v0)):
            edge_to.setdefault((min(ea, eb), max(ea, eb)), []).append(pi)
    crowded = sum(1 for ps in edge_to.values() if len(ps) > 2)
    if crowded:
        problems.append(f"{crowded} edge(s) shared by 3+ triangles (only 2 are joined)")
    adj = []
    for pi, (v0, v1, v2) in enumerate(polys):
        nb = []
        for ea, eb in ((v0, v1), (v1, v2), (v2, v0)):
            others = [p for p in edge_to[(min(ea, eb), max(ea, eb))] if p != pi]
            nb.append(others[0] if others else 0xFF)
        adj.append(tuple(nb))
    # soft problems (it works, but enemies can't use all of it)
    soft = []

    def regions(keep):
        """Connected groups of the triangles keep() picks: [group id per triangle] (-1 = not picked), count."""
        rid, n = [-1] * N, 0
        for s0 in range(N):
            if rid[s0] >= 0 or not keep(s0):
                continue
            stack = [s0]; rid[s0] = n
            while stack:
                cur = stack.pop()
                for nb in adj[cur]:
                    if nb != 0xFF and rid[nb] < 0 and keep(nb):
                        rid[nb] = n; stack.append(nb)
            n += 1
        return rid, n
    _all, parts = regions(lambda i: True)            # islands: parts no edge joins
    if parts > 1:
        soft.append(f"{parts} separate parts: enemies can't path from one to another")
    walk, _nw = regions(lambda i: not pats[i] & 1)
    jump, nj = regions(lambda i: bool(pats[i] & 1))
    dead = 0
    for j in range(nj):                              # a jump area should join two walkable areas
        touch = {walk[nb] for i in range(N) if jump[i] == j for nb in adj[i] if nb != 0xFF and walk[nb] >= 0}
        if len(touch) < 2:
            dead += 1
    if dead and any(not p & 1 for p in pats):
        soft.append(f"{dead} jump area(s) not joining two walkable areas: enemies stop at them")
    if not full:
        return {"poly_count": N, "vertex_count": V, "problems": problems, "soft": soft, "flipped": flipped}

    INF = 1 << 30

    def bfs_from(src):
        dist = [INF] * N
        came = [None] * N
        dist[src] = 0
        q, qi = [src], 0
        while qi < len(q):
            cur = q[qi]; qi += 1
            for slot, nb in enumerate(adj[cur]):
                if nb != 0xFF and dist[nb] == INF:
                    dist[nb] = dist[cur] + 1
                    came[nb] = (cur, slot)
                    q.append(nb)
        hop = [3] * N
        for dst in range(N):
            if dst == src or dist[dst] == INF:
                continue
            node = dst
            while came[node][0] != src:
                node = came[node][0]
            hop[dst] = came[node][1]
        return hop

    route_bytes = bytearray((N * N * 2 + 7) // 8)
    for frm in range(N):
        hop = bfs_from(frm)
        for to in range(N):
            bit = (frm * N + to) * 2
            route_bytes[bit // 8] |= (hop[to] & 3) << (bit % 8)
    n4 = (len(route_bytes) + 3) // 4
    route_bytes += bytearray(n4 * 4 - len(route_bytes))
    vec4ubs = [tuple(route_bytes[i * 4:(i + 1) * 4]) for i in range(n4)]
    return {"origin": (ox, oy, oz), "bounds_r": bounds_r, "verts_rel": rel, "polys": polys,
            "pats": pats, "adj": adj, "vec4ubs": vec4ubs, "poly_count": N, "vertex_count": V,
            "nodes": _bvh(polys, rel), "flipped": flipped, "problems": problems, "soft": soft}


def nav_mesh_static(mesh, indent="  "):
    """(new 'static 'nav-mesh ...) of a nav_compute() result. Same layout as
    The Forgotten Lands' tfl-nav-mesh.gc (no mod-base only fields)."""
    hx = lambda n: f"#x{n:x}"
    m = lambda v: f"(meters {v:.4f})"
    ox, oy, oz = mesh["origin"]
    I = indent
    L = [f"(new 'static 'nav-mesh",
         f"{I}:bounds (new 'static 'sphere :x {m(ox)} :y {m(oy)} :z {m(oz)} :w {m(mesh['bounds_r'])})",
         f"{I}:origin (new 'static 'vector :x {m(ox)} :y {m(oy)} :z {m(oz)} :w 1.0)",
         f"{I}:node-count {len(mesh['nodes'])}",
         f"{I}:nodes (new 'static 'inline-array nav-node {len(mesh['nodes'])}"]
    for (cx, cy, cz), (rx, ry, rz), typ, lo, ro, tris in mesh["nodes"]:
        head = (f"{I}  (new 'static 'nav-node :center-x {m(cx)} :center-y {m(cy)} :center-z {m(cz)} :type {typ}"
                f" :radius-x {m(rx)} :radius-y {m(ry)} :radius-z {m(rz)}")
        if typ == 0:
            L.append(head + f" :left-offset {lo} :right-offset {ro})")
        else:
            t = list(tris) + [0] * (8 - len(tris))
            L.append(head + f" :num-tris {len(tris)}"
                     f" :first-tris (new 'static 'array uint8 4 {' '.join(hx(x) for x in t[:4])})"
                     f" :last-tris (new 'static 'array uint8 4 {' '.join(hx(x) for x in t[4:])}))")
    L[-1] += ")"
    L.append(f"{I}:vertex-count {mesh['vertex_count']}")
    L.append(f"{I}:vertex (new 'static 'inline-array nav-vertex {mesh['vertex_count']}")
    for x, y, z in mesh["verts_rel"]:
        L.append(f"{I}  (new 'static 'nav-vertex :x {m(x)} :y {m(y)} :z {m(z)} :w 1.0)")
    L[-1] += ")"
    L.append(f"{I}:poly-count {mesh['poly_count']}")
    L.append(f"{I}:poly (new 'static 'inline-array nav-poly {mesh['poly_count']}")
    for i, ((v0, v1, v2), (a0, a1, a2), pat) in enumerate(zip(mesh["polys"], mesh["adj"], mesh["pats"])):
        L.append(f"{I}  (new 'static 'nav-poly :id {hx(i)} :vertex (new 'static 'array uint8 3 {hx(v0)} {hx(v1)} {hx(v2)})"
                 f" :adj-poly (new 'static 'array uint8 3 {hx(a0)} {hx(a1)} {hx(a2)})" + (f" :pat {pat})" if pat else ")"))
    L[-1] += ")"
    L.append(f"{I}:route (new 'static 'inline-array vector4ub {len(mesh['vec4ubs'])}")
    for b in mesh["vec4ubs"]:
        L.append(f"{I}  (new 'static 'vector4ub :data (new 'static 'array uint8 4 {' '.join(hx(x) for x in b)}))")
    L[-1] += "))"
    return "\n".join(L)


def nav_issues(nav_obj):
    """Problems of a nav-mesh object for the warnings (no triangles, over 255
    triangles / vertices, zero-area, 3+ triangles on an edge, only jump faces)."""
    if nav_obj is None or nav_obj.type != "MESH":
        return []
    m = nav_compute(nav_tris(nav_obj), full=False)
    return ["no triangles"] if m is None else m["problems"]


def nav_soft_issues(nav_obj):
    """Soft problems of a nav-mesh object (it works, enemies can't use all of
    it): separate parts, jump areas that don't join two walkable areas."""
    if nav_obj is None or nav_obj.type != "MESH":
        return []
    m = nav_compute(nav_tris(nav_obj), full=False)
    return [] if m is None else m["soft"]


def nav_spheres(nav_obj):
    """[[x, y, z, r]] (game coords, metres) of a nav-mesh's nav-sphere empties:
    the empty's position, radius = display size x its largest scale."""
    out = []
    for e in getattr(nav_obj, "og_nav_spheres", ()):
        o = e.obj
        if o is None:
            continue
        p = o.matrix_world.translation
        r = o.empty_display_size * max(o.matrix_world.to_scale()) if o.type == "EMPTY" else max(o.dimensions) / 2
        out.append([round(p.x, 4), round(p.z, 4), round(-p.y, 4), round(r, 4)])
    return out


def _navmesh_to_goal(mesh, actor_aid):
    """One (case (-> this aid)) entry of the current system's entity.gc block."""
    body = nav_mesh_static(mesh, indent="            ")
    return f"    (({actor_aid})\n      (set! (-> this nav-mesh)\n        " + body.replace("\n", "\n        ") + "))"


def _collect_navmesh_actors(scene):
    """
    Returns list of (actor_aid, mesh_data) for actors linked to navmeshes.
    actor_aid = base_id + 1-based index in canonical actor order,
    matching exactly what collect_actors and the JSONC builder assign.
    """
    if nav_system(scene) == "CUSTOM":
        return []                       # custom-nav: meshes go in the level's -nav.gc
    base_id = int(_get_level_prop(scene, "og_base_id", 10000))
    level_objs = _level_objects(scene)
    ordered = _canonical_actor_objects(scene, objects=level_objs)

    result = []
    for idx, o in enumerate(ordered):
        nm_name = o.get("og_navmesh_link", "")
        if not nm_name:
            continue
        nm_obj = scene.objects.get(nm_name)
        if not nm_obj or nm_obj.type != "MESH":
            continue

        actor_aid = base_id + idx + 1  # base_id+1 = first actor AID
        log(f"[navmesh] {o.name} idx={idx} aid={actor_aid} -> {nm_name}")

        mesh_data = nav_compute(nav_tris(nm_obj))
        if mesh_data:
            result.append((actor_aid, mesh_data))
            log(f"[navmesh]   {mesh_data['poly_count']} polys, {len(mesh_data['nodes'])} nodes"
                + (f", {mesh_data['flipped']} flipped to face up" if mesh_data['flipped'] else ""))
            for p in mesh_data["problems"]:
                log(f"[navmesh]   WARNING {nm_name}: {p}")
        else:
            log(f"[navmesh]   WARNING: navmesh compute returned nothing for {o.name}")

    return result

# ── nav-mesh systems ─────────────────────────────────────────────────────────
# AID    (default): entity.gc gets a (case (-> this aid)) block, every build.
# CUSTOM : The Forgotten Lands' "custom-nav": each level's meshes go in
#          goal_src/levels/<level>/<level>-nav.gc (loaded with the level) and
#          join *custom-nav-list*; an actor picks one with its 'custom-nav
#          symbol lump. The lookup / setup is level-tools/lt-nav-mesh.gc (or
#          TFL's own engine/mods/tfl-nav-mesh.gc when the install has it).

def nav_system(scene):
    return getattr(getattr(scene, "og_props", None), "og_navmesh_system", "AID") if scene is not None else "AID"


def tfl_nav_present():
    """The install has The Forgotten Lands' nav-mesh code (its list, lookup and hook)."""
    from .paths import _goal_src
    return (_goal_src() / "engine" / "mods" / "tfl-nav-mesh.gc").exists()


def nav_symbol(level, obj):
    """custom-nav name of a nav-mesh: <level>-<mesh name without NAVMESH_>."""
    base = obj.name[8:] if obj.name.startswith("NAVMESH_") else obj.name
    base = re.sub(r"[^a-z0-9-]+", "-", base.lower()).strip("-") or "mesh"
    return f"{level}-{base}"


def level_nav_meshes(scene):
    """[(mesh object, [actors linked to it, canonical order])] of the active level."""
    level_objs = _level_objects(scene)
    out = {}
    for o in _canonical_actor_objects(scene, objects=level_objs):
        nm = scene.objects.get(o.get("og_navmesh_link", "") or "")
        if nm is not None and nm.type == "MESH":
            out.setdefault(nm, []).append(o)
    return list(out.items())


def nav_actor_lumps(scene, level):
    """{actor name: {lump: value}} the nav-mesh systems add: 'custom-nav' (CUSTOM)
    and 'nav-mesh-sphere' (the mesh's spheres). The game keeps spheres per mesh,
    read from the actor that sets the mesh up: CUSTOM gives them to the mesh's
    first actor (like TFL), AID to every actor (each has its own copy)."""
    custom = nav_system(scene) == "CUSTOM"
    out = {}
    for nm, actors in level_nav_meshes(scene):
        sph = nav_spheres(nm)
        for i, a in enumerate(actors):
            d = out.setdefault(a.name, {})
            if custom:
                d["custom-nav"] = ["symbol", nav_symbol(level, nm)]
            if sph and (i == 0 or not custom):
                d["nav-mesh-sphere"] = ["vector4m"] + sph
    return out


def nav_gc_path(name):
    from .paths import _goal_src
    return _goal_src() / "levels" / name / f"{name}-nav.gc"


def write_nav_gc(name, scene):
    """CUSTOM: write <level>-nav.gc (only when changed); otherwise remove it.
    Returns True when the level has one."""
    from .level_tools import _write_if_changed
    p = nav_gc_path(name)
    meshes = level_nav_meshes(scene) if nav_system(scene) == "CUSTOM" else []
    if not meshes:
        if p.exists():
            p.unlink()
            log(f"Removed {p.name}")
        return False
    L = [";;-*-Lisp-*-", "(in-package goal)",
         f";; {name}-nav.gc -- nav-meshes of level {name} (written by OpenGOAL Level Tools).",
         ";; custom-nav system (The Forgotten Lands style): an actor picks a mesh with its",
         ";; 'custom-nav symbol lump; meshes join *custom-nav-list* when the level loads.", ""]
    seen = set()
    for nm, _actors in meshes:
        sym = nav_symbol(name, nm)
        if sym in seen:
            continue
        seen.add(sym)
        mesh = nav_compute(nav_tris(nm))
        if mesh is None:
            log(f"[navmesh] WARNING {nm.name}: no triangles - skipped")
            continue
        for pr in mesh["problems"]:
            log(f"[navmesh] WARNING {nm.name}: {pr}")
        L.append(f"(define *nav-{sym}*")
        L.append("  " + nav_mesh_static(mesh, indent="    ").replace("\n", "\n  ") + ")")
        L.append(f"(unless (custom-nav<-name '{sym})")
        L.append(f"  (set! *custom-nav-list* (cons '({sym} *nav-{sym}*) *custom-nav-list*)))")
        L.append("")
        log(f"[navmesh] {nm.name} -> custom-nav '{sym}' ({mesh['poly_count']} polys, {len(mesh['nodes'])} nodes)")
    p.parent.mkdir(parents=True, exist_ok=True)
    _write_if_changed(p, "\n".join(L) + "\n")
    return True


def nav_gc_deps():
    """game.gp deps of a level's -nav.gc (the lookup it calls)."""
    return '"tfl-nav-mesh"' if tfl_nav_present() else '"lt-nav-mesh"'


def collect_nav_mesh_geometry(scene, level_name):
    """Collect geometry tagged og_navmesh=True for future navmesh generation.

    Full navmesh injection into the level BSP is not yet implemented in the
    OpenGOAL custom level pipeline (Entity.cpp writes a null pointer for the
    nav-mesh field).  This function gathers the data so it's ready when
    engine-side support lands.
    """
    tris = []
    for o in _level_objects(scene):
        if not (o.type == "MESH" and o.get("og_navmesh", False)):
            continue
        mesh = o.data
        mat  = o.matrix_world
        verts = [mat @ v.co for v in mesh.vertices]
        mesh.calc_loop_triangles()
        for tri in mesh.loop_triangles:
            a, b, c = [verts[tri.vertices[i]] for i in range(3)]
            tris.append((
                (round(a.x,4), round(a.z,4), round(-a.y,4)),
                (round(b.x,4), round(b.z,4), round(-b.y,4)),
                (round(c.x,4), round(c.z,4), round(-c.y,4)),
            ))
    log(f"[navmesh] collected {len(tris)} tris from '{level_name}' "
        f"(injection pending engine support)")
    return tris
