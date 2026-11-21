# ───────────────────────────────────────────────────────────────────────
# export/fileio.py — OpenGOAL Level Tools
# Writing the game's text files: only when the content changed (an
# unchanged file keeps its date, so (mi) doesn't recompile it), keeping a
# file's own line ends (the game's files can be CRLF on Windows).
# ───────────────────────────────────────────────────────────────────────
from __future__ import annotations

from .paths import log


def write_if_changed(p, text, wrote=None, skipped="") -> bool:
    """Write a UTF-8 text file only when its content differs. Logs `wrote`
    (default "Wrote <path>") / `skipped` ("" = nothing). True if written."""
    if p.exists() and p.read_text(encoding="utf-8") == text:
        if skipped:
            log(skipped)
        return False
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    log(f"Wrote {p}" if wrote is None else wrote)
    return True


def rewrite(path, fn, wrote=None) -> bool:
    """Apply fn(text) to a text file (LF inside, its own line ends kept) and
    write it back if that changed it; logs `wrote` when given. False when
    the file doesn't exist."""
    if not path.exists():
        return False
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    new = fn(raw.decode("utf-8").replace("\r\n", "\n"))
    if crlf:
        new = new.replace("\n", "\r\n")
    out = new.encode("utf-8")
    if out == raw:
        return False
    path.write_bytes(out)
    if wrote:
        log(wrote)
    return True


def patch(p, add_lines, before, label) -> bool:
    """Add our tagged lines to a game file (once), before the last `before`."""
    def fn(txt):
        missing = [l for l in add_lines if l not in txt]
        if not missing:
            return txt
        i = txt.rfind(before)
        if i < 0:
            log(f"WARNING: {p.name}: no '{before.strip()}' to add {label} before")
            return txt
        return txt[:i] + "".join(l + "\n" for l in missing) + txt[i:]
    return rewrite(p, fn, f"Patched {p.name}: {label}")
