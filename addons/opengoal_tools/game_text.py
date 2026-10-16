"""Strings the game shows (text JSON): one conversion for every exported text.

The game font has no lowercase letters (they show as Japanese characters), so
texts are uppercased on export. OpenGOAL's text compiler already handles
accents, ' and the button tags; typographic quotes / dashes from copy-paste
become their plain versions. Characters the vanilla texts never use are
reported (they may not show).

References to existing texts (resolved by export/tasks_export.py):
  #xa00              the whole field: that text id
  [level_name]       the level's Menu Name
  [text:<name>]      a game text by its text-id name (engine/ui/text-h.gc)
A whole-field reference uses that text's id; inside a sentence it's replaced
by the (English) text.
"""
from __future__ import annotations

import os
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

ID_RE = re.compile(r"\s*#x([0-9a-fA-F]+)\s*")
VAR_RE = re.compile(r"\[(level_name|text:([a-z0-9-]+)|task:([a-z0-9-]+))\]")


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


# ── the game's own texts: {name: (id, English text)} ────────────────────────
_VANILLA = {"key": None, "texts": {}}


def vanilla_texts():
    """{text-id name: (id, English text or "")} from text-h.gc and the
    decompiler's game_text.txt (cached until those files change)."""
    from .export.paths import _goal_src, _data
    th = _goal_src() / "engine" / "ui" / "text-h.gc"
    gt = _data() / "decompiler_out" / "jak1" / "assets" / "game_text.txt"
    key = tuple(os.path.getmtime(p) if p.exists() else 0 for p in (th, gt)) + (str(th),)
    if key == _VANILLA["key"]:
        return _VANILLA["texts"]
    english = {}
    if gt.exists():
        for m in re.finditer(r'\(#x([0-9a-fA-F]+)\s*\n\s*"((?:[^"\\]|\\.)*)"', gt.read_text(encoding="utf-8", errors="replace")):
            english[int(m.group(1), 16)] = m.group(2)
    texts = {}
    if th.exists():
        for m in re.finditer(r"\(([a-z0-9-]+) #x([0-9a-fA-F]+)\)", th.read_text(encoding="utf-8", errors="replace")):
            i = int(m.group(2), 16)
            texts[m.group(1)] = (i, english.get(i, ""))
    _VANILLA.update(key=key, texts=texts)
    _TEXT_ITEMS.clear()
    return texts


def unknown_refs(s):
    """[text:<name>] / [task:<name>] references that name no game text / no
    task of this .blend."""
    refs = [(m.group(2), m.group(3)) for m in VAR_RE.finditer(str(s)) if m.group(2) or m.group(3)]
    if not refs:
        return []
    out = []
    vt = vanilla_texts() if any(a for a, _b in refs) else {}
    tasks = {t.name for t in bpy.context.scene.og_tasks.tasks} if any(b for _a, b in refs) else set()
    for a, b in refs:
        if a and a not in vt:
            out.append(a)
        elif b and b not in tasks:
            out.append(f"task {b}")
    return out


def unsupported(s):
    """Characters of the converted string the game font may not have
    (references aren't text)."""
    s = str(s)
    if ID_RE.fullmatch(s):
        return ""
    t = _KEEP.sub("", game_text(VAR_RE.sub("", s)))
    return "".join(sorted({c for c in t if c not in SUPPORTED and not _is_japanese(c)}))


def draw_field(layout, owner, prop, text=None):
    """A game text field: "?" (how the game shows it, references), a picker
    for an existing game text, and warnings under it."""
    row = layout.row(align=True)
    if text is None:
        row.prop(owner, prop)
    else:
        row.prop(owner, prop, text=text)
    op = row.operator("og.pick_game_text", text="", icon="VIEWZOOM")
    op.prop_key = prop
    op.id_name = owner.id_data.name
    op.id_kind = owner.id_data.bl_rna.identifier.upper()
    op.data_path = owner.path_from_id()
    row.operator("og.game_text_help", text="", icon="QUESTION")
    val = getattr(owner, prop)
    bad = unsupported(val)
    if bad:
        w = layout.row(); w.alert = True
        w.label(text=f"May not show in game: {' '.join(bad)}", icon="ERROR")
    for n in unknown_refs(val):
        w = layout.row(); w.alert = True
        w.label(text=f"Not found: {n}", icon="ERROR")


class OG_OT_GameTextHelp(bpy.types.Operator):
    """How the game shows this text, and how to use an existing text"""
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
            col.separator()
            col.label(text="Use an existing text:")
            col.label(text="   [level_name]   this level's Menu Name")
            col.label(text="   [text:name]   a game text by name (search button)")
            col.label(text="   [task:name]   a custom task's Introduced text")
            col.label(text="   #xa00   a text id (the whole field)")
            col.label(text="Alone in the field: that same text. In a sentence: its English words.")
        ctx.window_manager.popup_menu(draw, title="Game Text", icon="QUESTION")
        return {"FINISHED"}


_TEXT_ITEMS: list = []   # search-popup items must stay referenced


class OG_OT_PickGameText(bpy.types.Operator):
    """Use an existing game text (search by name or words): sets the field to [text:name]"""
    bl_idname = "og.pick_game_text"
    bl_label = "Pick Game Text"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    bl_property = "text"

    def _items(self, context):
        items = [("[level_name]", "[level_name]  (this level's Menu Name)", "")]
        for t in context.scene.og_tasks.tasks if context.scene.og_tasks.enabled else ():
            if t.name:
                items.append((f"[task:{t.name}]", f"task {t.name}  ·  {t.text_intro[:60]}", "A custom task's Introduced text"))
        vt = vanilla_texts()
        for name, (i, en) in sorted(vt.items(), key=lambda kv: kv[1][0]):
            items.append((f"[text:{name}]", f"{name}  ·  {en[:60]}" if en else name, f"#x{i:x}"))
        items = [(a, b, c, k) for k, (a, b, c) in enumerate(items)]
        if items != _TEXT_ITEMS:
            _TEXT_ITEMS[:] = items
        return _TEXT_ITEMS

    prop_key: bpy.props.StringProperty(options={"SKIP_SAVE", "HIDDEN"})
    data_path: bpy.props.StringProperty(options={"SKIP_SAVE", "HIDDEN"})
    id_name: bpy.props.StringProperty(options={"SKIP_SAVE", "HIDDEN"})
    id_kind: bpy.props.StringProperty(options={"SKIP_SAVE", "HIDDEN"})
    text: bpy.props.EnumProperty(name="Text", items=_items)

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        ids = {"SCENE": bpy.data.scenes, "COLLECTION": bpy.data.collections}.get(self.id_kind, bpy.data.objects)
        idb = ids.get(self.id_name)
        try:
            owner = idb.path_resolve(self.data_path) if idb is not None and self.data_path else idb
        except ValueError:
            owner = None
        if owner is None:
            return {"CANCELLED"}
        setattr(owner, self.prop_key, self.text)
        return {"FINISHED"}


CLASSES = (OG_OT_GameTextHelp, OG_OT_PickGameText)
