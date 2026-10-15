"""Shared GOAL code of the addon: goal_src/jak1/levels/level-tools/lt-*.gc.

Code every level can use lives here once instead of in each level's -obs.gc:
compiled once (a goal-src line in game.gp) and loaded with the game (an entry
in dgos/game.gd, the GAME.CGO list). Files are only written when their
content changed, so an unchanged build doesn't recompile them.
"""
from __future__ import annotations

from .paths import _goal_src, _game_gp, log

LT_DIR = "levels/level-tools"
_TAG = "; og-level-tools"

LT_CHECKPOINT_GC = ';;-*-Lisp-*-\n(in-package goal)\n;; lt-checkpoint.gc -- shared code of OpenGOAL Level Tools (written by the addon).\n;; lt-checkpoint: a checkpoint\'s trigger (Trigger option). Sets its continue point\n;; when Jak enters its sphere radius or its convex volume, then re-arms on exit.\n;; Compiled once (game.gp) and loaded with the game (dgos/game.gd).\n\n;; lt-point-in-planes? -- convex half-space test shared by all trigger volumes.\n;; Planes come from the \'vol res-lump (vector-vol): outward unit normals,\n;; distance pre-scaled to internal units by the build. A point is inside iff\n;; dot(N,P) - w <= 0 for EVERY plane. Zero planes -> not inside.\n(defun lt-point-in-planes? ((planes (inline-array vector)) (num-planes int) (pt vector))\n  (if (zero? num-planes)\n    #f\n    (let ((inside #t))\n      (dotimes (i num-planes)\n        (let ((pl (-> planes i)))\n          (if (< 0.0 (- (+ (* (-> pt x) (-> pl x))\n                           (* (-> pt y) (-> pl y))\n                           (* (-> pt z) (-> pl z)))\n                        (-> pl w)))\n            (set! inside #f))))\n      inside)))\n\n;; lt-checkpoint: sets continue point when Jak enters. Two modes:\n;; convex volume (quote vol) planes (has-volume = 1) or sphere radius (default).\n;; After firing it waits for exit, then re-arms.\n(deftype lt-checkpoint (process-drawable)\n  ((cp-name     string)\n   (cull-radius float)\n   (radius      float)\n   (use-vol     symbol)\n   (was-near    symbol)\n   (num-planes  int32)\n   (planes      (inline-array vector)))\n  :heap-base #x70\n  (:states lt-checkpoint-active lt-checkpoint-wait-exit))\n\n(defstate lt-checkpoint-wait-exit (lt-checkpoint)\n  :code\n  (behavior ()\n    (loop\n      (when (and *target* (zero? (mod (-> *display* base-frame-counter) 4)))\n        (let* ((pos  (-> *target* control trans))\n               (dx   (- (-> pos x) (-> self root trans x)))\n               (dy   (- (-> pos y) (-> self root trans y)))\n               (dz   (- (-> pos z) (-> self root trans z)))\n               (cr   (-> self cull-radius))\n               (still-inside (and\n                 (< (+ (* dx dx) (* dy dy) (* dz dz)) (* cr cr))\n                 (if (-> self use-vol)\n                   (lt-point-in-planes? (-> self planes) (-> self num-planes) pos)\n                   (let ((r (-> self radius)))\n                     (< (+ (* dx dx) (* dy dy) (* dz dz)) (* r r)))))))\n          (when (not still-inside)\n            (format 0 "[lt-checkpoint] ~A re-armed~%" (-> self cp-name))\n            (go lt-checkpoint-active))))\n      (suspend))))\n\n(defstate lt-checkpoint-active (lt-checkpoint)\n  :code\n  (behavior ()\n    (loop\n      (when (and *target* (zero? (mod (-> *display* base-frame-counter) 4)))\n        (let* ((pos  (-> *target* control trans))\n               (dx   (- (-> pos x) (-> self root trans x)))\n               (dy   (- (-> pos y) (-> self root trans y)))\n               (dz   (- (-> pos z) (-> self root trans z)))\n               (cr   (-> self cull-radius))\n               (near (< (+ (* dx dx) (* dy dy) (* dz dz)) (* cr cr)))\n               (inside (and near\n                 (if (-> self use-vol)\n                   (lt-point-in-planes? (-> self planes) (-> self num-planes) pos)\n                   (let ((r (-> self radius)))\n                     (< (+ (* dx dx) (* dy dy) (* dz dz)) (* r r)))))))\n          (set! (-> self was-near) near)\n          (when inside\n            (format 0 "[lt-checkpoint] fired -> ~A~%" (-> self cp-name))\n            (set-continue! *game-info* (-> self cp-name))\n            (go lt-checkpoint-wait-exit))))\n      (suspend))))\n\n(defmethod init-from-entity! ((this lt-checkpoint) (arg0 entity-actor))\n  (set! (-> this root) (new (quote process) (quote trsqv)))\n  (process-drawable-from-entity! this arg0)\n  (set! (-> this cp-name)  (res-lump-struct arg0 (quote continue-name) string))\n  (set! (-> this radius)   (res-lump-float  arg0 (quote radius) :default 12288.0))\n  (set! (-> this use-vol)  (!= 0 (the int (res-lump-value arg0 (quote has-volume) uint128))))\n  (set! (-> this was-near) #f)\n  (let ((tag (new (quote static) (quote res-tag))))\n    (let ((data (res-lump-data arg0 (quote vol) (inline-array vector) :tag-ptr (& tag))))\n      (cond\n        (data\n         (set! (-> this planes) (the-as (inline-array vector) data))\n         (set! (-> this num-planes) (the-as int (-> tag elt-count))))\n        (else\n         (set! (-> this planes) (the-as (inline-array vector) #f))\n         (set! (-> this num-planes) 0)))))\n  (set! (-> this cull-radius)\n    (if (-> this use-vol)\n      (res-lump-float arg0 (quote cull-radius) :default 122880.0)\n      (* (-> this radius) 1.2)))\n  (format 0 "[lt-checkpoint] armed: ~A~%" (-> this cp-name))\n  (go lt-checkpoint-active)\n  (none))\n'

FILES = {"lt-checkpoint": LT_CHECKPOINT_GC}


def _write_if_changed(p, text):
    if p.exists() and p.read_text(encoding="utf-8") == text:
        return False
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    log(f"Wrote {p}")
    return True


def _patch(p, add_lines, before, label):
    """Add our tagged lines to a game file (once), before `before`."""
    raw = p.read_bytes()
    crlf = b"\r\n" in raw
    txt = raw.decode("utf-8").replace("\r\n", "\n")
    missing = [l for l in add_lines if l not in txt]
    if not missing:
        return False
    i = txt.rfind(before)
    if i < 0:
        log(f"WARNING: {p.name}: no '{before.strip()}' to add {label} before")
        return False
    txt = txt[:i] + "".join(l + "\n" for l in missing) + txt[i:]
    if crlf:
        txt = txt.replace("\n", "\r\n")
    p.write_bytes(txt.encode("utf-8"))
    log(f"Patched {p.name}: {label}")
    return True


# ── custom tasks: one-time engine changes (mod-base) ─────────────────────────
_FIX = ";; og-level-tools fix"
_TASK_H = ("engine", "game", "task", "game-task-h.gc")
_SAVE = ("engine", "game", "game-save.gc")

# game-save.gc: mod-base sizes the task arrays with (game-task max) but three
# spots still assume 116 tasks. Each pair is (original, fixed); a fixed line
# carries _FIX so it's only applied once.
_SAVE_FIXES = (
    # writing: the block after the fuel-cell times went at a fixed 928 (= 116 * 8)
    # bytes, over the times of tasks 116+; place it after the real block size
    ("(let ((v1-97 (&+ v1-96 928)))",
     f"(let ((v1-97 (&+ v1-96 (+ -16 (logand -16 (+ (* 8 (the int (game-task max))) 31)))))) {_FIX}: was 928"),
    # loading an older save shrank the task list for the session: keep it full
    ("(set! (-> this task-perm-list length) s3-4)",
     f"(set! (-> this task-perm-list length) (-> this task-perm-list allocated-length)) {_FIX}: was s3-4"),
)
# loading: only the first 32 fuel-cell times were read back (the one in the
# fuel-cell-time case; other 32s are per-level arrays and stay)
_FCT_OLD = """        (((game-save-elt fuel-cell-time))
         (let ((v1-92 (min 32 (-> data elt-count))))"""
_FCT_NEW = f"""        (((game-save-elt fuel-cell-time))
         (let ((v1-92 (min (the int (game-task max)) (-> data elt-count)))) {_FIX}: was 32"""


def _src(*parts):
    return _goal_src().joinpath(*parts)


def task_enum():
    """({name: id} of game-task-h.gc's enum without max, its max value)."""
    import re
    txt = _src(*_TASK_H).read_text(encoding="utf-8", errors="replace")
    ids = {m.group(1): int(m.group(2)) for m in re.finditer(r"^\s*\(([a-z0-9-]+)\s+(\d+)\)", txt, re.M)}
    mx = ids.pop("max", None)
    return ids, mx


def ensure_task_engine(need_max):
    """Raise (game-task max) to need_max (never lowers it, keeps other mods'
    entries) and fix game-save.gc for more than 116 tasks. Only writes what
    changed. Returns the changed file names."""
    import re
    changed = []
    p = _src(*_TASK_H)
    txt = p.read_text(encoding="utf-8")
    ids, mx = task_enum()
    want = max(int(need_max), (max(ids.values()) + 1) if ids else 0, mx or 0)
    m = re.search(r"\(max\s*(\d*)\)\)", txt)
    if m and (not m.group(1) or int(m.group(1)) != want):
        txt = txt[:m.start()] + f"(max {want}))" + txt[m.end():]
        _write_if_changed(p, txt) and changed.append(p.name)
    p = _src(*_SAVE)
    raw = p.read_bytes()
    crlf = b"\r\n" in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s0 = s
    for old, new in _SAVE_FIXES:
        if old in s and _FIX not in s.split(old)[1].split("\n", 1)[0]:
            s = s.replace(old, new, 1)
    if _FCT_OLD in s:
        s = s.replace(_FCT_OLD, _FCT_NEW, 1)
    if s != s0:
        if crlf:
            s = s.replace("\n", "\r\n")
        p.write_bytes(s.encode("utf-8"))
        log(f"Patched {p.name}: save fixes for more than 116 tasks")
        changed.append(p.name)
    return changed


def ensure_level_tools():
    """Write the shared lt-*.gc files and register them in game.gp / game.gd."""
    d = _goal_src() / LT_DIR
    for name, text in FILES.items():
        _write_if_changed(d / f"{name}.gc", text)
    gp = _game_gp()
    if gp.exists():
        _patch(gp, [f'(goal-src "{LT_DIR}/{n}.gc" "process-drawable") {_TAG}' for n in FILES],
               '(group-list "all-code"', "level-tools goal-src")
    gd = _goal_src() / "dgos" / "game.gd"
    if gd.exists():
        _patch(gd, [f'  "{n}.o" {_TAG.replace(";", ";;", 1)}' for n in FILES], " ))", "level-tools objects")
