# export/includes.py — OpenGOAL Level Tools
# "Always include" content for a level: one JSONC text datablock (Blender
# Text Editor) picked in Level > Settings. Everything in it is ADDED to what
# the .blend's own actors produce, for edge cases the database doesn't cover.
#
# Keys (all optional):
#   gd            files added to the level .gd / DGO   ("my-code.o", "thing-ag.go")
#   json_ag       art groups added to the .jsonc "art_groups"  ("thing-ag")
#   json_texture  entries added to the .jsonc "textures"       ("tpage-name" or ["tpage", "tex", ...])
#   goal_src      game.gp (goal-src ...) lines for the level's own code
#                 ("levels/my-level/my-code.gc" or ["file.gc", "dep"])
#   actors        actor objects copied as-is into the .jsonc "actors"
#   ambients      ambient objects copied as-is into the .jsonc "ambients"
#   cameras       built-in camera objects copied as-is into the .jsonc "cameras"
#                 (OpenGOAL v0.3.4+)
#
# level-info.gc and game.gp entries of OTHER levels are never touched by an
# export (each level only replaces its own block), so there are no keys for
# those files.

import json
import re

import bpy

KEYS = ("gd", "json_ag", "json_texture", "goal_src", "actors", "ambients", "cameras")

TEMPLATE = """// Always-included content for this level (OpenGOAL Level Tools).
// Everything here is ADDED to what the actors in the .blend already need.
// JSONC: // comments and trailing commas are fine. Delete what you don't use.
{
  // Files added to the level's .gd (DGO): code .o files and art groups (-ag.go)
  "gd": [
    // "my-code.o",
    // "some-art-ag.go",
  ],
  // Art groups added to the level .jsonc "art_groups" (no .go)
  "json_ag": [
    // "some-art-ag",
  ],
  // Textures added to the level .jsonc "textures": a tpage name, or [tpage, texture, ...]
  "json_texture": [
    // "some-texture-name",
  ],
  // game.gp (goal-src ...) lines for this level's own code: path, or [path, dependency]
  "goal_src": [
    // ["levels/my-level/my-code.gc", "process-drawable"],
  ],
  // Actors copied as-is into the level .jsonc (game coordinates, metres)
  "actors": [
    // {
    //   "trans": [0.0, 2.0, 0.0], "etype": "eco-blue", "game_task": "(game-task none)",
    //   "quat": [0.0, 0.0, 0.0, 1.0], "vis_id": 0, "bsphere": [0.0, 2.0, 0.0, 10.0],
    //   "lump": {"name": "included-eco-blue-0"}
    // },
  ],
  // Ambients copied as-is into the level .jsonc
  "ambients": [
    // {
    //   "trans": [0.0, 2.0, 0.0, 10.0], "bsphere": [0.0, 2.0, 0.0, 15.0],
    //   "lump": {"name": "included-ambient-0", "type": "'hint", "text-id": ["enum-uint32", "(text-id fuel-cell)"], "play-mode": "'notice"}
    // },
  ],
  // Built-in cameras copied as-is into the level .jsonc (OpenGOAL v0.3.4+)
  "cameras": [
    // {
    //   "trans": [17.26, 9.0, 13.2], "quat": [0, 1, 0, 0],
    //   "lump": {
    //     "name": "included-cam-0",
    //     "flags": ["enum-uint32", "(cam-slave-options SAME_SIDE)"],
    //     "pivot": ["vector3m", [15.0761, 2.6482, 25.548]],
    //     "interpTime": ["float", 1.0],
    //     // volume planes [nx, ny, nz, d] — Jak inside all of them = camera active
    //     "vol": ["vector-vol@0", [-0.09, 0.03, 0.996, 32.5], [-0.996, 0.007, -0.09, -8.7]]
    //   }
    // },
  ]
}
"""

_EMPTY = {k: [] for k in KEYS}


def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments outside strings, then trailing commas."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1]); i += 2; continue
            if c == '"':
                in_str = False
            i += 1; continue
        if c == '"':
            in_str = True; out.append(c); i += 1; continue
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            # keep line count so error line numbers stay right
            out.append("\n" * text.count("\n", i, n if j < 0 else j))
            i = n if j < 0 else j + 2
            continue
        out.append(c); i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def parse(text: str) -> tuple[dict, list[str]]:
    """Parse + normalise an include text. Returns (data, errors); data always
    has every key (lists), errors are human-readable."""
    data = {k: [] for k in KEYS}
    errors = []
    if not text.strip():
        return data, errors
    try:
        raw = json.loads(strip_jsonc(text))
    except json.JSONDecodeError as e:
        return data, [f"JSON error line {e.lineno}: {e.msg}"]
    if not isinstance(raw, dict):
        return data, ["Top level must be { ... }"]
    for k in raw:
        if k not in KEYS:
            errors.append(f"Unknown key '{k}' (ignored)")

    def _strs(key):
        out = []
        for v in raw.get(key) or []:
            if isinstance(v, str) and v.strip():
                out.append(v.strip())
            else:
                errors.append(f"'{key}': {v!r} is not a file name")
        return out

    data["gd"] = _strs("gd")
    data["json_ag"] = [s[:-3] if s.endswith(".go") else s for s in _strs("json_ag")]
    for v in raw.get("json_texture") or []:
        if isinstance(v, str) and v.strip():
            data["json_texture"].append([v.strip()])
        elif isinstance(v, list) and v and all(isinstance(x, str) for x in v):
            data["json_texture"].append(list(v))
        else:
            errors.append(f"'json_texture': {v!r} must be a name or [tpage, texture, ...]")
    for v in raw.get("goal_src") or []:
        if isinstance(v, str) and v.strip():
            data["goal_src"].append((v.strip(), "process-drawable"))
        elif isinstance(v, list) and len(v) == 2 and all(isinstance(x, str) for x in v):
            data["goal_src"].append((v[0].strip(), v[1].strip()))
        else:
            errors.append(f"'goal_src': {v!r} must be a path or [path, dependency]")
    for key in ("actors", "ambients", "cameras"):
        for i, v in enumerate(raw.get(key) or []):
            if not isinstance(v, dict):
                errors.append(f"'{key}' #{i}: must be an object {{...}}"); continue
            missing = [f for f in (("trans", "etype") if key == "actors" else ("trans",)) if f not in v]
            if missing:
                errors.append(f"'{key}' #{i}: missing {', '.join(missing)}"); continue
            data[key].append(v)
    return data, errors


# ── Scene access ────────────────────────────────────────────────────────────

def include_text(scene):
    """The level's include Text datablock, or None (feature off / not set)."""
    from ..collections import _get_level_prop
    if not bool(_get_level_prop(scene, "og_include_enabled", False)):
        return None
    name = str(_get_level_prop(scene, "og_include_text", "") or "")
    return bpy.data.texts.get(name) if name else None


def load(scene) -> tuple[dict, list[str]]:
    """Included content for the active level ({} lists when off/unset)."""
    if scene is None:
        return {k: [] for k in KEYS}, []
    txt = include_text(scene)
    if txt is None:
        return {k: [] for k in KEYS}, []
    return parse(txt.as_string())


def summary(data: dict) -> str:
    parts = [f"{len(data[k])} {k}" for k in KEYS if data.get(k)]
    return ", ".join(parts) if parts else "nothing to include yet"
