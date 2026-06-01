# ───────────────────────────────────────────────────────────────────────
# export/schema_emit.py — OpenGOAL Level Tools
#
# Schema-driven lump emission. Given an actor's `fields[]` schema (from the
# game DB) and a getter for the object's og_* properties, build the lump dict
# directly from the schema — no per-actor code path, no hardcoded gates.
#
# Supported field shapes (keys live in field["lump"] unless noted):
#   key, type                    — target lump + element type
#   slot: N                      — array element index (sync[0..3], delay[0,1])
#   bit:  N                      — OR-accumulate constant N into a uint32 bitfield
#   const: V        (on field)   — emit a constant value, ignore the prop
#   scale: F        (on field)   — multiply numeric value by F before encoding
#   value_if_true: V (on field)  — value to use when a bool/flag prop is set
# Field-level: key (og_ prop), type, default, write_if, scale, const, value_if_true
# write_if: always | if_true | if_nonzero | if_set | if_not_default
#
# Pure module: no Blender imports, so it is unit-testable standalone.
# ───────────────────────────────────────────────────────────────────────
from __future__ import annotations

_NUMERIC = ("float", "meters", "degrees", "vector3m", "vector4m", "vector",
            "vector-vol", "movie-pos")
_INT = ("int32", "uint32", "mode")


def _should_write(value, rule, default):
    if rule == "always":
        return True
    if rule == "if_true":
        return bool(value)
    if rule == "if_nonzero":
        return value not in (0, 0.0, None, False, "")
    if rule == "if_set":
        return value not in (None, "")
    if rule == "if_not_default":
        return value != default
    return True  # unknown -> write, never silently drop


def _coerce(lump_type, value):
    if value is None:
        value = 0
    if lump_type in _NUMERIC:
        return float(value)
    if lump_type in _INT:
        return int(value)
    if lump_type == "bool":
        return int(bool(value))
    return value  # symbol/string/type/enum-*/cell-info/buzzer-info -> passthrough


def emit_schema_lumps(get, fields):
    groups = {}  # lump_key -> dict(type, mode, slots/scalar/bits, any)
    for f in fields:
        lp = f.get("lump")
        if not isinstance(lp, dict) or not lp.get("key"):
            continue
        key = lp["key"]
        ltype = lp.get("type", f.get("type", "float"))
        default = f.get("default")

        if "const" in f:
            value, wrote = f["const"], True
        else:
            raw = get(f.get("key"), default)
            wrote = _should_write(raw, f.get("write_if", "always"), default)
            if "value_if_true" in f and raw:
                value = f["value_if_true"]
            else:
                value = raw if wrote else default
            if f.get("scale") is not None and isinstance(value, (int, float)):
                value = value * f["scale"]
            if f.get("format") and wrote:
                value = f["format"].format(value)

        g = groups.setdefault(key, {"type": ltype, "slots": {}, "any": False})
        slot = lp.get("slot")
        bit = lp.get("bit")
        if slot is not None:
            g["mode"] = "array"
            g["slots"][slot] = (value, wrote)
        elif bit is not None or ("value_if_true" in f and ltype in _INT):
            g["mode"] = "bits"
            contrib = bit if bit is not None else value
            g.setdefault("bits", []).append((contrib, wrote))
        else:
            g["mode"] = "scalar"
            g["scalar"] = (value, wrote)
        if wrote:
            g["any"] = True

    result = {}
    for key, g in groups.items():
        if not g["any"]:
            continue
        t = g["type"]
        mode = g.get("mode", "scalar")
        if mode == "array":
            n = max(g["slots"]) + 1
            result[key] = [t] + [_coerce(t, g["slots"].get(i, (0, False))[0]) for i in range(n)]
        elif mode == "bits":
            acc = 0
            for v, w in g["bits"]:
                if w:
                    acc |= int(v)
            result[key] = [t, acc]
        else:
            v, _w = g["scalar"]
            result[key] = [t, _coerce(t, v)]
    return result
