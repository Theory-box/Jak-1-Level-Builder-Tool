# Backward-compatibility code

During development old `.blend` files and older database formats are **not**
supported on purpose (Kuitar, 2026-10-08): breaking changes are fine, and new
compatibility code is only added when a break would really hurt, after asking.
Such code is marked with a `# COMPAT:` comment (`grep -rn "COMPAT:" addons/`)
and listed here.

The code audit (branch `claude/audit`, 2026-11-20) removed every shim that was
here: old prop names / scale fields converted on load, old DB record formats,
`legacy_key`, TraitFields, the old single volume link, the `<actor>_wp_NN`
waypoint fallback and its Migrate button, the level-index fill-in, the
no-level-collection fallback and the first-version project-settings tags.

| Where | What it keeps working | Remove with |
| --- | --- | --- |
| (none) | | |

Not addon-version code (kept): OpenGOAL / Blender version support
(`versions.py` feature checks, built-in vs legacy cameras for OpenGOAL before
v0.3.4, Blender 5 special cases, older decompilers' flat `glb_out/` layout),
the min / max clamp at export (`export/schema_emit.py`, a safety net) and the
AllSFX table (still drives the SFX list). Path-mode enum numbers stay pinned
(saved values).
