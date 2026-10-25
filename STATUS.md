# STATUS

Project: **Email Calm Guide** — a friend-style manual for taming email and inbox dread.
Maintained by Asdale Dynamics, LLC. MIT licensed. Last verified: 2026-10-25.

## What was built

- **The manual** (`docs/`, 13 chapters, markdown):
  - `00-start-here.md` — welcome, the whole system in one breath, how to use the guide
  - `01-why-email-feels-so-heavy.md` — why inboxes dread-load people (open loops, the dread loop, the perfection trap)
  - `02-the-three-folder-system.md` — Needs action / Waiting on / Someday, and why only three
  - `03-the-ten-minute-tidy.md` — the daily 10-minute triage: reply / move / archive / unsubscribe
  - `04-unsubscribe-without-guilt.md` — the permission slip, three-strikes rule, sketchy-sender caveat
  - `05-fast-kind-replies.md` — reply/wait/no-reply judgment, three-sentence replies, boundaries
  - `06-reply-templates.md` — how the templates work; the five you'll use most; pairing with kind-email-crafter-cli
  - `07-the-local-ai-helper.md` — local AI (Ollama / LM Studio), four email jobs, copy-paste prompt recipes, privacy rules
  - `08-rules-and-auto-reply.md` — rules worth having for Gmail/Outlook/Apple Mail, kind auto-reply draft, canned responses
  - `09-scam-resistant-habits.md` — the three-touch check, red-flag list, verify-out-of-band, family/clinic add-ons, what to do after a click
  - `10-the-weekly-reset.md` — 8-box weekly checklist (as real hoverable checkboxes), skip-a-week rules
  - `11-common-mistakes.md` — 11-row mistakes table (mistake / what's behind it / gentler fix)
  - `12-digging-out.md` — the 5,000-email rescue plan: holding reply, big archive, then normal tidy
- **The template library** (`templates/replies/`, 12 fill-in reply templates): yes, not now, kind no, handoff, quick update, checking in, request, no-reply-needed, can-we-meet, sorry-slow-reply, decline-invite, out-of-office. Plain markdown + tiny front matter (name/when/tone/subject) so any tool — including **kind-email-crafter-cli**, the companion CLI — can read them. Blanks are marked `__like this__`.
- **The static site** (`site/`, built output): warm, calm HTML with sidebar chapter nav, prev/next links, dark/light automatic theme, print styles, and a copy button on each template. Works fully offline; `site/index.html` opens straight from disk.
- **The builder** (`build.py`): stdlib-only (no dependencies, no API keys, no network). Converts docs → HTML, builds the template library page from files, copies CSS, prunes stale output. Deterministic: rebuilding always produces byte-identical files. `--out` and `--serve [port]` flags; preview binds to 127.0.0.1 only and publishes nothing.
- **Tests** (`tests/test_all.py`): 32 checks (build, page chrome, nav order, determinism, freshness of committed site/, markdown renderer behavior, template integrity, internal links, CLI-pairing references, LICENSE/README clauses, email-provider ban, credential scan, STATUS presence).
- **`README.md`, `LICENSE` (MIT, exact line `Copyright (c) 2026 Asdale Dynamics, LLC`), `.gitignore`, this STATUS.md.**

## How to run it

```bash
python3 build.py              # build the site into site/
python3 build.py --serve      # build, then preview at http://127.0.0.1:8000 (Ctrl+C stops)
python3 tests/test_all.py     # run the test suite (also: python3 -m unittest discover -s tests)
```

Requires only Python 3.8+ (no packages to install). Read `site/index.html` in any browser, or open the `docs/*.md` files directly.

## Verification results

- `python3 build.py` → builds 13 manual pages + 1 template library page (14 HTML files) successfully.
- `python3 tests/test_all.py -v` → **32/32 tests pass** (0 failures, 0 errors).
- Determinism: two fresh builds produce byte-identical trees; committed `site/` matches a fresh build.
- Preview server verified by scripted request: `/`, `/templates.html`, `/style.css`, and two chapter pages all returned HTTP 200 with content.
- Manual glitch-sweep for stray non-ASCII: only intentional em-dashes and arrows remain.
- Credential scan passes: no keys, tokens, or personal email addresses anywhere in the repo (verified by test; PRs get scanned too).
- No network calls during build or tests; the optional preview server binds 127.0.0.1 only.

## Known gaps

- **No site search.** A tiny client-side search (pure static) would be a nice next addition; the manual is small enough to navigate by hand for now.
- **The template library order is filename-based** (10, 20, ... 99); renaming or renumbering files is how you reorder.
- **No RSS or "reading progress"** extras, and the pages have no images — intentional for a v1 but worth revisiting if the guide grows.
- **English only.** A Spanish or plain-sentence second edition would be a good future fork.
- **kind-email-crafter-cli is referenced, not bundled.** It's the companion tool from the same toolkit; this repo contains only the manual + templates it consumes. Until it's installed, everything works by copy-paste.
- **Desktop-first examples** (menu paths drift across mail-client versions); steps say what to look for, not exact button pixels.
