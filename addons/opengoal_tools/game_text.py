"""Strings the game shows (text JSON): one conversion for every exported text.

The game font has no lowercase letters (they show as Japanese characters), so
texts are uppercased on export. OpenGOAL's text compiler already handles
accents, ' and the button tags; typographic quotes / dashes from copy-paste
become their plain versions. Characters the vanilla texts never use are
reported (they may not show).
"""
from __future__ import annotations

import re

import bpy

# Tags / codes kept as typed: <PAD_X> ... and ~ format codes (~D, ~34L).
_KEEP = re.compile(r"<[A-Z_0-9]+>|~[0-9,]*[A-Za-z%]")
_PLAIN = str.maketrans({"‘": "'", "’": "'", "‚": "'", "′": "'", "´": "'", "`": "'",
                        "“": '"', "”": '"', "„": '"', "–": "-", "—": "-",
                        " ": " "})
_ELLIPSIS = "…"
# Every character the vanilla texts use (all languages but Japanese), uppercase.
SUPPORTED = set(" !\"%'()+,-./0123456789:=?ABCDEFGHIJKLMNOPQRSTUVWXYZ_"
                "¡º¿ÀÁÂÃÄÅÆÇÈÉÊËÌ"
                "ÍÎÑÒÓÔÕÖØÙÚÛÜÝ"
                "ĄĆČĐĖĘĚĮŁŃŐŒŘŚŠ"
                "ŪŮŰŲŹŻŽ™")
PAD_TAGS = ("<PAD_X>", "<PAD_CIRCLE>", "<PAD_SQUARE>", "<PAD_TRIANGLE>")


def _is_japanese(c):
    return "　" <= c <= "ヿ" or "一" <= c <= "鿿"


def game_text(s):
    """The string as the game should get it: uppercase (tags kept), plain quotes."""
    s = str(s).translate(_PLAIN).replace(_ELLIPSIS, "...")
    out, i = [], 0
    for m in _KEEP.finditer(s):
        out.append(s[i:m.start()].upper())
        out.append(m.group(0))
        i = m.end()
    out.append(s[i:].upper())
    return "".join(out)


def unsupported(s):
    """Characters of the converted string the game font may not have (a task
    text's "#x..." id and [level_name] aren't text)."""
    s = str(s)
    if re.fullmatch(r"\s*#x[0-9a-fA-F]+\s*", s):
        return ""
    t = _KEEP.sub("", game_text(s.replace("[level_name]", "")))
    return "".join(sorted({c for c in t if c not in SUPPORTED and not _is_japanese(c)}))


def draw_field(layout, owner, prop, text=None):
    """A text field with a "?" (how the game shows it) and a warning under it."""
    row = layout.row(align=True)
    if text is None:
        row.prop(owner, prop)
    else:
        row.prop(owner, prop, text=text)
    row.operator("og.game_text_help", text="", icon="QUESTION")
    bad = unsupported(getattr(owner, prop))
    if bad:
        w = layout.row(); w.alert = True
        w.label(text=f"May not show in game: {' '.join(bad)}", icon="ERROR")


class OG_OT_GameTextHelp(bpy.types.Operator):
    """In game, texts are shown in capitals (done on export). Accents and ' work.
Button icons: <PAD_X> <PAD_CIRCLE> <PAD_SQUARE> <PAD_TRIANGLE>"""
    bl_idname = "og.game_text_help"
    bl_label = "Game Text"
    bl_options = {"INTERNAL"}

    def execute(self, ctx):
        def draw(menu, _ctx):
            col = menu.layout.column()
            col.label(text="Shown in capitals in game (done on export).")
            col.label(text="Accents and ' work; curly quotes become plain ones.")
            col.label(text="Button icons: " + " ".join(PAD_TAGS))
            col.label(text="Other symbols may not show: a warning appears under the field.")
        ctx.window_manager.popup_menu(draw, title="Game Text", icon="QUESTION")
        return {"FINISHED"}


CLASSES = (OG_OT_GameTextHelp,)
