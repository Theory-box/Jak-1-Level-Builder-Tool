# ───────────────────────────────────────────────────────────────────────
# export/path_modes.py — OpenGOAL Level Tools
#
# Path modes: turn an actor's path sources (waypoint empties / curves) into
# the `path` control points and, for curve-control actors, the `path-k` knot
# vector.
#
# How the engine reads a curve (geometry.gc curve-evaluate!): cubic B-spline,
# num-knots = num-cverts + 4, and the input t (0..1) is scaled by the LAST knot
# and clamped to [first knot, last knot]. So only knots[0] and knots[-1] set
# the usable range — which is what lets an unclamped uniform spline work: set
# knots[0] = knots[3] and knots[-1] = knots[-4] and the range starts/ends where
# the curve is fully defined.
#
# Modes (Kuitar's ToDo "Expending paths for more features/control"):
#   LINEAR               points as-is, no path-k
#   LINEAR_LOOP          + first point again at the end
#   SMOOTH               uniform (unclamped) cubic; doesn't touch the ends
#   SMOOTH_LOOP          + first 3 points repeated -> seamless closed loop
#   SMOOTH_CLAMPED       clamped cubic; starts/ends exactly on the end points
#                        (this was the old "Smooth")
#   SMOOTH_CLAMPED_LOOP  + first point again at the end
#   BEZIER               each anchor-handle-handle-anchor segment is its own
#                        clamped cubic -> passes through every anchor, sharp
#                        corners allowed (knots 0000 1111 2222 ...)
#   BEZIER_LOOP          + closing segment from the last anchor to the first
#   AUTO                 picked from the sources (see auto_mode)
#
# Pure module (no bpy) except gather_sources(), so the maths is unit-testable.
# ───────────────────────────────────────────────────────────────────────
from __future__ import annotations

MAX_CVERTS = 256           # engine clamps cverts (res.gc) but not knots

CURVE_MODES = {"SMOOTH", "SMOOTH_LOOP", "SMOOTH_CLAMPED", "SMOOTH_CLAMPED_LOOP",
               "BEZIER", "BEZIER_LOOP"}

MODE_LABELS = {
    "AUTO": "Automatic",
    "LINEAR": "Linear",
    "LINEAR_LOOP": "Linear (Looped)",
    "SMOOTH": "Smooth",
    "SMOOTH_LOOP": "Smooth (Looped)",
    "SMOOTH_CLAMPED": "Smooth Clamped",
    "SMOOTH_CLAMPED_LOOP": "Smooth Clamped (Looped)",
    "BEZIER": "Bezier (Sharp Corners)",
    "BEZIER_LOOP": "Bezier (Looped)",
}


# EnumProperty items for every path-mode prop (main path + extra paths). The
# numbers are fixed: 0 = Linear and 1 = the old "Smooth" (clamped) keep files
# saved before the expanded list on the same setting.
MODE_ITEMS = [
    ("AUTO", MODE_LABELS["AUTO"],
     "Pick from the path: waypoints = Linear; Poly curve = Linear (Looped if cyclic); "
     "NURBS = Smooth / Smooth Clamped (Endpoint), Looped if cyclic; Bezier = Bezier (Looped if cyclic)", 2),
    ("LINEAR", MODE_LABELS["LINEAR"], "Straight segments through every point (no path-k)", 0),
    ("LINEAR_LOOP", MODE_LABELS["LINEAR_LOOP"], "Linear, plus the first point again at the end", 3),
    ("SMOOTH", MODE_LABELS["SMOOTH"],
     "Uniform cubic B-spline — smooth, doesn't reach the first/last points. Needs 4+ points", 4),
    ("SMOOTH_LOOP", MODE_LABELS["SMOOTH_LOOP"], "Smooth closed loop (first 3 points repeated)", 5),
    ("SMOOTH_CLAMPED", MODE_LABELS["SMOOTH_CLAMPED"],
     "Cubic B-spline that starts and ends exactly on the end points. Needs 4+ points", 1),
    ("SMOOTH_CLAMPED_LOOP", MODE_LABELS["SMOOTH_CLAMPED_LOOP"], "Smooth Clamped, plus the first point again", 6),
    ("BEZIER", MODE_LABELS["BEZIER"],
     "One Bezier curve: passes through every anchor, handles shape each segment, sharp corners allowed", 7),
    ("BEZIER_LOOP", MODE_LABELS["BEZIER_LOOP"], "Bezier with a closing segment back to the first anchor", 8),
]

# Path lump names the engine reads (battlecontroller: path + patha..pathh +
# pathspawn; swamp-bat: path + pathb). Knots are always "<name>-k".
STANDARD_PATH_NAMES = ["path", "patha", "pathb", "pathc", "pathd", "pathe", "pathf",
                       "pathg", "pathh", "pathspawn"]


def keyframe_suffix(text) -> str:
    """Lump type suffix for a path keyframe: "" for blank (default res time),
    else "@<float>" (build_level reads e.g. "vector4m@1.0"). Invalid -> ""."""
    t = str(text or "").strip()
    if not t:
        return ""
    try:
        return "@" + repr(float(t))
    except ValueError:
        return ""


# ── Knot vectors ────────────────────────────────────────────────────────────

def knots_clamped(n: int) -> list[float]:
    """Clamped uniform cubic: [0,0,0,0, 1..n-4, n-3 x4]. n >= 4."""
    return [0.0] * 4 + [float(i) for i in range(1, n - 3)] + [float(n - 3)] * 4


def knots_uniform(n: int) -> list[float]:
    """Unclamped uniform cubic with the range pinned to the fully defined part:
    u_i = i - 3 for i in 0..n+3, then u[0] = u[3] and u[-1] = u[-4].
    8 points -> [0,-2,-1,0,1,2,3,4,5,6,7,5] (Kuitar's example). n >= 4."""
    u = [float(i - 3) for i in range(n + 4)]
    u[0] = u[3]
    u[-1] = u[-4]
    return u


def knots_bezier(segments: int) -> list[float]:
    """Piecewise cubic Bezier: each segment value repeated 4 times, 0..segments.
    3 segments (12 points) -> 0000 1111 2222 3333 (16 knots)."""
    return [float(v) for v in range(segments + 1) for _ in range(4)]


def resize_knots(vals, need: int) -> list[float]:
    """Fit a manual knot list to `need` values (cverts + 4) after points were
    added or removed: keeps the leading values and the last 4 (the end
    clamp), dropping or inserting values just before them (+1 steps)."""
    vals = [float(v) for v in vals]
    if need <= 0:
        return []
    if len(vals) == need:
        return vals
    if len(vals) < 4:
        return knots_clamped(max(need - 4, 4))[:need]
    head, tail = vals[:-4], vals[-4:]
    if len(vals) > need:
        return head[:need - 4] + tail
    add = need - len(vals)
    last = head[-1] if head else tail[0]
    return head + [last + i + 1 for i in range(add)] + [t + add for t in tail]


def manual_knots(auto_knots, manual_vals) -> tuple[list[float] | None, str]:
    """Knots to export when the user edits them by hand: the manual list,
    resized to the curve's current knot count if points changed. Returns
    (knots, note); knots is None when the path has no knots (linear)."""
    if not auto_knots:
        return None, ""
    need = len(auto_knots)
    vals = [float(v) for v in manual_vals]
    note = ""
    if len(vals) != need:
        note = f"manual knots resized {len(vals)} -> {need} (points changed — Fit to keep it)"
        vals = resize_knots(vals, need)
    if any(b < a for a, b in zip(vals, vals[1:])):
        note = (note + "; " if note else "") + "knots must never decrease"
    return vals, note


def knot_presets(n_cverts: int, auto_knots) -> dict:
    """Preset knot lists for the manual editor."""
    out = {"AUTO": list(auto_knots or [])}
    if n_cverts >= 4:
        out["CLAMPED"] = knots_clamped(n_cverts)
        out["UNIFORM"] = knots_uniform(n_cverts)
    return out


# ── Automatic mode ──────────────────────────────────────────────────────────

def auto_mode(sources: list[dict]) -> str:
    """Pick a mode from the path sources (rules from Kuitar's ToDo):
    waypoints or several sources -> Linear; one curve -> by its type:
      POLY:   cyclic -> Linear (Looped), else Linear
      NURBS:  cyclic/endpoint -> the four Smooth variants
      BEZIER: cyclic -> Bezier (Looped), else Bezier
    """
    if len(sources) != 1 or sources[0]["kind"] != "curve":
        return "LINEAR"
    s = sources[0]
    t, cyc, end = s.get("type"), s.get("cyclic", False), s.get("endpoint", False)
    if t == "POLY":
        return "LINEAR_LOOP" if cyc else "LINEAR"
    if t == "NURBS":
        if end:
            return "SMOOTH_CLAMPED_LOOP" if cyc else "SMOOTH_CLAMPED"
        return "SMOOTH_LOOP" if cyc else "SMOOTH"
    if t == "BEZIER":
        return "BEZIER_LOOP" if cyc else "BEZIER"
    return "LINEAR"


# ── Build ───────────────────────────────────────────────────────────────────

def _anchors(sources):
    """Every source's main points in order (waypoints, curve control points /
    Bezier anchors) — the linear reading of the path."""
    pts = []
    for s in sources:
        if s["kind"] == "point":
            pts.append(s["co"])
        else:
            pts.extend(s["points"])
    return pts


def build(sources: list[dict], mode: str, linear_only: bool = False):
    """-> (points, knots_or_None, effective_mode, warning_or_None)

    sources: [{"kind": "point", "co": (x,y,z)}
              | {"kind": "curve", "type": "POLY"|"NURBS"|"BEZIER",
                 "cyclic": bool, "endpoint": bool, "points": [(x,y,z)...],
                 "handles": [(left, right)...]   # BEZIER only, per anchor
                }]
    Points are in whatever space the caller uses (the exporter converts).
    """
    if mode == "AUTO":
        mode = auto_mode(sources)
    warn = None
    if linear_only and mode in CURVE_MODES:
        # path-control actor: it ignores path-k, so only the anchors matter.
        mode = "LINEAR_LOOP" if mode.endswith("_LOOP") else "LINEAR"
        warn = "this actor only follows straight lines (path-control) — exported as " + MODE_LABELS[mode]

    if mode == "BEZIER" or mode == "BEZIER_LOOP":
        curve = sources[0] if (len(sources) == 1 and sources[0]["kind"] == "curve"
                               and sources[0].get("type") == "BEZIER") else None
        if curve is None:
            mode, warn = "LINEAR", "Bezier mode needs exactly one Bezier curve — exported as Linear"
        else:
            a, h = curve["points"], curve["handles"]
            n = len(a)
            seg_ends = list(range(n - 1)) + ([n - 1] if mode == "BEZIER_LOOP" and n > 1 else [])
            pts = []
            for i in seg_ends:
                j = (i + 1) % n
                pts += [a[i], h[i][1], h[j][0], a[j]]
            if not pts:
                return _anchors(sources), None, "LINEAR", "Bezier curve has fewer than 2 points — exported as Linear"
            if len(pts) > MAX_CVERTS:
                return _anchors(sources), None, "LINEAR", f"{len(pts)} points is over the engine's {MAX_CVERTS} — exported as Linear"
            return pts, knots_bezier(len(seg_ends)), mode, warn

    pts = _anchors(sources)
    if mode in ("LINEAR", "LINEAR_LOOP"):
        if mode == "LINEAR_LOOP" and len(pts) > 1:
            pts = pts + [pts[0]]
        return pts, None, mode, warn

    loop_extra = {"SMOOTH_LOOP": 3, "SMOOTH_CLAMPED_LOOP": 1}.get(mode, 0)
    if loop_extra and len(pts) >= 3:
        pts = pts + pts[:loop_extra]
    if len(pts) < 4:
        return pts, None, "LINEAR", f"{MODE_LABELS[mode]} needs 4+ points (has {len(pts)}) — exported as Linear"
    if len(pts) > MAX_CVERTS:
        return pts, None, "LINEAR", f"{len(pts)} points is over the engine's {MAX_CVERTS} — exported as Linear"
    knots = knots_uniform(len(pts)) if mode in ("SMOOTH", "SMOOTH_LOOP") else knots_clamped(len(pts))
    return pts, knots, mode, warn


def straight_bezier(points: list) -> tuple[list, list[float]]:
    """Polyline as a piecewise cubic: each segment's handles at 1/3 and 2/3, so
    the curve is exactly the straight segments. For curve-only readers (camera
    'campath' needs knots) when the chosen mode is linear."""
    pts = []
    for a, b in zip(points, points[1:]):
        h1 = tuple(a[i] + (b[i] - a[i]) / 3.0 for i in range(3))
        h2 = tuple(a[i] + (b[i] - a[i]) * 2.0 / 3.0 for i in range(3))
        pts += [a, h1, h2, b]
    return pts, knots_bezier(len(points) - 1)


# ── Blender side ────────────────────────────────────────────────────────────

def gather_sources(obj) -> list[dict]:
    """Read an object's main path (og_waypoint_sources) into build() sources,
    in Blender world space. Falls back to legacy <name>_wp_NN empties."""
    import bpy
    sources = getattr(obj, "og_waypoint_sources", None)
    if sources and len(sources) > 0:
        return gather_from(sources)
    out = []
    prefix = obj.name + "_wp_"
    # Legacy main-path empties are exactly <name>_wp_NN (extra paths use
    # <name>_wp_<lump>_NN and must not leak in here).
    for o in sorted((o for o in bpy.data.objects if o.name.startswith(prefix) and o.type == "EMPTY"
                     and o.name[len(prefix):].isdigit()),
                    key=lambda o: o.name):
        out.append({"kind": "point", "co": tuple(o.matrix_world.translation)})
    return out


def gather_from(sources) -> list[dict]:
    """Read a collection of OGWaypointSource entries (main path or an extra
    path) into build() sources."""
    import bpy
    out = []
    if sources:
        for src in sources:
            o = src.obj
            if o is None or o.name not in bpy.data.objects:
                continue
            if o.type == "EMPTY":
                out.append({"kind": "point", "co": tuple(o.matrix_world.translation)})
            elif o.type == "CURVE":
                M = o.matrix_world
                for sp in o.data.splines:
                    if sp.type == "BEZIER":
                        out.append({"kind": "curve", "type": "BEZIER", "cyclic": sp.use_cyclic_u,
                                    "endpoint": False,
                                    "points": [tuple(M @ bp.co) for bp in sp.bezier_points],
                                    "handles": [(tuple(M @ bp.handle_left), tuple(M @ bp.handle_right))
                                                for bp in sp.bezier_points]})
                    else:
                        import mathutils
                        out.append({"kind": "curve", "type": sp.type, "cyclic": sp.use_cyclic_u,
                                    "endpoint": sp.use_endpoint_u,
                                    "points": [tuple(M @ mathutils.Vector(p.co[:3])) for p in sp.points]})
    return out
