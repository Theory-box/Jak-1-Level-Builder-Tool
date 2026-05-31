# ───────────────────────────────────────────────────────────────────────
# export/schema_emit.py — OpenGOAL Level Tools
#
# Schema-driven lump emission. Given an actor's `fields[]` schema (from the
# game DB) and a getter for the object's og_* properties, build the lump dict
# directly from the schema — no per-actor code path, no hardcoded gates.
#
# This is the core of the "DB as single source of truth" restructure: an actor
# (including a custom one added only to the DB) emits its lumps purely from its
# declared fields, so setting a field with a value is sufficient to export it.
#
# Pure module: no Blender imports, so it is unit-testable standalone.
# ───────────────────────────────────────────────────────────────────────
from __future__ import annotations


def _should_write(value, rule, default):
    """Decide whether a field contributes to its lump, given its write_if rule."""
    if rule == "always":
        return True
    if rule == "if_true":
        return bool(value)
    if rule == "if_nonzero":
        return value not in (0, 0.0, None, False, "")
    if rule == "if_set":
        return value is not None
    if rule == "if_not_default":
        return value != default
    # Unknown rule: be conservative and write, so we never silently drop data.
    return True


def _coerce(lump_type, value):
    """Coerce a Python prop value to the JSONC lump element for its type."""
    if value is None:
        value = 0
    if lump_type in ("float", "meters", "degrees", "vector3m", "vector4m"):
        return float(value)
    if lump_type in ("int32", "uint32", "mode"):
        return int(value)
    if lump_type == "bool":
        return int(bool(value))
    # symbol / string / type / enum-* and anything else: pass through as-is
    return value


def emit_schema_lumps(get, fields):
    """Build {lump_key: [type, v0, v1, ...]} from an actor's fields[] schema.

    get(key, default) -> the object's og_* property value (e.g. obj.get).
    fields            -> list of field dicts from the DB actor record.

    Fields sharing a lump key with different `slot` indices assemble into a
    single array (e.g. plat-flip 'delay' = [down, up]; 'sync' = [period, phase,
    ease_out, ease_in]). A lump is emitted only if at least one of its
    contributing fields passes its write_if; slots not written use their field
    default so the array stays well-formed.
    """
    groups = {}  # lump_key -> {"type": t, "slots": {idx: (out_value, wrote)}, "any": bool}
    for f in fields:
        lp = f.get("lump")
        if not isinstance(lp, dict) or not lp.get("key"):
            continue
        key = lp["key"]
        ltype = lp.get("type", f.get("type", "float"))
        slot = lp.get("slot", 0)
        default = f.get("default")
        value = get(f.get("key"), default)
        wrote = _should_write(value, f.get("write_if", "always"), default)
        # bool fields may map a True to a specific lump value
        if f.get("type") == "bool" and value and "value_if_true" in f:
            out = f["value_if_true"]
        else:
            out = value if wrote else default
        g = groups.setdefault(key, {"type": ltype, "slots": {}, "any": False})
        g["slots"][slot] = (out, wrote)
        if wrote:
            g["any"] = True

    result = {}
    for key, g in groups.items():
        if not g["any"]:
            continue
        n = max(g["slots"]) + 1
        vals = []
        for i in range(n):
            out, _wrote = g["slots"].get(i, (0, False))
            vals.append(_coerce(g["type"], out))
        result[key] = [g["type"]] + vals
    return result
