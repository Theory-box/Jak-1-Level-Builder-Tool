"""Custom tasks export (tasks.py data -> game files). Needs mod-base.

Per task group (one per .blend):
- the task names in game-task-h.gc and all-types.gc, in a marked block
  before (max N); max raised to cover every task (level_tools.ensure_task_engine,
  with mod-base's save fixes)
- goal_src/jak1/levels/level-tools/lt-tasks-<group>.gc: the task-controls
  (stages + conditions) and the progress menu pages. At boot it puts them in
  longer copies of *task-controls*, *level-task-data*, *level-task-data-remap*
  and *game-counts*: task-control.gc / progress-static.gc stay untouched.
  Compiled once (game.gp) and loaded with the game (game.gd), like lt-checkpoint.
- game/assets/jak1/text/lt_<group>_text_en-US.json: the menu names (registered
  in game_text.gp next to the user's game_custom_text). Text ids start at the
  "starting text ID" and skip ids the game / other files use.
Every file is only written when its content changed.
"""
from __future__ import annotations

import json
import re

from .paths import _goal_src, _game_gp, _data, log
from .level_tools import (_write_if_changed, _patch, task_enum, ensure_task_engine, LT_DIR, _TAG)

_BEGIN = ";; og-level-tools tasks: {g} BEGIN"
_END = ";; og-level-tools tasks: {g} END"
_DGO_GAME = ("dgos", "game.gd")
_ALL_TYPES = ("decompiler", "config", "jak1", "all-types.gc")

_COND = {
    "ALWAYS": lambda st: "#t",
    "STAGE_CLOSED": lambda st: (f"(task-closed? (game-task {st.cond_task.strip()}) (task-status {st.cond_status}))"
                                if st.cond_task.strip() else "#t"),
    "CELLS": lambda st: f"(>= (the int (the float (send-event *target* 'query 'pickup (pickup-type fuel-cell)))) {st.cond_value})",
    "ORBS": lambda st: (f"(and *target* (>= (the-as float (send-event *target* 'query 'pickup (pickup-type money))) "
                        f"{float(st.cond_value)}))"),
}


def _text_dir():
    return _data() / "game" / "assets" / "jak1" / "text"


def _text_json_name(group):
    return f"lt_{group}_text_en-US.json"


def used_text_ids(group):
    """Text ids the game and other text files use (not this group's file)."""
    used = set()
    dec = _data() / "decompiler_out" / "jak1" / "assets" / "game_text.txt"
    if dec.exists():
        used |= {int(m, 16) for m in re.findall(r"\(#x([0-9a-fA-F]+)", dec.read_text(encoding="utf-8", errors="replace"))}
    th = _goal_src() / "engine" / "ui" / "text-h.gc"
    if th.exists():
        used |= {int(m, 16) for m in re.findall(r"\([a-z0-9-]+ #x([0-9a-fA-F]+)\)", th.read_text(encoding="utf-8", errors="replace"))}
    td = _text_dir()
    if td.exists():
        mine = _text_json_name(group)
        for f in td.glob("*.json"):
            if f.name == mine:
                continue
            try:
                used |= {int(k, 16) for k in json.loads(f.read_text(encoding="utf-8")).keys()}
            except Exception:
                pass
    return used


def _other_group_tasks(group):
    """{name: id} of task entries outside this group's block (vanilla, other
    groups, other mods)."""
    p = _goal_src().joinpath("engine", "game", "task", "game-task-h.gc")
    txt = p.read_text(encoding="utf-8", errors="replace")
    b, e = _BEGIN.format(g=group), _END.format(g=group)
    if b in txt and e in txt:
        txt = txt[:txt.index(b)] + txt[txt.index(e) + len(e):]
    ids = {m.group(1): int(m.group(2)) for m in re.finditer(r"^\s*\(([a-z0-9-]+)\s+(\d+)\)", txt, re.M)}
    ids.pop("max", None)
    return ids


def check(scene):
    """[problem text] that stop the export (names / ids clashing with tasks
    outside this group)."""
    from .. import tasks as T
    s = T.settings(scene)
    group = T.group_name(scene)
    others = _other_group_tasks(group)
    by_id = {v: k for k, v in others.items()}
    out = [m for i, m in T.problems(scene) if "limit" in m or "used twice" in m or "no name" in m or "vanilla" in m]
    for t in s.tasks:
        if t.name in others:
            out.append(f"task name '{t.name}' is already a game-task ({others[t.name]})")
        if t.task_id in by_id:
            out.append(f"task {t.name}: ID {t.task_id} is already used by '{by_id[t.task_id]}'")
    return out


def _enum_block(group, tasks):
    """The group's enum lines (indented like the enum's (max ...) line by _put_enum_block)."""
    return [_BEGIN.format(g=group)] + [f"({t.name} {t.task_id})" for t in tasks] + [_END.format(g=group)]


def _put_enum_block(path, group, block):
    """Replace this group's block (or add it before (max ...)) in an enum file."""
    if not path.exists():
        log(f"WARNING: {path} not found")
        return False
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    txt = raw.decode("utf-8").replace("\r\n", "\n")
    b, e = _BEGIN.format(g=group), _END.format(g=group)
    start = txt.index("(defenum game-task")
    m = re.compile(r"^([ \t]*)\(max\b", re.M).search(txt, start)
    if not m:
        log(f"WARNING: {path.name}: no (max ...) in the game-task enum")
        return False
    ind = m.group(1)
    text = "\n".join(ind + line for line in block)
    if b in txt and e in txt:
        i = txt.rfind("\n", 0, txt.index(b)) + 1          # from the start of the BEGIN line
        j = txt.index(e) + len(e)
        new = txt[:i] + text + txt[j:]
    else:
        new = txt[:m.start()] + text + "\n" + txt[m.start():]
    if crlf:
        new = new.replace("\n", "\r\n")
    if new.encode("utf-8") == raw:
        return False
    path.write_bytes(new.encode("utf-8"))
    log(f"Patched {path.name}: tasks of group {group}")
    return True


def _set_all_types_max(path, mx):
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    txt = raw.decode("utf-8").replace("\r\n", "\n")
    start = txt.index("(defenum game-task")
    m = re.compile(r"\(max\s*(\d*)\)").search(txt, start)
    if not m or m.group(1) == str(mx):
        return False
    new = txt[:m.start()] + f"(max {mx})" + txt[m.end():]
    if crlf:
        new = new.replace("\n", "\r\n")
    path.write_bytes(new.encode("utf-8"))
    return True


def _texts(scene, group):
    """({text id: string} of this group, {task name: [3 slot ids]}, {level col
    name: level name text id})."""
    from .. import tasks as T
    from ..collections import _all_level_collections
    s = T.settings(scene)
    used = used_text_ids(group)
    nxt = [max(s.start_text_id, 0x100)]
    strings = {}            # string -> id (same string, same id)

    def alloc(text):
        if text in strings:
            return strings[text]
        while nxt[0] in used:
            nxt[0] += 1
        tid = nxt[0]
        nxt[0] += 1
        strings[text] = tid
        return tid

    levels = {}
    for col in _all_level_collections(scene):
        if any(t.level == col.name for t in s.tasks):
            menu = (col.og_level.menu_name.strip() if hasattr(col, "og_level") else "") or \
                str(col.get("og_level_name", col.name)).upper()
            levels[col.name] = (alloc(menu), menu)

    slots = {}
    for t in s.tasks:
        raw = [t.text_intro.strip(), t.text_reminder.strip(), t.text_resolution.strip()]
        # empty: the next filled one further into completion, else the last filled one
        filled = [x for x in raw if x]
        fall = filled[-1] if filled else t.name.replace("-", " ").upper()
        vals = []
        for k, x in enumerate(raw):
            vals.append(x or next((y for y in raw[k + 1:] if y), fall))
        ids = []
        lvl_id, lvl_name = levels.get(t.level, (None, ""))
        for x in vals:
            m = re.fullmatch(r"#x([0-9a-fA-F]+)", x)
            if m:
                ids.append(int(m.group(1), 16))
            elif x == "[level_name]" and lvl_id is not None:
                ids.append(lvl_id)
            else:
                ids.append(alloc(x.replace("[level_name]", lvl_name)))
        slots[t.name] = ids
    return {v: k for k, v in strings.items()}, slots, {k: v[0] for k, v in levels.items()}


def _counts(scene, level_col):
    """(orbs, scout flies) of a level, for its progress page."""
    from ..collections import _recursive_col_objects
    orbs = flies = 0
    for o in _recursive_col_objects(level_col, exclude_no_export=True):
        if not (o.type == "EMPTY" and o.name.startswith("ACTOR_")) or "_wp_" in o.name:
            continue
        et = o.name.split("_", 2)[1]
        if et == "money":
            orbs += 1
        elif et == "buzzer":
            flies += 1
        elif et in ("crate", "crate-buzzer"):
            ct = str(o.get("og_crate_pickup", "") or o.get("og_crate_type", ""))
            if "buzzer" in ct:
                flies += 1
            elif "money" in ct:
                orbs += int(o.get("og_crate_pickup_amount", 1) or 1)
    return orbs, flies


def generate_gc(scene, group, slots, level_text):
    """lt-tasks-<group>.gc text."""
    from .. import tasks as T
    from ..collections import _all_level_collections
    s = T.settings(scene)
    gs = re.sub(r"[^a-z0-9]+", "-", group)
    L = [";;-*-Lisp-*-", "(in-package goal)",
         f";; lt-tasks-{group}.gc -- written by OpenGOAL Level Tools from the .blend's tasks (task group '{group}').",
         ";; Edits are overwritten by the next export.", ""]
    # task controls
    L.append(f"(define *lt-{gs}-task-ids* (new 'static 'boxed-array :type int32 "
             + " ".join(str(t.task_id) for t in s.tasks) + "))")
    L.append(f"(define *lt-{gs}-task-controls*")
    L.append("  (new 'static 'boxed-array :type task-control")
    for t in s.tasks:
        L.append(f"    (new 'static 'task-control :current-stage -1 :stage  ;; {t.name} {t.task_id}")
        L.append("      (new 'static 'boxed-array :type task-cstage")
        for st in t.stages:
            flags = " ".join(f for f, on in (("has-entity", st.has_entity), ("closed-by-default", st.closed_by_default)) if on)
            cond = _COND.get(st.condition, _COND["ALWAYS"])(st)
            L.append(f"        (new 'static 'task-cstage :game-task (game-task {t.name}) :status (task-status {st.status})"
                     f" :flags (task-flags {flags})")
            L.append(f"             :condition (lambda :behavior process-taskable ((arg0 task-control)) {cond}))")
        L.append("        ))")
    L.append("    ))")
    L.append("")
    # progress pages
    pages = []
    for col in _all_level_collections(scene):
        lt = [t for t in s.tasks if t.level == col.name][:8]
        if not lt:
            continue
        idx = int(col.get("og_level_index", 100))
        fly = next((i for i, t in enumerate(lt) if t.buzzer), -1)
        orbs, flies = _counts(scene, col)
        infos = []
        for t in lt:
            a, b, c = slots[t.name]
            infos.append(f"(new 'static 'task-info-data :task-id (game-task {t.name}) :text-index-when-resolved {int(t.done_slot)}"
                         f" :task-name (new 'static 'array text-id 4 #x{a:x} #x{b:x} #x{c:x} (text-id zero)))")
        pages.append((idx, orbs, flies,
                      f"    (new 'static 'level-tasks-info :level-name-id #x{level_text[col.name]:x}"
                      f" :text-group-index 1 :nb-of-tasks {len(lt)} :buzzer-task-index {fly}\n"
                      f"      :task-info (new 'static 'array task-info-data 8\n        " + "\n        ".join(infos) + "))"))
    L.append(f"(define *lt-{gs}-pages* (new 'static 'boxed-array :type level-tasks-info")
    L += [p[3] for p in pages]
    L.append("    ))")
    L.append(f"(define *lt-{gs}-page-levels* (new 'static 'boxed-array :type int32 " + " ".join(str(p[0]) for p in pages) + "))")
    L.append(f"(define *lt-{gs}-page-counts* (new 'static 'boxed-array :type int32 "
             + " ".join(f"{p[1]} {p[2]}" for p in pages) + "))")
    L.append("")
    L.append(_INSTALL.replace("<g>", gs))
    return "\n".join(L) + "\n"


# Installs one group's data at boot (GAME.CGO link time, after the engine):
# longer copies of the game's tables, with this group's entries in them.
_INSTALL = """
;; a game-count-info with room for 32 pages (same layout: length + inline count-info)
(deftype lt-game-count-info-<g> (basic)
  ((length int32)
   (data   count-info 32 :inline)))

(defun lt-tasks-install-<g> ()
  ;; task controls: one per game-task, ours at their ids
  (let* ((n (the int (game-task max)))
         (old *task-controls*)
         (arr (new 'global 'boxed-array task-control n)))
    (dotimes (i n)
      (set! (-> arr i) (if (< i (-> old length)) (-> old i) *null-task-control*)))
    (dotimes (i (-> *lt-<g>-task-ids* length))
      (set! (-> arr (-> *lt-<g>-task-ids* i)) (-> *lt-<g>-task-controls* i)))
    (set! *task-controls* (the-as (array task-control) arr))
    (dotimes (i (-> *lt-<g>-task-controls* length))
      (reset! (-> *lt-<g>-task-controls* i) 'game #f)
      (first-any (-> *lt-<g>-task-controls* i) #f)))
  ;; progress pages, the level -> page remap and the orb / fly counts
  (let ((np (-> *lt-<g>-pages* length)))
    (when (> np 0)
      (let* ((old *level-task-data*)
             (base (-> old length))
             (pages (new 'global 'boxed-array level-tasks-info (+ base np))))
        (dotimes (i base) (set! (-> pages i) (-> old i)))
        (dotimes (i np) (set! (-> pages (+ base i)) (-> *lt-<g>-pages* i)))
        (set! *level-task-data* (the-as (array level-tasks-info) pages))
        ;; remap: level-info :index - 1 -> page
        (let ((len (-> *level-task-data-remap* length)))
          (dotimes (i np) (set! len (max len (-> *lt-<g>-page-levels* i))))
          (let ((remap (new 'global 'boxed-array int32 len)))
            (dotimes (i len)
              (set! (-> remap i) (if (< i (-> *level-task-data-remap* length)) (-> *level-task-data-remap* i) 0)))
            (dotimes (i np)
              (set! (-> remap (+ (-> *lt-<g>-page-levels* i) -1)) (+ base i)))
            (set! *level-task-data-remap* (the-as (array int32) remap))))
        ;; counts
        (let ((cnt (new 'global 'lt-game-count-info-<g>))
              (oldc *game-counts*))
          (set! (-> cnt length) (+ base np))
          (dotimes (i base)
            (when (and oldc (< i (-> oldc length)))
              (set! (-> cnt data i money-count) (-> oldc data i money-count))
              (set! (-> cnt data i buzzer-count) (-> oldc data i buzzer-count))))
          (dotimes (i np)
            (set! (-> cnt data (+ base i) money-count) (-> *lt-<g>-page-counts* (* i 2)))
            (set! (-> cnt data (+ base i) buzzer-count) (-> *lt-<g>-page-counts* (+ (* i 2) 1))))
          (set! *game-counts* (the-as game-count-info cnt))))))
  (format 0 "[lt-tasks] <g>: ~D task(s), ~D page(s)~%" (-> *lt-<g>-task-ids* length) (-> *lt-<g>-pages* length))
  (none))

(lt-tasks-install-<g>)
"""


def export_tasks(scene):
    """Write the group's task files (only what changed). Returns problems
    (nothing written when there are any) or []."""
    from .. import tasks as T
    from ..versions import feature_status
    s = T.settings(scene)
    if not s.enabled or not len(s.tasks):
        return []
    if feature_status("custom_tasks")[0] is not True:
        return ["custom tasks need mod-base (Tasks panel)"]
    errs = check(scene)
    if errs:
        for e in errs:
            log(f"[tasks] {e}")
        return errs
    group = T.group_name(scene)
    ids, _mx = task_enum()
    need_max = max([t.task_id for t in s.tasks] + list(ids.values())) + 1
    # names in the enum (game code + level .jsonc), then max (+ mod-base save fixes)
    block = _enum_block(group, s.tasks)
    _put_enum_block(_goal_src().joinpath("engine", "game", "task", "game-task-h.gc"), group, block)
    ensure_task_engine(need_max)
    _ids, mx = task_enum()
    at = _data().joinpath(*_ALL_TYPES)
    if at.exists():
        _put_enum_block(at, group, block)
        _set_all_types_max(at, mx)
    # texts
    strings, slots, level_text = _texts(scene, group)
    td = _text_dir()
    _write_if_changed(td / _text_json_name(group),
                      json.dumps({f"{k:x}": v for k, v in sorted(strings.items())}, indent=2, ensure_ascii=False) + "\n")
    gp = _data() / "game" / "assets" / "jak1" / "game_text.gp"
    if gp.exists():
        txt = gp.read_text(encoding="utf-8")
        entry = f'"game/assets/jak1/text/{_text_json_name(group)}"'
        if entry not in txt:
            new = txt.replace('"game/assets/jak1/text/game_custom_text_en-US.json"',
                              f'"game/assets/jak1/text/game_custom_text_en-US.json" {entry}', 1)
            if new != txt:
                gp.write_text(new, encoding="utf-8")
                log(f"Patched {gp.name}: {_text_json_name(group)}")
    # the task file + its registration (game.gp goal-src, game.gd object)
    name = f"lt-tasks-{group}"
    _write_if_changed(_goal_src() / LT_DIR / f"{name}.gc", generate_gc(scene, group, slots, level_text))
    _patch(_game_gp(), [f'(goal-src "{LT_DIR}/{name}.gc" "progress" "task-control") {_TAG}'],
           '(group-list "all-code"', f"{name} goal-src")
    _patch(_goal_src().joinpath(*_DGO_GAME), [f'  "{name}.o" {_TAG.replace(";", ";;", 1)}'], " ))", f"{name} object")
    log(f"[tasks] group {group}: {len(s.tasks)} task(s) exported")
    return []
