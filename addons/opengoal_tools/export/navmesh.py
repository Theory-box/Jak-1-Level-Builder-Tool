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
    NAV_UNSAFE_TYPES, NEEDS_PATH_TYPES, NEEDS_PATHB_TYPES, IS_PROP_TYPES,
    needed_tpages, LUMP_REFERENCE, ACTOR_LINK_DEFS,
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


def _navmesh_compute(world_tris):
    """
    world_tris: list of 3-tuples of (x,y,z) world-space points (already in game coords)
    Returns dict with all data needed to write the GOAL nav-mesh struct.
    """
    import math
    EPS = 0.01

    verts = []
    def find_or_add(pt):
        for i, v in enumerate(verts):
            if abs(v[0]-pt[0]) < EPS and abs(v[1]-pt[1]) < EPS and abs(v[2]-pt[2]) < EPS:
                return i
        verts.append(pt)
        return len(verts) - 1

    polys = []
    for tri in world_tris:
        i0 = find_or_add(tri[0])
        i1 = find_or_add(tri[1])
        i2 = find_or_add(tri[2])
        if len({i0, i1, i2}) == 3:
            polys.append((i0, i1, i2))

    N = len(polys)
    V = len(verts)
    if N == 0 or V == 0:
        return None

    ox = sum(v[0] for v in verts) / V
    oy = sum(v[1] for v in verts) / V
    oz = sum(v[2] for v in verts) / V
    rel = [(v[0]-ox, v[1]-oy, v[2]-oz) for v in verts]
    max_dist = max(math.sqrt(v[0]**2 + v[1]**2 + v[2]**2) for v in rel)
    bounds_r = max_dist + 5.0

    def edge_key(a, b): return (min(a,b), max(a,b))
    edge_to_polys = {}
    for pi, (v0,v1,v2) in enumerate(polys):
        for ea, eb in [(v0,v1),(v1,v2),(v2,v0)]:
            edge_to_polys.setdefault(edge_key(ea,eb), []).append(pi)

    adj = []
    for pi, (v0,v1,v2) in enumerate(polys):
        neighbors = []
        for ea, eb in [(v0,v1),(v1,v2),(v2,v0)]:
            others = [p for p in edge_to_polys.get(edge_key(ea,eb),[]) if p != pi]
            neighbors.append(others[0] if others else 0xFF)
        adj.append(tuple(neighbors))

    INF = 9999
    def bfs_from(src):
        dist = [INF] * N
        came = [None] * N
        dist[src] = 0
        q = [src]; qi = 0
        while qi < len(q):
            cur = q[qi]; qi += 1
            for slot, nb in enumerate(adj[cur]):
                if nb != 0xFF and dist[nb] == INF:
                    dist[nb] = dist[cur] + 1
                    came[nb] = (cur, slot)
                    q.append(nb)
        next_hop = [3] * N
        for dst in range(N):
            if dst == src or dist[dst] == INF:
                continue
            node = dst
            while came[node][0] != src:
                node = came[node][0]
            next_hop[dst] = came[node][1]
        return next_hop

    route_table = [bfs_from(i) for i in range(N)]
    total_bits = N * N * 2
    total_bytes = (total_bits + 7) // 8
    route_bytes = bytearray(total_bytes)
    for frm in range(N):
        for to in range(N):
            val = route_table[frm][to] & 3
            bit_idx = (frm * N + to) * 2
            byte_idx = bit_idx // 8
            bit_off = bit_idx % 8
            route_bytes[byte_idx] |= (val << bit_off)
    total_vec4ub = (total_bytes + 3) // 4
    padded = route_bytes + bytearray(total_vec4ub * 4 - len(route_bytes))
    vec4ubs = [tuple(padded[i*4:(i+1)*4]) for i in range(total_vec4ub)]

    # Build BVH nodes — required by find-poly-fast (called during enemy chase).
    # Without nodes, recursive-inside-poly dereferences null -> crash.
    # For small meshes we use a simple flat structure:
    # One root node per group of <=4 polys, so ceil(N/4) leaf nodes,
    # plus one branch node if more than one leaf.
    # For our typical small meshes (2-16 polys) one leaf node is enough.
    # Leaf node: type != 0, num-tris stored in low 16 bits of left-offset field.
    # first-tris: up to 4 poly indices packed in 4 uint8 slots.
    # last-tris:  next 4 poly indices (for polys 5-8).
    # center/radius: AABB of all verts in the node (in local/rel coords).
    import math as _math

    # Compute AABB of all relative verts for the node bounding box
    xs = [v[0] for v in rel]; ys = [v[1] for v in rel]; zs = [v[2] for v in rel]
    cx = (_math.fsum(xs)) / V
    cy = (_math.fsum(ys)) / V
    cz = (_math.fsum(zs)) / V
    rx = max(abs(x - cx) for x in xs) + 1.0  # 1m padding
    ry = max(abs(y - cy) for y in ys) + 5.0  # extra Y padding for height tolerance
    rz = max(abs(z - cz) for z in zs) + 1.0

    # Build flat list of leaf nodes — one per group of 4 polys
    # Each leaf: (cx, cy, cz, rx, ry, rz, [poly_idx...])
    nodes = []
    for start in range(0, N, 4):
        chunk = list(range(start, min(start+4, N)))
        # AABB for this chunk's verts
        chunk_verts = []
        for pi in chunk:
            for vi in polys[pi]:
                chunk_verts.append(rel[vi])
        if chunk_verts:
            cxs = [v[0] for v in chunk_verts]
            cys = [v[1] for v in chunk_verts]
            czs = [v[2] for v in chunk_verts]
            ncx = (_math.fsum(cxs)) / len(cxs)
            ncy = (_math.fsum(cys)) / len(cys)
            ncz = (_math.fsum(czs)) / len(czs)
            nrx = max(abs(x - ncx) for x in cxs) + 1.0
            nry = max(abs(y - ncy) for y in cys) + 5.0
            nrz = max(abs(z - ncz) for z in czs) + 1.0
        else:
            ncx, ncy, ncz, nrx, nry, nrz = cx, cy, cz, rx, ry, rz
        nodes.append((ncx, ncy, ncz, nrx, nry, nrz, chunk))

    return {
        'origin': (ox, oy, oz), 'bounds_r': bounds_r,
        'verts_rel': rel, 'polys': polys, 'adj': adj,
        'vec4ubs': vec4ubs, 'poly_count': N, 'vertex_count': V,
        'nodes': nodes,
        'node_aabb': (cx, cy, cz, rx, ry, rz),
    }

def _navmesh_to_goal(mesh, actor_aid):
    ox, oy, oz = mesh['origin']
    br = mesh['bounds_r']
    N = mesh['poly_count']
    V = mesh['vertex_count']

    def gx(n):
        """Format integer as GOAL hex literal: #x0, #xff, #x1a etc."""
        return f"#x{n:x}"

    def gadj(n):
        """Format adjacency index — #xff for boundary, else #xNN."""
        return "#xff" if n == 0xFF else f"#x{n:x}"

    L = []
    L.append(f"    (({actor_aid})")
    L.append(f"      (set! (-> this nav-mesh)")
    L.append(f"        (new 'static 'nav-mesh")
    L.append(f"          :bounds (new 'static 'sphere :x (meters {ox:.4f}) :y (meters {oy:.4f}) :z (meters {oz:.4f}) :w (meters {br:.4f}))")
    L.append(f"          :origin (new 'static 'vector :x (meters {ox:.4f}) :y (meters {oy:.4f}) :z (meters {oz:.4f}) :w 1.0)")
    node_list = mesh.get('nodes', [])
    L.append(f"          :node-count {len(node_list)}")
    L.append(f"          :nodes (new 'static 'inline-array nav-node {len(node_list)}")
    for ncx, ncy, ncz, nrx, nry, nrz, chunk in node_list:
        # Leaf node: type=1, num-tris in lower 16 of left-offset field
        # first-tris: poly indices 0-3, last-tris: poly indices 4-7
        ft = chunk[:4] + [0] * (4 - len(chunk[:4]))
        lt = (chunk[4:8] if len(chunk) > 4 else []) + [0] * (4 - len(chunk[4:8]) if len(chunk) > 4 else 4)
        L.append(f"            (new 'static 'nav-node")
        L.append(f"              :center-x (meters {ncx:.4f}) :center-y (meters {ncy:.4f}) :center-z (meters {ncz:.4f})")
        L.append(f"              :type #x1 :parent-offset #x0")
        L.append(f"              :radius-x (meters {nrx:.4f}) :radius-y (meters {nry:.4f}) :radius-z (meters {nrz:.4f})")
        L.append(f"              :num-tris {len(chunk)}")
        L.append(f"              :first-tris (new 'static 'array uint8 4 {gx(ft[0])} {gx(ft[1])} {gx(ft[2])} {gx(ft[3])})")
        L.append(f"              :last-tris  (new 'static 'array uint8 4 {gx(lt[0])} {gx(lt[1])} {gx(lt[2])} {gx(lt[3])})")
        L.append(f"            )")
    L.append(f"          )")
    L.append(f"          :vertex-count {V}")
    L.append(f"          :vertex (new 'static 'inline-array nav-vertex {V}")
    for vx, vy, vz in mesh['verts_rel']:
        L.append(f"            (new 'static 'nav-vertex :x (meters {vx:.4f}) :y (meters {vy:.4f}) :z (meters {vz:.4f}) :w 1.0)")
    L.append(f"          )")
    L.append(f"          :poly-count {N}")
    L.append(f"          :poly (new 'static 'inline-array nav-poly {N}")
    for i, ((v0,v1,v2),(a0,a1,a2)) in enumerate(zip(mesh['polys'], mesh['adj'])):
        L.append(f"            (new 'static 'nav-poly :id {gx(i)} :vertex (new 'static 'array uint8 3 {gx(v0)} {gx(v1)} {gx(v2)}) :adj-poly (new 'static 'array uint8 3 {gadj(a0)} {gadj(a1)} {gadj(a2)}))")
    L.append(f"          )")
    rc = len(mesh['vec4ubs'])
    L.append(f"          :route (new 'static 'inline-array vector4ub {rc}")
    for b0,b1,b2,b3 in mesh['vec4ubs']:
        L.append(f"            (new 'static 'vector4ub :data (new 'static 'array uint8 4 {gx(b0)} {gx(b1)} {gx(b2)} {gx(b3)}))")
    L.append(f"          )")
    L.append(f"        )")
    L.append(f"      )")
    L.append(f"    )")
    return "\n".join(L)

def _collect_navmesh_actors(scene):
    """
    Returns list of (actor_aid, mesh_data) for actors linked to navmeshes.
    actor_aid = base_id + 1-based index in canonical actor order,
    matching exactly what collect_actors and the JSONC builder assign.
    """
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

        nm_obj.data.calc_loop_triangles()
        mat = nm_obj.matrix_world
        tris = []
        for tri in nm_obj.data.loop_triangles:
            pts = []
            for vi in tri.vertices:
                co = mat @ nm_obj.data.vertices[vi].co
                # Blender Y-up -> game coords: game_x=bl_x, game_y=bl_z, game_z=-bl_y
                pts.append((round(co.x, 4), round(co.z, 4), round(-co.y, 4)))
            tris.append(tuple(pts))

        mesh_data = _navmesh_compute(tris)
        if mesh_data:
            result.append((actor_aid, mesh_data))
            log(f"[navmesh]   {mesh_data['poly_count']} polys OK")
        else:
            log(f"[navmesh]   WARNING: navmesh compute returned nothing for {o.name}")

    return result

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
