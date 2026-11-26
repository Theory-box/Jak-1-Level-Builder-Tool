"""Custom ocean maps (Oceans panel) -> GOAL ocean-map data.

Per map (oceans.py, the grid mesh): the game's tables, built like vanilla's (ocean-tables.gc):
- spheres: 36, one per 768 m square (its centre, radius 384 m x sqrt 2)
- colors: 49 x 49 grid points (row stride 52), from the OceanColor attribute (game bytes: 128 = full)
- mid-masks: a shared pool of 8 x 8 bit masks (row = z, bit = x; 1 = no ocean), entry 0 all zeros
- mid-indices: per square, its mask (0: all water, #xffff: no water at all)
- trans-indices: per 96 m cell, (0, 0) = all of it (water) or (-1, -1) (no water)
- near-indices: one entry, all zeros (whole cells: edges at 96 m)
Water or colour can come from a game map instead (its tables are used as they are).
"Always loaded" maps go in goal_src/jak1/levels/level-tools/lt-oceans-<group>.gc (GAME.CGO, like the
moods); "with its levels" maps go in the -obs.gc of each level using them (level_lines).
Game axes: Blender (x, y) -> game (x, -y); 1 m = 4096 units.
"""
from __future__ import annotations

from .paths import _goal_src, log
from .fileio import write_if_changed

M = 4096.0
TILE = 8                     # cells per square side
SQUARES = 6


def _f(x):
    s = f"{float(x):.4f}".rstrip("0")
    return s + "0" if s.endswith(".") else s


def start_corner(o):
    """(x, z) of the grid's corner in game units, from the grid mesh's centre."""
    from ..oceans import HALF
    g = o.grid
    cx, cy = (g.matrix_world.translation.x, g.matrix_world.translation.y) if g is not None else (0.0, 0.0)
    return ((cx - HALF) * M, (-cy - HALF) * M)


def water_cells(o):
    """48 x 48 [row z][col x] booleans from the grid mesh's materials (game axes)."""
    from ..oceans import CELL, CELLS, HALF
    w = [[True] * CELLS for _ in range(CELLS)]
    g = o.grid
    if g is None:
        return w
    if g.mode == "EDIT":
        g.update_from_editmode()                         # the faces as they are now
    mw = g.matrix_world
    ox, oy = mw.translation.x, mw.translation.y
    mats = g.data.materials
    for f in g.data.polygons:
        c = mw @ f.center
        col = int((c.x - ox + HALF) // CELL)
        row = int((-(c.y - oy) + HALF) // CELL)          # game z = -Blender y
        if 0 <= col < CELLS and 0 <= row < CELLS:
            m = mats[f.material_index] if f.material_index < len(mats) else None
            w[row][col] = not (m is not None and m.name.startswith("OG Ocean No Water"))
    return w


def mask_tables(w):
    """(pool of 64-bit masks, 36 mid indices) from the water cells."""
    pool, index, mids = [0], {0: 0}, []
    for t in range(SQUARES * SQUARES):
        tz, tx = divmod(t, SQUARES)
        mask = 0
        for rz in range(TILE):
            for cx in range(TILE):
                if not w[tz * TILE + rz][tx * TILE + cx]:
                    mask |= 1 << (rz * 8 + cx)
        if mask == (1 << 64) - 1:
            mids.append(0xFFFF)                      # no water in the whole square
            continue
        if mask not in index:
            index[mask] = len(pool)
            pool.append(mask)
        mids.append(index[mask])
    return pool, mids


def point_colors(o):
    """49 x 49 rgba bytes [row z][col x] from the OceanColor attribute (far colour if missing)."""
    from ..oceans import CELL, CELLS, HALF, COLOR_ATTR
    n = CELLS + 1
    fc = tuple(int(round(c * 255)) for c in o.far_color)
    out = [[fc] * n for _ in range(n)]
    g = o.grid
    if g is None:
        return out
    ca = g.data.color_attributes.get(COLOR_ATTR)
    if ca is None or ca.domain != "POINT":
        return out
    mw = g.matrix_world
    ox, oy = mw.translation.x, mw.translation.y
    for v, d in zip(g.data.vertices, ca.data):
        p = mw @ v.co
        col = int(round((p.x - ox + HALF) / CELL))
        row = int(round((-(p.y - oy) + HALF) / CELL))
        if 0 <= col < n and 0 <= row < n:
            c = d.color_srgb
            out[row][col] = tuple(max(0, min(255, int(round(c[k] * 255)))) for k in range(3))
    return out


def ocean_gc(o):
    from ..oceans import clean, CELLS
    n = clean(o.name)
    sx, sz = start_corner(o)
    out = ["", f";; ---- ocean map *{n}-ocean-map* ----"]
    # spheres: one per square
    out += [f"(define *{n}-ocean-spheres*", "  (new 'static 'ocean-spheres :spheres",
            "    (new 'static 'inline-array sphere 36"]
    for t in range(36):
        tz, tx = divmod(t, SQUARES)
        out.append(f"      (new 'static 'sphere :x {_f(sx + (384 + 768 * tx) * M)} :z {_f(sz + (384 + 768 * tz) * M)} :w 2224365.5)")
    out[-1] += ")))"
    syms = {"spheres": f"*{n}-ocean-spheres*"}
    if o.color_from == "own":
        pc = point_colors(o)
        out += [f"(define *{n}-ocean-colors*", "  (new 'static 'ocean-colors :colors",
                "    (new 'static 'array rgba 2548"]
        for row in range(CELLS + 1):
            r = pc[row] + [pc[row][-1]] * 3                  # 49 points + 3 padding (stride 52)
            for c in r:
                out.append(f"      (new 'static 'rgba :r #x{c[0]:x} :g #x{c[1]:x} :b #x{c[2]:x} :a #x80)")
        out[-1] += ")))"
        syms["colors"] = f"*{n}-ocean-colors*"
    else:
        syms["colors"] = f"*ocean-colors-{o.color_from}*"
    if o.water_from == "own":
        w = water_cells(o)
        pool, mids = mask_tables(w)
        out += [f"(define *{n}-ocean-mid-masks*", "  (new 'static 'ocean-mid-masks :data",
                f"    (new 'static 'inline-array ocean-mid-mask {len(pool)}"]
        out += ["      (new 'static 'ocean-mid-mask)" if m == 0 else f"      (new 'static 'ocean-mid-mask :dword #x{m:x})"
                for m in pool]
        out[-1] += ")))"
        out += [f"(define *{n}-ocean-mid-indices*", "  (new 'static 'ocean-mid-indices :data",
                "    (new 'static 'array uint16 36"]
        out += [f"      #x{v:x}" for v in mids]
        out[-1] += ")))"
        out += [f"(define *{n}-ocean-trans-indices*", "  (new 'static 'ocean-trans-indices :data",
                "    (new 'static 'inline-array ocean-trans-index 2304"]
        out += ["      (new 'static 'ocean-trans-index)" if w[z][x] else "      (new 'static 'ocean-trans-index :parent -1 :child -1)"
                for z in range(CELLS) for x in range(CELLS)]
        out[-1] += ")))"
        out += [f"(define *{n}-ocean-near-indices*", "  (new 'static 'ocean-near-indices :data",
                "    (new 'static 'inline-array ocean-near-index 1 (new 'static 'ocean-near-index))))"]
        for k in ("mid-masks", "mid-indices", "trans-indices", "near-indices"):
            syms[k] = f"*{n}-ocean-{k}*"
    else:
        for k in ("mid-masks", "mid-indices", "trans-indices", "near-indices"):
            syms[k] = f"*ocean-{k}-{o.water_from}*"
    fc = [c * 255 for c in o.far_color]
    out += [f"(define *{n}-ocean-map*",
            f"  (new 'static 'ocean-map :start-corner (new 'static 'vector :x {_f(sx)} :z {_f(sz)} :w 1.0)",
            f"                          :far-color (new 'static 'vector :x {_f(fc[0])} :y {_f(fc[1])} :z {_f(fc[2])})))"]
    for k in ("spheres", "colors", "mid-masks", "mid-indices", "trans-indices", "near-indices"):
        out.append(f"(set! (-> *{n}-ocean-map* ocean-{k}) {syms[k]})")
    return out


def _header(name):
    return [";;-*-Lisp-*-", "(in-package goal)",
            f";; {name}.gc -- written by OpenGOAL Level Tools from the .blend's ocean maps (Oceans panel)."]


def export_oceans(scene):
    """Write this .blend's always-loaded ocean maps (only what changed). Returns problems or []."""
    from .. import oceans as O
    from ..moods import group_name
    from .moods_export import LT_DIR, _register, _unregister
    errs = [f"ocean {i + 1}: {t}" for i, t in O.problems(scene) if not t.startswith("grey:")]
    if errs:
        for e in errs:
            log(f"[oceans] {e}")
        return errs
    name = f"lt-oceans-{group_name(scene)}"
    maps = [o for o in scene.og_oceans if o.export and o.place == "game"]
    if not maps:
        if (_goal_src() / LT_DIR / f"{name}.gc").exists():
            _unregister(name)
        return []
    lines = _header(name)
    for o in maps:
        lines += ocean_gc(o)
    write_if_changed(_goal_src() / LT_DIR / f"{name}.gc", "\n".join(lines) + "\n")
    _register(name, "ocean-tables")
    log(f"[oceans] {name}: {len(maps)} map(s)")
    return []


def level_lines(scene, col):
    """GOAL for the level's -obs.gc: its ocean map when it is a "with its levels" one."""
    from .. import oceans as O
    o = O.level_ocean(scene, col)
    if o is None or not o.export or o.place != "level":
        return []
    return ocean_gc(o)
