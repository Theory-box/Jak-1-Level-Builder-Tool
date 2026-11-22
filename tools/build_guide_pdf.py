"""Build the user guide (docs/guide/*.md) into one PDF, with working links between pages and the pictures.

    python tools/build_guide_pdf.py [out.pdf] [--html out.html] [--chrome PATH]

No extra Python packages: a small Markdown converter for what the guide uses (headings, paragraphs, lists,
tables, quotes, code, links, images), then Chrome / Chromium / Edge prints the page to PDF (headless).
Pages come in the order of the guide index (docs/guide/README.md). Links to other guide pages become links inside
the PDF; links outside the guide point at GitHub. Run by .github/workflows/guide-pdf.yml for every release.
"""
from __future__ import annotations

import base64
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "docs" / "guide"
REPO_URL = "https://github.com/Theory-box/Jak-1-Level-Builder-Tool/blob/main/"


# ── Markdown (the subset the guide uses) ────────────────────────────────────────

def slug(text: str) -> str:
    """GitHub's heading anchor."""
    s = re.sub(r"<[^>]+>", "", text).strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


class Page:
    def __init__(self, name: str):
        self.name = name                 # "levels" (file without .md)

    def anchor(self, a: str = "") -> str:
        return f"{self.name}--{a}" if a else self.name

    def link(self, url: str) -> str:
        """Guide page links -> anchors inside the PDF; everything else -> absolute URLs."""
        if re.match(r"^[a-z]+:", url):
            return url
        path, _, frag = url.partition("#")
        if not path:
            return "#" + self.anchor(frag)
        if path.endswith(".md") and "/" not in path:
            return "#" + Page(path[:-3]).anchor(frag) if path != "README.md" else "#guide-index"
        full = os.path.normpath(os.path.join("docs/guide", path)).replace("\\", "/")
        return REPO_URL + full + (f"#{frag}" if frag else "")


def inline(text: str, page: Page) -> str:
    codes = []

    def keep_code(m):
        codes.append("<code>" + html.escape(m.group(1)) + "</code>")
        return f"\x00{len(codes) - 1}\x00"
    text = re.sub(r"`([^`]+)`", keep_code, text)
    text = html.escape(text, quote=False).replace("&amp;lt;", "&lt;").replace("&amp;gt;", "&gt;") \
        .replace("&amp;nbsp;", "&nbsp;").replace("&amp;amp;", "&amp;")

    def image(m):
        src = m.group(2)
        f = (GUIDE / src)
        if f.exists():
            data = base64.b64encode(f.read_bytes()).decode()
            src = f"data:image/png;base64,{data}"
        return f'<img alt="{m.group(1)}" src="{src}">'
    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", image, text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{page.link(html.unescape(m.group(2)))}">{m.group(1)}</a>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text, flags=re.S)    # may wrap over lines
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text, flags=re.S)
    text = re.sub(r"  $", "<br>", text, flags=re.M)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)


def _table(lines, page):
    rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in lines]
    head, body = rows[0], rows[2:]
    out = ["<table><thead><tr>" + "".join(f"<th>{inline(c, page)}</th>" for c in head) + "</tr></thead><tbody>"]
    for r in body:
        out.append("<tr>" + "".join(f"<td>{inline(c, page)}</td>" for c in r) + "</tr>")
    return "\n".join(out) + "</tbody></table>"


def _list(lines, page):
    """Nested lists from indentation."""
    items = []                   # [indent, tag, text]; continuation lines join their item
    for l in lines:
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", l)
        if m:
            items.append([len(m.group(1)), "ol" if m.group(2)[0].isdigit() else "ul", m.group(3)])
        elif items:
            items[-1][2] += "\n" + l.strip()
    out, stack = [], []          # stack of (indent, tag)
    for ind, tag, text in items:
        while stack and ind < stack[-1][0]:
            out.append(f"</li></{stack.pop()[1]}>")
        if not stack or ind > stack[-1][0]:
            out.append(f"<{tag}>"); stack.append((ind, tag))
        else:
            out.append("</li>")
        out.append("<li>" + inline(text, page))
    while stack:
        out.append(f"</li></{stack.pop()[1]}>")
    return "".join(out)


def convert(md: str, page: Page) -> str:
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    lines = md.split("\n")
    out, i = [], 0
    while i < len(lines):
        l = lines[i]
        if not l.strip():
            i += 1; continue
        if l.startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            out.append("<pre><code>" + html.escape("\n".join(lines[i + 1:j])) + "</code></pre>")
            i = j + 1; continue
        m = re.match(r"^(#{1,6})\s+(.*)$", l)
        if m:
            n, t = len(m.group(1)), m.group(2).strip()
            out.append(f'<h{n} id="{page.anchor(slug(t))}">{inline(t, page)}</h{n}>')
            i += 1; continue
        if re.match(r"^\s*(---|\*\*\*)\s*$", l):
            out.append("<hr>"); i += 1; continue
        if l.lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            j = i
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                j += 1
            out.append(_table(lines[i:j], page)); i = j; continue
        if l.startswith(">"):
            j = i
            while j < len(lines) and lines[j].startswith(">"):
                j += 1
            inner = "\n".join(x[1:].lstrip() if x.startswith("> ") or x == ">" else x[1:] for x in lines[i:j])
            out.append("<blockquote>" + convert(inner, page) + "</blockquote>"); i = j; continue
        if re.match(r"^\s*([-*]|\d+\.)\s+", l):
            j = i + 1
            while j < len(lines) and lines[j].strip() and not lines[j].startswith(("#", "|", ">")):
                j += 1
            out.append(_list(lines[i:j], page)); i = j; continue
        j = i + 1
        while j < len(lines) and lines[j].strip() and not re.match(r"^(#|\s*([-*]|\d+\.)\s|\||>|```)", lines[j]):
            j += 1
        out.append("<p>" + inline("\n".join(lines[i:j]), page) + "</p>")
        i = j
    return "\n".join(out)


# ── the guide ─────────────────────────────────────────────────────────────────

def page_order():
    """The pages linked from the guide index, in order."""
    idx = (GUIDE / "README.md").read_text(encoding="utf-8")
    seen = []
    for f in re.findall(r"\]\(([\w-]+\.md)(?:#[^)]*)?\)", idx):
        if f != "README.md" and f not in seen and (GUIDE / f).exists():
            seen.append(f)
    return seen


def strip_nav(md: str) -> str:
    """Drop the per-page navigation (top index link, bottom previous / next line)."""
    md = re.sub(r"^\[↑[^\n]*\n+", "", md)
    md = re.sub(r"\n-{3,}\s*\n\[← Previous\][^\n]*\s*$", "\n", md)
    md = re.sub(r"\n\[← Previous\][^\n]*\s*$", "\n", md)
    return md


CSS = """
@page { size: A4; margin: 16mm 14mm; }
body { font-family: "Segoe UI", "DejaVu Sans", Arial, sans-serif; font-size: 10.5pt; line-height: 1.45; color: #1f2328; }
h1 { font-size: 22pt; border-bottom: 2px solid #d0d7de; padding-bottom: 4px; margin-top: 0; }
h2 { font-size: 15pt; border-bottom: 1px solid #d0d7de; padding-bottom: 2px; margin-top: 1.4em; }
h3 { font-size: 12.5pt; margin-top: 1.2em; } h4 { font-size: 11pt; }
h2, h3, h4 { break-after: avoid; }
section.page { break-before: page; }
a { color: #0969da; text-decoration: none; }
code { font-family: Consolas, "DejaVu Sans Mono", monospace; font-size: 9pt; background: #eff1f3; padding: 1px 4px; border-radius: 4px; }
pre { background: #f6f8fa; padding: 8px 10px; border-radius: 6px; white-space: pre-wrap; break-inside: avoid; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; margin: 8px 0; width: 100%; font-size: 9.5pt; }
th, td { border: 1px solid #d0d7de; padding: 4px 7px; vertical-align: top; text-align: left; }
th { background: #f6f8fa; } tr { break-inside: avoid; }
blockquote { margin: 8px 0; padding: 4px 12px; border-left: 4px solid #d0d7de; color: #444; background: #fafbfc; }
img { max-width: 100%; max-height: 220mm; display: block; margin: 8px 0; break-inside: avoid; }
.cover { text-align: center; padding-top: 70mm; }
.cover h1 { border: none; font-size: 30pt; }
.cover p { font-size: 13pt; color: #555; }
"""


def build_html(version: str = "") -> str:
    parts = [f'<div class="cover"><h1>OpenGOAL Level Tools</h1><p>User Guide{(" — " + version) if version else ""}</p>'
             f'<p><a href="https://github.com/Theory-box/Jak-1-Level-Builder-Tool">github.com/Theory-box/Jak-1-Level-Builder-Tool</a></p></div>']
    idx = strip_nav((GUIDE / "README.md").read_text(encoding="utf-8"))
    parts.append('<section class="page" id="guide-index">' + convert(idx, Page("README")) + "</section>")
    for f in page_order():
        p = Page(f[:-3])
        body = convert(strip_nav((GUIDE / f).read_text(encoding="utf-8")), p)
        parts.append(f'<section class="page" id="{p.anchor()}">{body}</section>')
    return ("<!DOCTYPE html><html><head><meta charset='utf-8'><title>OpenGOAL Level Tools — User Guide</title>"
            f"<style>{CSS}</style></head><body>" + "\n".join(parts) + "</body></html>")


def find_chrome(given=None):
    cands = [given] if given else []
    cands += [shutil.which(n) for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                                        "chrome", "msedge")]
    cands += [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    return next((c for c in cands if c and Path(c).exists()), None)


def main(argv):
    out = Path(argv[0]) if argv and not argv[0].startswith("--") else ROOT / "OpenGOAL-Level-Tools-Guide.pdf"
    opts = dict(zip(argv[::1], argv[1::1]))
    version = opts.get("--version", "")
    doc = build_html(version)
    if "--html" in opts:
        Path(opts["--html"]).write_text(doc, encoding="utf-8")
    chrome = find_chrome(opts.get("--chrome"))
    if chrome is None:
        sys.exit("Chrome / Chromium / Edge not found (use --chrome PATH)")
    with tempfile.TemporaryDirectory() as td:
        h = Path(td) / "guide.html"
        h.write_text(doc, encoding="utf-8")
        cmd = [chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
               f"--user-data-dir={Path(td) / 'profile'}", f"--print-to-pdf={out.resolve()}", h.resolve().as_uri()]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    if not out.exists() or out.stat().st_size < 10000:
        sys.exit(f"PDF not written: {out}")
    print(f"{out} ({out.stat().st_size // 1024} KB, {len(page_order()) + 1} pages of the guide)")


if __name__ == "__main__":
    main(sys.argv[1:])
