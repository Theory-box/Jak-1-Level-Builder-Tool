# ───────────────────────────────────────────────────────────────────────
# export/schema_emit.py — OpenGOAL Level Tools
#
# Schema-driven lump emission, driven by the SAME fields[] schema the UI panel
# uses (panels/actor_fields.py). Given an actor's fields[] and a getter for its
# og_* properties, build the lump dict — no per-actor code path.
#
# This implements the DB's existing fields[] convention:
#   field: key, type, default | default_per_etype{etype:v} | default_from(skip),
#          label/min/max (UI only), write_if, value_if_true, choices, note
#   lump:      { key, type, slot?, scale?, format?, pairs_with?, bare? }
#              bare: emit the raw value with no [type, value] wrapper (plain
#              string lumps like continue-name).
#   computed encoder — lump.type "const": emit lump.const verbatim, always
#          (fixed eco-info for pickups; no backing prop).
#   computed encoder — lump.type "eco-info-picker": pickup enum (choices carry
#          engine_string) + pairs_with amount field -> ["eco-info", sym, amount].
#   lump_bit:  { key, type, bit_value }   (OR-accumulated uint32 bitfield)
#   types: float|meters|degrees (->float), int|int32|uint32|mode (->int),
#          bool, symbol|string|enum-uint32|water-height|... (passthrough),
#          symbol_literal (bare 'value), object_ref (SKIPPED — computed in code)
#   write_if: always|None, if_true, if_nonzero, if_nonneg(>=0), if_positive(>0),
#          if_non_empty, if_not_none(!= "none"), if_not_default,
#          if_any_nonzero(GROUP: any value in the lump-group nonzero),
#          if_object_found(SKIPPED — object_ref/computed)
#   enum: choices = inline [{value,label,lump_value?}] or a named-table string.
#         If the selected choice has lump_value -> emit that (int); else emit the
#         value string (with lump.format "(... {value})" applied, or 'value for
#         symbol_literal).
#
# Fields with neither `lump` nor `lump_bit`, or type object_ref, contribute
# nothing (their lumps are produced by computed code emitters). Pure module: no
# Blender import, unit-testable standalone.
# ───────────────────────────────────────────────────────────────────────
from __future__ import annotations

_FLOAT = ("float", "meters", "degrees")
_INT = ("int", "int32", "uint32", "mode")


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _coerce(t, v):
    if v is None:
        v = 0
    if t in _FLOAT:
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0
    if t in _INT:
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0
    if t == "bool":
        return int(bool(v))
    return v  # symbol/string/enum-uint32/water-height/... passthrough


def _resolve_default(f, etype):
    if "default_per_etype" in f:
        return f["default_per_etype"].get(etype)
    if "default_from" in f:
        return None  # computed (scene) — such actors stay code-driven
    return f.get("default")


def _passes(raw, rule, default):
    if rule in (None, "always"):
        return True
    if rule == "if_true":
        return bool(raw)
    if rule == "if_nonzero":
        return _num(raw) != 0
    if rule == "if_nonneg":
        return _num(raw) >= 0
    if rule == "if_positive":
        return _num(raw) > 0
    if rule == "if_non_empty":
        return str(raw).strip() != ""
    if rule == "if_not_none":
        return raw not in (None, "") and str(raw) != "none"
    if rule == "if_not_default":
        return raw != default
    if rule == "if_any_nonzero":
        return None  # decided at group level
    if rule == "if_object_found":
        return False  # computed in code
    return True


def _enum_value(f, raw, default=None):
    """Map an enum selection to its emitted value. Inline choices with lump_value
    emit the int lump_value; otherwise the selected value string is used. If the
    value is not a known choice, fall back to the default choice's lump_value
    (defensive against stale/invalid prop values)."""
    ch = f.get("choices")
    if isinstance(ch, list):
        for c in ch:
            if c.get("value") == raw and "lump_value" in c:
                return c["lump_value"], True   # (value, is_lump_value_int)
        for c in ch:                            # raw unknown -> default choice
            if c.get("value") == default and "lump_value" in c:
                return c["lump_value"], True
    return raw, False


def _resolve_choice_table(f, choice_tables):
    """Return the choices as a list of dicts, resolving a named-table string
    (e.g. "CratePickups") through choice_tables. Inline lists pass through."""
    ch = f.get("choices")
    if isinstance(ch, str):
        return choice_tables.get(ch)
    return ch


def emit_schema_lumps(get, fields, etype=None, choice_tables=None):
    choice_tables = choice_tables or {}
    groups = {}   # lump_key -> dict
    direct = {}   # lump_key -> fully-formed value (computed encoders below)
    for f in fields:
        if f.get("type") == "object_ref":
            continue
        lp = f.get("lump") if isinstance(f.get("lump"), dict) else None
        lb = f.get("lump_bit") if isinstance(f.get("lump_bit"), dict) else None

        # ── Computed encoder: const ──────────────────────────────────────────
        # A fixed lump value with no backing prop, always emitted. Used for
        # pickups whose eco-info never varies (fuel-cell cell-info, buzzer
        # buzzer-info, money eco-info).
        if lp and lp.get("type") == "const":
            direct[lp["key"]] = lp.get("const")
            continue

        # ── Computed encoder: eco-info-picker ────────────────────────────────
        # A pickup enum (choices carry an `engine_string` per id) plus a paired
        # amount field become the 3-element eco-info lump:
        #     ["eco-info", "(pickup-type X)", amount]
        # The pickup→symbol map lives entirely in the choices table (DB), so any
        # actor that declares this field exports eco-info with no code changes.
        # Amount comes from the paired field and passes through as set, unless
        # the chosen pickup pins it via `force_amount` in the choices table.
        if lp and lp.get("type") == "eco-info-picker":
            default = _resolve_default(f, etype)
            raw = get(f.get("key"), default)
            if not _passes(raw, f.get("write_if", "if_not_none"), default):
                continue
            table = _resolve_choice_table(f, choice_tables)
            choice = None
            if isinstance(table, list):
                for c in table:
                    if raw in (c.get("id"), c.get("value")):
                        choice = c
                        break
            if not choice or not choice.get("engine_string"):
                continue  # unknown pickup id / table missing — emit nothing
            engine_str = choice["engine_string"]
            amt_key = lp.get("pairs_with")
            amount = 1
            if amt_key:
                amt_f = next((x for x in fields if x.get("key") == amt_key), None)
                amt_default = _resolve_default(amt_f, etype) if amt_f else 1
                amount = int(_num(get(amt_key, amt_default)))
            # A choice may pin its amount (buzzer → the engine always spawns
            # exactly one scout fly). Everything else passes through as set.
            if choice.get("force_amount") is not None:
                amount = int(choice["force_amount"])
            direct[lp["key"]] = ["eco-info", engine_str, amount]
            continue

        if not lp and not lb:
            continue

        default = _resolve_default(f, etype)
        raw = get(f.get("key"), default)
        rule = f.get("write_if")
        passed = _passes(raw, rule, default)        # True / False / None(group)

        # resolve the emitted value
        if "value_if_true" in f:
            value = f["value_if_true"] if raw else (default if default is not None else 0)
        elif f.get("type") == "enum":
            value, is_lv = _enum_value(f, raw, default)
        else:
            value = raw

        if lb:
            key = lb["key"]
            g = groups.setdefault(key, {"type": lb.get("type", "uint32"),
                                        "mode": "bits", "bits": [], "any": False,
                                        "anynz": False, "nzvals": []})
            g["bits"].append((int(lb.get("bit_value", 0)), bool(passed)))
            if passed:
                g["any"] = True
            continue

        key = lp["key"]
        t = lp.get("type", f.get("type", "float"))
        g = groups.setdefault(key, {"type": t, "mode": "scalar", "slots": {},
                                    "any": False, "anynz": False, "nzvals": [],
                                    "bare": False})
        # apply lump.scale / lump.format / symbol_literal
        if lp.get("scale") is not None and isinstance(value, (int, float)):
            value = value * lp["scale"]
        if f.get("type") == "enum" and not (isinstance(f.get("choices"), list)
                and any(c.get("value") == raw and "lump_value" in c
                        for c in f["choices"])):
            if lp.get("format"):
                value = lp["format"].format(value=value)
        if t == "symbol_literal":
            value = "'%s" % value
            g["bare"] = True
        elif lp.get("format") and f.get("type") != "enum":
            value = lp["format"].format(value=value)
        if lp.get("bare"):
            g["bare"] = True   # emit the raw value with no [type, value] wrapper

        if rule == "if_any_nonzero":
            g["anynz"] = True
        g["nzvals"].append(value)

        slot = lp.get("slot")
        if slot is not None:
            g["mode"] = "array"
            g["slots"][slot] = value
            if passed:
                g["any"] = True
        else:
            g["scalar"] = value
            if passed:
                g["any"] = True

    result = {}
    for key, g in groups.items():
        t = g["type"]
        write = g["any"]
        if g.get("anynz"):
            write = any(_num(v) != 0 for v in g["nzvals"])
        if not write:
            continue
        mode = g.get("mode")
        if mode == "array":
            n = max(g["slots"]) + 1 if g["slots"] else 0
            result[key] = [t] + [_coerce(t, g["slots"].get(i, 0)) for i in range(n)]
        elif mode == "bits":
            acc = 0
            for bit, ok in g["bits"]:
                if ok:
                    acc |= bit
            result[key] = [t, acc]
        else:
            v = g.get("scalar", 0)
            result[key] = v if g.get("bare") else [t, _coerce(t, v)]
    result.update(direct)   # computed encoders (eco-info-picker, ...)
    return result
