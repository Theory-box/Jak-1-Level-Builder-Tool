# ---------------------------------------------------------------------------
# project_settings.py — OpenGOAL Level Tools
# Settings of the whole project (scene.og_project), Level > Project Settings:
#   - Retail Boot Checkpoint: where a retail (non-debug) boot starts
#     (engine/game/game-info.gc, vanilla "title-start")
#   - New Game Checkpoint: where New Game starts (engine/ui/progress/progress.gc
#     "intro-start", and a new-game save's game-save.gc "game-start")
#   - Quit To Menu Checkpoint: where Quit goes (progress.gc / pc/progress-pc.gc
#     "title-start")
#   - Discord RPC Status (pc/pckernel.gc, vanilla "Playing Jak and Daxter: ...")
# Blank = the game file is left as vanilla (a value set before is put back).
# The patched lines carry ";; og-level-tools project" and the vanilla value,
# so they can always be restored. Written on export, only when changed.
# ---------------------------------------------------------------------------
from __future__ import annotations

import re
import bpy
from bpy.props import StringProperty, PointerProperty

_TAG = ";; og-level-tools project"


def _checkpoint_names(self, ctx, edit_text):
    """Search list: this .blend's checkpoints, then the game's (level-info.gc)."""
    out = []
    from .collections import _all_level_collections, spawn_uid
    for col in _all_level_collections(ctx.scene):
        for o in col.all_objects:
            if o.type == "EMPTY" and o.name.startswith("CHECKPOINT_") and not o.name.endswith("_CAM"):
                out.append((f"{col.name}-{spawn_uid(o)}", f"{col.name} (this .blend)"))
    out += [(n, "game") for n in vanilla_checkpoints()]
    t = edit_text.lower()
    return [(n, d) for n, d in out if t in n.lower()] if t else out


_VANILLA: list = []


def vanilla_checkpoints():
    """Continue-point names of the game's level-info.gc (read once)."""
    if not _VANILLA:
        try:
            from .export import _goal_src
            txt = (_goal_src() / "engine" / "level" / "level-info.gc").read_text(encoding="utf-8", errors="replace")
            _VANILLA[:] = re.findall(r"'continue-point\s+:name \"([^\"]+)\"", txt)
        except Exception:
            pass
    return _VANILLA


class OGProjectSettings(bpy.types.PropertyGroup):
    retail_checkpoint: StringProperty(
        name="Retail Boot Checkpoint", default="", search=_checkpoint_names, search_options={"SUGGESTION"},
        description="Checkpoint a retail (non-debug) boot starts at. Blank: unchanged (the title screen)")
    new_game_checkpoint: StringProperty(
        name="New Game Checkpoint", default="", search=_checkpoint_names, search_options={"SUGGESTION"},
        description="Checkpoint New Game starts at. Blank: unchanged (the intro, then game-start)")
    quit_checkpoint: StringProperty(
        name="Quit To Menu Checkpoint", default="", search=_checkpoint_names, search_options={"SUGGESTION"},
        description="Checkpoint Quit (pause menu) goes to. Blank: unchanged (the title screen)")
    discord_status: StringProperty(
        name="Discord RPC Status", default="",
        description="Status Discord shows while playing this mod (pc/pckernel.gc). Blank: unchanged")


# key -> [(file parts, line pattern with the vanilla value, vanilla value)];
# every match in the file is set (New Game has 5 in progress.gc). key None:
# a line an older version patched by mistake, always put back to vanilla.
_INIT = r"(\(initialize! \*game-info\* 'game \(the-as game-save #f\) "
_PATCHES = {
    "retail_checkpoint": [(("engine", "game", "game-info.gc"), r'(\(else ")title-start("\)\)\))', "title-start")],
    "new_game_checkpoint": [(("engine", "ui", "progress", "progress.gc"), _INIT + r'")intro-start("\))', "intro-start"),
                            (("engine", "game", "game-save.gc"), r'(\(set-continue! this ")game-start("\))', "game-start")],
    "quit_checkpoint": [(("engine", "ui", "progress", "progress.gc"), _INIT + r'")title-start("\))', "title-start"),
                        (("pc", "progress-pc.gc"), _INIT + r'")title-start("\))', "title-start")],
    "discord_status": [(("pc", "pckernel.gc"), r'(\(set! \(-> info status\) ")Playing Jak and Daxter: The Precursor Legacy™("\))',
                        "Playing Jak and Daxter: The Precursor Legacy™")],
    None: [(("pc", "progress-pc.gc"), r'(\(get-continue-by-name \*game-info\* ")game-start("\)\))', "game-start")],
}


_VALUE_RX = r'(?:[^"\n\\]|\\.)*'          # a GOAL string's contents (escapes allowed)


def _gc_string(v):
    return v.replace("\\", "\\\\").replace('"', '\\"')


def apply(scene):
    """Write the project settings into the game files (or put vanilla back).
    Returns the files changed."""
    from .export import _goal_src, log
    s = scene.og_project
    root = _goal_src()
    changed = []
    for key, patches in _PATCHES.items():
        value = getattr(s, key).strip() if key else ""
        for parts, pattern, vanilla in patches:
            p = root.joinpath(*parts)
            if not p.exists():
                continue
            raw = p.read_bytes()
            crlf = b"\r\n" in raw
            txt = raw.decode("utf-8").replace("\r\n", "\n")
            # The line with any value, the rest of the line, and our tag at its end
            # (the tag goes after the whole line: closing parens may follow).
            # Changed only when it holds the vanilla value or carries our tag;
            # each key has its own tag so two settings on the same kind of line
            # stay apart (None: the first version's tag, "<tag>: was").
            tag = f"{_TAG} {key}" if key else f"{_TAG}:"
            head, tail = pattern.split(vanilla, 1)
            rx = re.compile(head + f"({_VALUE_RX})" + tail + r"([^\n]*?)" + rf"([ \t]*{re.escape(tag)}[^\n]*)?$",
                            re.M)

            def repl(m):
                g1, cur, g2, rest, old_tag = m.groups()
                if old_tag is None and cur != vanilla:
                    return m.group(0)                   # someone else's line
                if value:
                    return f'{g1}{_gc_string(value)}{g2}{rest} {tag}: was "{vanilla}"'
                return f"{g1}{vanilla}{g2}{rest}"
            new, n = rx.subn(repl, txt)
            if not n:
                if key:
                    log(f"WARNING: {p.name}: the {key} line wasn't found (game version?)")
                continue
            if new == txt:
                continue
            if crlf:
                new = new.replace("\n", "\r\n")
            p.write_bytes(new.encode("utf-8"))
            changed.append(p.name)
    if changed:
        log(f"Project settings written: {', '.join(changed)}")
    return changed


CLASSES = (OGProjectSettings,)


def register_props():
    bpy.types.Scene.og_project = PointerProperty(type=OGProjectSettings)


def unregister_props():
    if hasattr(bpy.types.Scene, "og_project"):
        del bpy.types.Scene.og_project
