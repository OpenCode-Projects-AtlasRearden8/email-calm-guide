#!/usr/bin/env python3
"""Email Calm Guide site builder.

Turns docs/ markdown plus templates/replies/ into a static HTML site
in site/. Standard library only: no network, no API keys, no
dependencies, and no timestamps in the output (rebuilds are identical).

    python3 build.py            build the site into site/
    python3 build.py --out DIR  build somewhere else
    python3 build.py --serve    build, then preview at localhost
"""

import argparse
import functools
import html
import http.server
import re
import shutil
import socketserver
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
REPLIES = ROOT / "templates" / "replies"
ASSETS = ROOT / "assets"
DEFAULT_OUT = ROOT / "site"

SITE_TITLE = "Email Calm Guide"
SITE_TAGLINE = "A friend-style manual for inbox dread"
FOOTER = (
    "Made by Asdale Dynamics, LLC. MIT licensed."
    " No accounts, no keys, no trackers; works offline."
)
FAVICON = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E"
    "%3Crect width='100' height='100' rx='18' fill='%230b7285'/%3E"
    "%3Cpath d='M20 32h60v36H20z' fill='none' stroke='%23fbf9f6' stroke-width='7'/%3E"
    "%3Cpath d='M20 36l30 22 30-22' fill='none' stroke='%23fbf9f6' stroke-width='7'/%3E"
    "%3C/svg%3E"
)

COPY_SCRIPT = """
document.addEventListener('click', function (e) {
  var btn = e.target.closest('.copy-btn');
  if (!btn) { return; }
  var host = document.querySelector(btn.getAttribute('data-copy'));
  var text = host ? host.textContent : '';
  function done() {
    btn.textContent = 'Copied';
    setTimeout(function () { btn.textContent = 'Copy template'; }, 1600);
  }
  function fallback() {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (err) {}
    document.body.removeChild(ta);
    return ok;
  }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done, function () {
      if (fallback()) { done(); }
    });
  } else if (fallback()) { done(); }
});
"""


# --------------------------------------------------------------------------
# tiny markdown renderer (exactly the subset this manual uses)
# --------------------------------------------------------------------------

BLANK_RE = re.compile(r"(?<![\w\\])__([^_]+?)__(?![\w\\])")
CODE_RE = re.compile(r"`([^`]+)`")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
ITALIC_RE = re.compile(r"(?<![\w*])\*([^*\n]+?)\*(?![\w*])")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^()\s]+)\)")
TASK_RE = re.compile(r"^(\s*)[-*]\s+\[([ xX])\]\s+(.*)$")
ULEX = re.compile(r"^(\s*)[-*]\s+(.*)$")
OLEX = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")
HEAD_RE = re.compile(r"^(#{1,6})\s+(.*)$")
FENCE_RE = re.compile(r"^```\s*([A-Za-z0-9_+-]*)\s*$")
HR_RE = re.compile(r"^ {0,3}(?:-{3,}|\*{3,}|_{3,})\s*$")
SEP_RE = re.compile(r"^ {0,3}\|?\s*:?-{3,}[\s:|-]*\|?\s*$")


def slugify(text, taken):
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "page"
    base = slug
    n = 2
    while slug in taken:
        slug = "%s-%d" % (base, n)
        n += 1
    taken.add(slug)
    return slug


class MiniMD:
    """Markdown -> HTML for the subset used across docs/ and templates/."""

    def __init__(self, href_rewriter=None):
        self.rewrite = href_rewriter
        self.slugs = set()

    # -- inline ----------------------------------------------------------
    def inline(self, text):
        text = html.escape(text, quote=True)
        stash = []

        def _keep_code(m):
            stash.append("<code>%s</code>" % m.group(1))
            return "\x00%d\x00" % (len(stash) - 1)

        text = CODE_RE.sub(_keep_code, text)

        def _keep_link(m):
            inner = self.styles(m.group(1))
            stash.append('<a href="%s">%s</a>' % (self._rewrite(m.group(2)), inner))
            return "\x00%d\x00" % (len(stash) - 1)

        text = LINK_RE.sub(_keep_link, text)
        text = self.styles(text)
        return self._restore(text, stash)

    def styles(self, text):
        """Blanks, bold, italic on already-escaped text (no links, no code)."""
        text = BLANK_RE.sub(
            lambda m: '<span class="fill">%s</span>' % m.group(1), text
        )
        text = BOLD_RE.sub(lambda m: "<strong>%s</strong>" % m.group(1), text)
        text = ITALIC_RE.sub(lambda m: "<em>%s</em>" % m.group(1), text)
        return text

    def _restore(self, text, stash):
        def _put(m):
            i = int(m.group(1))
            if 0 <= i < len(stash):
                return stash[i]
            return m.group(0)

        return re.sub("\x00(\\d+)\x00", _put, text)

    def _rewrite(self, target):
        if target.startswith("#") or "://" in target or target.startswith("mailto:"):
            return html.escape(target, quote=True)
        if self.rewrite:
            target = self.rewrite(target)
        return html.escape(target, quote=True)

    # -- blocks ------------------------------------------------------------
    def render(self, source):
        lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        out = []
        i = 0
        n = len(lines)
        while i < n:
            line = lines[i]
            if not line.strip():
                i += 1
                continue
            fence = FENCE_RE.match(line)
            if fence:
                lang, body, i = self._read_fence(lines, i)
                out.append(self._code_block(body, lang))
                continue
            if HR_RE.match(line):
                out.append('<hr class="rule">')
                i += 1
                continue
            head = HEAD_RE.match(line)
            if head:
                level = len(head.group(1))
                title = head.group(2).strip()
                hid = slugify(title, self.slugs)
                out.append(
                    '<h%d id="%s">%s</h%d>'
                    % (level, hid, self.inline(title), level)
                )
                i += 1
                continue
            if (
                i + 1 < n
                and line.strip().startswith("|")
                and SEP_RE.match(lines[i + 1])
            ):
                rows, i = self._read_table(lines, i)
                out.append(self._table(rows))
                continue
            if line.lstrip().startswith(">"):
                block, i = self._read_quote(lines, i)
                out.append("<blockquote>%s</blockquote>" % self.render("\n".join(block)))
                continue
            if TASK_RE.match(line) or ULEX.match(line) or OLEX.match(line):
                block, i = self._read_list(lines, i)
                out.append(block)
                continue
            para, i = self._read_paragraph(lines, i)
            out.append("<p>%s</p>" % self.inline(para))
        return "\n".join(out)

    def _read_fence(self, lines, i):
        lang = FENCE_RE.match(lines[i]).group(1) or "text"
        i += 1
        body = []
        while i < len(lines) and not lines[i].startswith("```"):
            body.append(lines[i])
            i += 1
        i += 1  # step past the closing fence (or EOF)
        return lang, body, i

    def _code_block(self, body, lang):
        text = html.escape("\n".join(body), quote=False)
        cls = ""
        if lang and lang != "text":
            cls = ' class="lang-%s"' % html.escape(lang, quote=True)
        return "<pre><code%s>%s</code></pre>" % (cls, text)

    def _read_table(self, lines, i):
        rows = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            rows.append(self._split_row(lines[i]))
            i += 1
        return rows, i

    def _split_row(self, line):
        raw = line.strip()
        if raw.startswith("|"):
            raw = raw[1:]
        if raw.endswith("|"):
            raw = raw[:-1]
        cells = [c.strip() for c in raw.split("|")]
        if cells and cells[-1] == "":
            cells.pop()
        return cells

    def _table(self, rows):
        # drop separator rows like | --- | --- | that GFM puts after the header
        body_rows = [r for r in rows[1:] if not all(re.match(r"^:?-+:?$", c) for c in r)]
        rows = [r for r in rows if r]
        if not rows:
            return '<div class="tablewrap"><table></table></div>'
        out = ['<div class="tablewrap"><table>']
        head = "<tr>%s</tr>" % "".join(
            "<th>%s</th>" % self.styles(c) for c in rows[0]
        )
        out.append("<thead>%s</thead>" % head)
        out.append("<tbody>")
        for r in body_rows:
            out.append("<tr>%s</tr>" % "".join("<td>%s</td>" % self.styles(c) for c in r))
        out.append("</tbody>")
        out.append("</table></div>")
        return "\n".join(out)

    def _read_quote(self, lines, i):
        block = []
        while i < len(lines) and lines[i].lstrip().startswith(">"):
            strip = lines[i].lstrip()
            block.append(strip[1:].strip())
            i += 1
        return block, i

    def _collect_list_items(self, lines, i):
        items = []
        while i < len(lines):
            m = TASK_RE.match(lines[i])
            if m:
                items.append((len(m.group(1)), "task", m.group(3), m.group(2).lower() == "x"))
                i += 1
                continue
            m = ULEX.match(lines[i])
            if m:
                items.append((len(m.group(1)), "ul", m.group(2), None))
                i += 1
                continue
            m = OLEX.match(lines[i])
            if m:
                items.append((len(m.group(1)), "ol", m.group(3), None))
                i += 1
                continue
            break
        return items, i

    def _read_list(self, lines, i):
        items, i = self._collect_list_items(lines, i)
        if not items:
            return "", i
        htmlout, _pos = self._lists_build(items, 0, items[0][0])
        return htmlout, i

    def _lists_build(self, items, pos, depth):
        """Render consecutive items at exactly `depth` as one list."""
        kind = items[pos][1]
        tag = "ol" if kind == "ol" else "ul"
        out = ["<%s>" % tag]
        while pos < len(items) and items[pos][0] >= depth:
            level, ikind, text, done = items[pos]
            if level == depth:
                if ikind == "task":
                    box = '<input type="checkbox"%s aria-label="task">' % (
                        " checked" if done else ""
                    )
                    out.append('<li class="task">%s%s' % (box, self.inline(text)))
                else:
                    out.append("<li>%s" % self.inline(text))
                pos += 1
                if pos < len(items) and items[pos][0] > depth:
                    nested, pos = self._lists_build(items, pos, depth + 1)
                    out[-1] += nested
                out.append("</li>")
            else:
                nested, pos = self._lists_build(items, pos, depth + 1)
                out.append(nested)
        out.append("</%s>" % tag)
        return "".join(out), pos

    def _read_paragraph(self, lines, i):
        para = [lines[i].strip()]
        i += 1
        while i < len(lines):
            s = lines[i]
            if (
                not s.strip()
                or HEAD_RE.match(s)
                or FENCE_RE.match(s)
                or HR_RE.match(s)
                or s.strip().startswith("|")
                or s.lstrip().startswith(">")
                or TASK_RE.match(s)
                or ULEX.match(s)
                or OLEX.match(s)
            ):
                break
            para.append(s.strip())
            i += 1
        return " ".join(para), i


# --------------------------------------------------------------------------
# templates (fill-in reply scripts)
# --------------------------------------------------------------------------

FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def parse_template(text):
    """Return (fields dict from --- front matter, raw template body)."""
    fields = {}
    body = text
    m = FRONT_RE.match(text)
    if m:
        for line in m.group(1).split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                fields[key.strip().lower()] = val.strip()
        body = text[m.end():]
    return fields, body.strip("\n")


def template_copy_text(fields, body):
    """Exactly what 'Copy template' should put on the clipboard."""
    subject = fields.get("subject", "").strip()
    copy = ""
    if subject:
        copy += "Subject: %s\n\n" % subject
    copy += body + "\n"
    return copy


# --------------------------------------------------------------------------
# site assembly
# --------------------------------------------------------------------------

def doc_href(target):
    """Rewrite links between docs pages into links between built pages."""
    if "://" in target or target.startswith("#") or target.startswith("mailto:"):
        return target
    path = target.split("#")[0]
    if path.endswith(".md"):
        base = path[:-3]
        if base == "00-start-here":
            return "index.html"
        return base + ".html"
    return target


def doc_title(source, fallback):
    for line in source.replace("\r\n", "\n").split("\n"):
        m = HEAD_RE.match(line)
        if m:
            return m.group(2).strip()
    return fallback


def page_name(mdpath):
    if mdpath.stem == "00-start-here":
        return "index.html"
    return mdpath.stem + ".html"


NAV_TEMPLATES_LABEL = "Template library"
NAV_TEMPLATES_HREF = "templates.html"


def site_nav(html_pages):
    """[(label, href)] for every built page, in reading order."""
    nav = [(title, outname) for _stem, title, outname in html_pages]
    nav.append((NAV_TEMPLATES_LABEL, NAV_TEMPLATES_HREF))
    return nav


def page_html(title, body, nav, current, description, script=""):
    items = []
    for i, (label, href) in enumerate(nav):
        here = ""
        if i == current:
            here = ' class="here" aria-current="page"'
        items.append(
            '<li><a%s href="%s">%s</a></li>'
            % (here, html.escape(href, quote=True), html.escape(label))
        )
    nav_html = "\n".join(items)

    prev = nav[current - 1] if current > 0 else None
    nxt = nav[current + 1] if current < len(nav) - 1 else None
    links = []
    if prev:
        links.append(
            '<a class="pnav-prev" href="%s">&larr; %s</a>'
            % (html.escape(prev[1], quote=True), html.escape("Previous: " + prev[0]))
        )
    if nxt:
        links.append(
            '<a class="pnav-next" href="%s">%s &rarr;</a>'
            % (html.escape(nxt[1], quote=True), html.escape("Next: " + nxt[0]))
        )
    pnav = "\n".join(links)
    if pnav:
        pnav = '<nav class="pnav" aria-label="Adjacent pages">%s</nav>' % pnav

    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{description}">
<meta name="generator" content="build.py">
<link rel="stylesheet" href="style.css">
<link rel="icon" href="{favicon}">
<title>{title} &middot; {site_title}</title>
</head>
<body>
<input id="nav-toggle" class="nav-toggle" type="checkbox" tabindex="-1" aria-hidden="true">
<div class="wrap">
<header class="masthead">
  <p class="brand"><a href="index.html">{site_title}</a><span class="tagline">{tagline}</span></p>
  <label class="menu" for="nav-toggle">Menu</label>
</header>
<div class="layout">
<nav class="chapternav" aria-label="Chapters">
<ol>
{nav_html}
</ol>
</nav>
<main class="content" id="main">
{body}
{pnav}
</main>
</div>
<footer class="pagefoot">
<p>{footer}</p>
<p><a href="index.html">Start here</a> &middot; <a href="templates.html">Template library</a></p>
</footer>
</div>
{script}
</body>
</html>
""".format(
        title=html.escape(title),
        site_title=html.escape(SITE_TITLE),
        tagline=html.escape(SITE_TAGLINE),
        description=html.escape(description, quote=True),
        favicon=FAVICON,
        nav_html=nav_html,
        body=body,
        pnav=pnav,
        footer=FOOTER,
        script=('<script>%s</script>' % COPY_SCRIPT) if script else "",
    )


def drop_stale_html(out_dir, expected):
    """Remove .html files in out_dir we didn't (re)build, so rebuilds don't accumulate litter."""
    removed = []
    for f in sorted(out_dir.glob("*.html")):
        if f.name not in expected:
            f.unlink()
            removed.append(f.name)
    return removed


def meta_description(source):
    desc = ""
    seen_h1 = False
    for line in source.replace("\r\n", "\n").split("\n"):
        if HEAD_RE.match(line):
            if line.lstrip().startswith("# "):
                seen_h1 = True
            continue
        if seen_h1 and line.strip():
            desc = line.strip()
            break
    text = CODE_RE.sub(lambda m: m.group(1), desc)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^()\s]+\)", r"\1", text)
    text = re.sub(r"[*_]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 150:
        text = text[:147].rstrip() + "..."
    return text


def build_template_section(stem, idx):
    """html (section only) for one template file."""
    raw = (REPLIES / stem).read_text(encoding="utf-8")
    fields, body = parse_template(raw)
    name = fields.get("name", stem.rsplit(".", 1)[0].replace("-", " "))
    when = fields.get("when", "")
    tone = fields.get("tone", "")
    subject = fields.get("subject", "")
    md = MiniMD()
    slug = slugify(name, set())
    copy_id = "copy-%d" % idx
    bodyh = md.render(body)
    subjecth = md.inline(subject) if subject else ""
    parts = ['<section class="tpl" id="tpl-%s">' % slug]
    parts.append("<h2>%s</h2>" % md.inline(name))
    if when:
        parts.append('<p class="tpl-meta"><strong>Use when:</strong> %s</p>' % md.inline(when))
    if tone:
        parts.append('<p class="tpl-meta"><strong>Tone:</strong> %s</p>' % md.inline(tone))
    if subject:
        parts.append('<p class="tpl-meta tpl-subject"><strong>Subject:</strong> %s</p>' % subjecth)
    parts.append('<div class="tpl-body">%s</div>' % bodyh)
    parts.append(
        '<div class="tpl-actions"><button class="copy-btn" data-copy="#%s" type="button">Copy template</button></div>'
        % copy_id
    )
    raw_text = template_copy_text(fields, body)
    parts.append(
        '<script type="text/plain" class="tpl-raw" id="%s">%s</script>'
        % (copy_id, raw_text)
    )
    parts.append("</section>")
    return "\n".join(parts)


def templates_intro(count):
    return (
        "<h1>Template library</h1>\n"
        "<p>%d fill-in reply scripts, from &ldquo;yes&rdquo; to &ldquo;out of office&rdquo;. "
        "Every <span class=\"fill\">yellow blank</span> is yours to fill in. "
        "Pick one, copy it, trim it, send it &mdash; a 30-second reply beats a perfect one you never send.</p>\n"
        "<p>The copy buttons work locally on your machine: nothing is sent anywhere. "
        "Print this page if it helps; the blanks read like a paper form.</p>" % count
    )


def build_templates_page(nav):
    if not REPLIES.is_dir():
        raise SystemExit("missing templates folder: %s" % REPLIES)
    files = sorted(p.name for p in REPLIES.glob("*.md"))
    sections = [build_template_section(name, idx) for idx, name in enumerate(files, start=1)]
    body = templates_intro(len(files)) + "\n\n" + "\n\n".join(sections)
    current = len(nav) - 1
    return page_html(
        NAV_TEMPLATES_LABEL,
        body,
        nav,
        current,
        "%d fill-in replies for awkward emails: yes, not now, a kind no, "
        "checking in, out of office, and more. Local only; nothing is sent anywhere." % len(files),
        script=COPY_SCRIPT,
    )


def build_site(out_dir=DEFAULT_OUT):
    if not DOCS.is_dir():
        raise SystemExit("missing docs folder: %s" % DOCS)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    md_files = sorted(DOCS.glob("*.md"))
    pages = []
    for p in md_files:
        source = p.read_text(encoding="utf-8")
        title = doc_title(source, p.stem.replace("-", " "))
        pages.append((p.stem, title, page_name(p)))

    nav = site_nav([(s, t, h) for s, t, h in pages])
    expected = {h for (_s, _t, h) in pages} | {NAV_TEMPLATES_HREF}
    for idx, (stem, title, outname) in enumerate(pages):
        source = (DOCS / (stem + ".md")).read_text(encoding="utf-8")
        md = MiniMD(href_rewriter=doc_href)
        body = md.render(source)
        out_html = page_html(
            title,
            body,
            nav,
            idx,
            meta_description(source),
        )
        (out_dir / outname).write_text(out_html, encoding="utf-8")

    (out_dir / NAV_TEMPLATES_HREF).write_text(build_templates_page(nav), encoding="utf-8")

    css = ASSETS / "style.css"
    if css.exists():
        shutil.copyfile(css, out_dir / "style.css")

    drop_stale_html(out_dir, expected)

    template_files = sorted(p.name for p in REPLIES.glob("*.md"))
    return {
        "pages": len(pages),
        "outputs": len(expected),
        "templates": len(template_files),
    }


def serve_site(out_dir, port=8000):
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(out_dir)
    )
    print("Preview running at http://127.0.0.1:%d/ (Ctrl+C stops)" % port)
    print("Nothing is published; this only serves one folder on this machine.")
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nPreview stopped.")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Build the Email Calm Guide static site from docs/."
    )
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="output folder (default: site)")
    ap.add_argument(
        "--serve",
        nargs="?",
        const=8000,
        default=None,
        type=int,
        metavar="PORT",
        help="after building, preview locally on this port",
    )
    args = ap.parse_args(argv)
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    summary = build_site(out_dir)
    print(
        "Built %d manual pages + %d templates into %s (%d html files)"
        % (summary["pages"], summary["templates"], out_dir, summary["outputs"])
    )
    if args.serve is not None:
        serve_site(out_dir, args.serve)
    return 0


if __name__ == "__main__":
    sys.exit(main())
