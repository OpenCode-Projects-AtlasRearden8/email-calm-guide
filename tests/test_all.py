#!/usr/bin/env python3
"""Tests for the Email Calm Guide repo.

Run:  python3 tests/test_all.py            (or: python3 -m unittest discover -s tests)

Checks five things, roughly in order of importance:
  1. the build works (subprocess, fresh temp dir) and pages look right
  2. the committed site/ is exactly what a fresh build produces
  3. the markdown renderer handles what docs/ and templates/ use
  4. every reply template is parseable and has fill-in blanks
  5. repo hygiene: no secrets, license line exact, internal links resolve
"""

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import build  # noqa: E402

DOCS = ROOT / "docs"
REPLIES = ROOT / "templates" / "replies"
SITE = ROOT / "site"
LICENSE = ROOT / "LICENSE"
README = ROOT / "README.md"
STATUS = ROOT / "STATUS.md"


def build_to(tmpdir):
    """Run build.py as a subprocess (mimics a real user build) and return the dir."""
    out = Path(tmpdir) / "built"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "build.py"), "--out", str(out)],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        raise AssertionError("build.py failed:\n%s\n%s" % (proc.stdout, proc.stderr))
    return out


def read(p):
    return Path(p).read_text(encoding="utf-8")


class TestBuild(unittest.TestCase):
    def test_subprocess_build_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = build_to(tmp)
            pages = sorted(p.name for p in out.glob("*.html"))
            self.assertIn("index.html", pages)
            self.assertIn("templates.html", pages)
            self.assertGreaterEqual(len(pages), 14, "expected 13 chapters + library")
            self.assertTrue((out / "style.css").exists())

    def test_every_doc_page_has_chrome(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = build_to(tmp)
            for p in DOCS.glob("*.md"):
                name = "index.html" if p.stem == "00-start-here" else p.stem + ".html"
                text = read(out / name)
                self.assertIn("<html lang=\"en\">", text, name)
                self.assertIn('class="chapternav"', text, name)
                self.assertTrue(text.count('aria-current="page"') == 1, name)
                self.assertIn("Asdale Dynamics, LLC", text, name)
                self.assertIn("Template library", text, name)

    def test_nav_lists_all_pages_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = build_to(tmp)
            home = read(out / "index.html")
            pos = {n: home.find(n) for n in (
                "01-why-email-feels-so-heavy.html",
                "02-the-three-folder-system.html",
                "templates.html",
            )}
            self.assertGreater(pos["02-the-three-folder-system.html"], -1)
            self.assertLess(pos["01-why-email-feels-so-heavy.html"],
                            pos["02-the-three-folder-system.html"])
            self.assertLess(pos["02-the-three-folder-system.html"], pos["templates.html"])

    def test_current_page_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = build_to(tmp)
            text = read(out / "index.html")
            self.assertEqual(text.count('class="here"'), 1)
            self.assertEqual(text.count('aria-current="page"'), 1)

    def test_templates_page_lists_all_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = build_to(tmp)
            text = read(out / "templates.html")
            for f in sorted(REPLIES.glob("*.md")):
                fields, _ = build.parse_template(read(f))
                name = fields.get("name", "")
                self.assertTrue(name, "%s missing name" % f.name)
                # count matters: names can repeat legitimately ("Re:"), so check once
                self.assertIn(name, text, "%s not on templates page" % f.name)
            self.assertIn("copy-btn", text)
            self.assertIn("Copy template", text)

    def test_deterministic_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = build_to(tmp)
            b = build_to(tmp)  # second build into a fresh dir
            names_a = sorted(p.name for p in a.iterdir())
            names_b = sorted(p.name for p in b.iterdir())
            self.assertEqual(names_a, names_b)
            for name in names_a:
                self.assertEqual(
                    read(a / name), read(b / name), "nondeterministic output: %s" % name
                )

    @unittest.skipUnless(SITE.is_dir(), "site/ not present yet")
    def test_committed_site_is_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            fresh = build_to(tmp)
            a = sorted((p.name, read(p)) for p in fresh.iterdir())
            b = sorted((p.name, read(SITE / p)) for p in SITE.iterdir())
            self.assertEqual([n for n, _t in a], [n for n, _t in b],
                             "site/ file list out of date: rebuild with `python3 build.py`")
            for (na, ta), (nb, tb) in zip(a, b):
                self.assertEqual(na, nb)
                self.assertEqual(ta, tb, "site/%s differs from a fresh build" % na)


class TestMiniMD(unittest.TestCase):
    def setUp(self):
        self.md = build.MiniMD()

    def test_heading(self):
        h = self.md.render("# Hello there\n\nBody.")
        self.assertIn('<h1 id="hello-there">', h)
        self.assertIn("<p>Body.</p>", h)

    def test_inline_styles(self):
        i = self.md.inline("A **bold** and *soft* and `code hold`.")
        self.assertIn("<strong>bold</strong>", i)
        self.assertIn("<em>soft</em>", i)
        self.assertIn("<code>code hold</code>", i)

    def test_code_span_protects_markers(self):
        i = self.md.inline("keep `__this__` raw-ish")
        self.assertIn("<code>__this__</code>", i)
        self.assertNotIn('class="fill"', i)

    def test_blanks_render(self):
        i = self.md.inline("Meet me on __Tuesday__ at __2pm__, or whenever.")
        self.assertEqual(i.count('class="fill"'), 2)
        self.assertIn('>Tuesday<', i)

    def test_links(self):
        self.md_doc = build.MiniMD(href_rewriter=build.doc_href)
        i = self.md_doc.inline("[the tidy](03-the-ten-minute-tidy.md) and [web](https://example.org)")
        self.assertIn('<a href="03-the-ten-minute-tidy.html">the tidy</a>', i)
        self.assertIn('<a href="https://example.org">web</a>', i)

    def test_lists_and_nesting(self):
        h = self.md.render(
            "- top one\n- top two\n  - nested a\n  - nested b\n- top three"
        )
        self.assertEqual(h.count("<li>"), 5)
        self.assertIn("<li>top two<ul>", h)
        self.assertIn("nested a", h)

    def test_task_list(self):
        h = self.md.render("- [ ] not done yet\n- [x] done already")
        self.assertIn('<li class="task"><input type="checkbox" aria-label="task">not done yet</li>', h)
        self.assertIn('type="checkbox" checked aria-label="task">done already', h)

    def test_blockquote_and_fence(self):
        h = self.md.render("> **Callout:** hi\n\n```text\nline one\nline two\n```")
        self.assertIn("<blockquote>", h)
        self.assertIn("<strong>Callout:</strong>", h)
        self.assertIn("line one\nline two", h)

    def test_table(self):
        h = self.md.render(
            "| A | B |\n|---|---|\n| one | two |\n| with **bold** | __a blank__ |"
        )
        self.assertIn("<thead><tr><th>A</th><th>B</th></tr></thead>", h)
        self.assertIn("<tr><td>one</td><td>two</td></tr>", h)
        self.assertNotIn("<td>---</td>", h)
        self.assertIn('<span class="fill">a blank</span>', h)

    def test_hr_and_paragraph_joining(self):
        h = self.md.render("First line\nsecond line continues.\n\n---\n\ndeep breath")
        self.assertIn("<p>First line second line continues.</p>", h)
        self.assertIn('<hr class="rule">', h)

    def test_escaping(self):
        h = self.md.render("Tag <b> & \"quote\" stay text")
        self.assertIn("&lt;b&gt;", h)
        self.assertIn("&quot;quote&quot;", h)
        self.assertNotIn("<b>", h)


class TestTemplates(unittest.TestCase):
    def test_parse_and_required_fields(self):
        files = sorted(REPLIES.glob("*.md"))
        self.assertGreaterEqual(len(files), 12, "expected at least 12 reply templates")
        seen_names = set()
        for f in files:
            fields, body = build.parse_template(read(f))
            self.assertIn("name", fields, "%s: missing name in front matter" % f.name)
            self.assertIn("when", fields, "%s: missing use-when" % f.name)
            self.assertIn("tone", fields, "%s: missing tone" % f.name)
            self.assertTrue(fields["name"].strip(), "%s: empty name" % f.name)
            self.assertNotIn(fields["name"], seen_names, "duplicate name: %s" % fields["name"])
            seen_names.add(fields["name"])

    def test_body_has_blanks(self):
        for f in sorted(REPLIES.glob("*.md")):
            _fields, body = build.parse_template(read(f))
            blanks = build.BLANK_RE.findall(body)
            self.assertGreaterEqual(len(blanks), 2, "%s: expected at least 2 blanks" % f.name)
            for b in blanks:
                self.assertFalse("_" in b, "%s: nested underscore blank %r" % (f.name, b))

    def test_front_matter_only_fields(self):
        """Front matter must be simple key: value lines the CLI can read."""
        for f in sorted(REPLIES.glob("*.md")):
            raw = read(f)
            m = build.FRONT_RE.match(raw)
            self.assertTrue(m, "%s: front matter block missing" % f.name)
            for line in m.group(1).split("\n"):
                self.assertRegex(line, r"^[a-z][a-z ]*:\s*\S", "%s: bad front matter line %r"
                                 % (f.name, line))

    def test_copy_text_starts_with_subject(self):
        raw = read(REPLIES / "60-checking-in.md")
        fields, body = build.parse_template(raw)
        copy = build.template_copy_text(fields, body)
        self.assertTrue(copy.startswith("Subject: "))

    def test_templates_page_refs_cli_pairing(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = build_to(tmp)
            text = read(out / "templates.html")
            self.assertGreaterEqual(text.count('class="tpl"'), 12)


class TestRepoHygiene(unittest.TestCase):
    DOC_FILES = None

    def test_docs_internal_links_resolve(self):
        allowed_special = {"templates.html", "index.html"}
        for f in sorted(DOCS.glob("*.md")):
            text = read(f)
            for target in re.findall(r"\]\(([^()\s]+)\)", text):
                if target.startswith("http") or target.startswith("mailto:") or target.startswith("#"):
                    continue
                path, _, _frag = target.partition("#")
                if path.endswith(".md"):
                    self.assertTrue((DOCS / path).exists(),
                                    "%s links to missing %s" % (f.name, path))
                else:
                    self.assertIn(path, allowed_special,
                                  "%s: non-doc link %s not covered" % (f.name, path))

    def test_docs_reference_companion_cli(self):
        text6 = read(DOCS / "06-reply-templates.md")
        text7 = read(DOCS / "07-the-local-ai-helper.md")
        self.assertIn("kind-email-crafter-cli", text6)
        self.assertIn("kind-email-crafter-cli", text7)
        self.assertIn("kind-email-crafter-cli", read(README))

    def test_no_email_personal_addresses(self):
        """Docs and templates use example.org/example.com, never personal mail providers."""
        banned = re.compile(r"@(?:gmail|googlemail|outlook|hotmail|yahoo|icloud|aol)\.com", re.I)
        for p in list(DOCS.glob("*.md")) + list(REPLIES.glob("*.md")) + [README, STATUS]:
            if not p.exists():
                continue
            self.assertNotRegex(read(p), banned, "%s contains a personal-style email" % p.name)

    def test_no_secrets(self):
        """Scan every repo text file for common credential shapes."""
        patterns = [
            re.compile(r"sk-[A-Za-z0-9]{20,}"),               # openai-style
            re.compile(r"AKIA[0-9A-Z]{16}"),                  # aws key id
            re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),        # github tokens
            re.compile(r"xox[bap]-[A-Za-z0-9-]{10,}"),        # slack tokens
            re.compile(r"mysql://|postgres(ql)?://[^@\s]+:[^@\s]+@"),  # db urls with creds
            re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
            re.compile(r"(?i)\bapi[_-]?key\b\s*[:=]\s*['\"][^'\"]{16,}['\"]"),
            re.compile(r"(?i)\bsecret[_-]?key\b\s*[:=]\s*['\"][^'\"]{16,}['\"]"),
            re.compile(r"(?i)\bpassw(or)?d\b\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"),
        ]
        targets = [
            p for p in ROOT.rglob("*")
            if p.is_file()
            and ".git" not in p.parts
            and "__pycache__" not in p.parts
            and p.resolve() != Path(__file__).resolve()  # this file describes the patterns
            and p.suffix in {".py", ".md", ".css", ".txt", ".html", ""}
        ]
        for p in targets:
            try:
                text = read(p)
            except (UnicodeDecodeError,):
                continue
            for pat in patterns:
                m = pat.search(text)
                self.assertIsNone(m, "%s looks like a credential: %r" % (p.relative_to(ROOT), m.group(0) if m else ""))

    def test_license_exact_copyright(self):
        lic = read(LICENSE)
        self.assertEqual(lic.count("Copyright (c) 2026 Asdale Dynamics, LLC"), 1)
        self.assertIn("MIT License", lic)
        self.assertIn("Permission is hereby granted", lic)

    def test_readme_credits_and_docs(self):
        r = read(README)
        self.assertIn("Asdale Dynamics, LLC", r)
        self.assertIn("Email Calm Guide", r)
        self.assertIn("python3 build.py", r)
        self.assertIn("tests/test_all.py", r)
        self.assertIn("site/index.html", r)

    def test_status_md_exists_and_complete(self):
        self.assertTrue(STATUS.exists(), "STATUS.md missing")
        s = read(STATUS)
        for heading in ("Built", "Run", "verif", "gap"):
            self.assertIn(heading.lower(), s.lower(),
                          "STATUS.md missing section hint: %s" % heading)

    def test_docs_pages_have_one_h1(self):
        for f in sorted(DOCS.glob("*.md")):
            h1s = [l for l in read(f).split("\n") if re.match(r"^# [^#]", l)]
            self.assertEqual(len(h1s), 1, "%s: expected exactly one H1" % f.name)

    def test_docs_reference_core_promises(self):
        """The manual must cover the topics this project is about, by name."""
        checks = {
            "02-the-three-folder-system.md": ["Needs action", "Waiting on", "Someday"],
            "03-the-ten-minute-tidy.md": ["ten-minute", "timer"],
            "07-the-local-ai-helper.md": ["Ollama", "LM Studio", "local"],
            "09-scam-resistant-habits.md": ["Hover", "password", "Urgency"],
            "10-the-weekly-reset.md": ["- [ ]"],
            "11-common-mistakes.md": ["The mistake", "The gentler fix"],
        }
        for name, needles in checks.items():
            text = read(DOCS / name)
            for needle in needles:
                self.assertIn(needle, text, "%s missing content: %s" % (name, needle))


if __name__ == "__main__":
    unittest.main(verbosity=2)
