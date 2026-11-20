# Build Process

LabRef ships as a single self-contained HTML file with zero network
dependencies and zero build tooling (no npm, no bundler) — intentional,
since the app must work fully offline after a one-time download/"Add to
Home Screen".

## How it fits together

```
app/labref_data_v1.10.js  (content — pure data, no HTML/CSS)
          │
          │  python3 -I build.py
          ▼
app/shell.html  (UI shell: CSS + JS, with a placeholder /*__LABREF_DATA__*/)
          │
          ▼
app/LabRef_v1.10.html  (the shipped artifact — this is what you open in a
                        browser or "Add to Home Screen")
```

`build.py`:
1. Reads `labref_data_v1.10.js` and `shell.html`.
2. Strips `<cite index="...">...</cite>` research-citation markup from the
   data (see SOURCES.md for why these markers exist and the gap around
   them) so the clinician never sees raw citation syntax.
3. Replaces the `/*__LABREF_DATA__*/` placeholder in `shell.html` with the
   (now-stripped) data file's contents, inlining the whole data module
   directly into a `<script>` tag in the shell.
4. Writes the result to `LabRef_v1.10.html` and prints a byte count plus a
   `cite tags remaining` sanity count. **This must read 0.** Anything else
   means citation markup reached the shipped file — `qa/audit_build.js`
   fails the build on it too. (In v1.0 this count read 1 because a source
   comment happened to contain the literal string; that comment was
   reworded, so the signal is now clean and any non-zero value is real.)
5. Aborts with an explicit error if the `/*__LABREF_DATA__*/` placeholder
   is missing from the shell, rather than silently writing a shell with no
   data in it.

## Rebuilding after any change

```bash
cd app
python3 -I build.py
```

That's the entire build step. No install, no dependency resolution. The
`-I` flag runs Python in isolated mode (ignores any `PYTHONPATH`/user site
packages) — keep using it; it avoids a stray same-directory module
shadowing a stdlib import, which matters more once this moves to a CI
environment that isn't a known-clean sandbox.

**Always rebuild before testing or shipping.** Editing `shell.html` or
`labref_data_v1.10.js` has no effect on `LabRef_v1.10.html` until you rebuild
— there is no watch mode or live reload.

## What never needs to change

- The build script itself should not need modification for ordinary
  content additions (§EXTENSION_GUIDE.md) or new test records — it's
  content-agnostic.
- If you add a new theme, a new tool, or any new UI surface, that's a
  `shell.html` change (CSS + JS), not a `build.py` change.

## Verifying a build

1. Open `LabRef_v1.10.html` directly in a browser (`file://` URL — no
   server needed, confirming the "fully offline" requirement still holds).
2. Run the QA suite (QA.md) against the freshly built file — every QA
   script points at `file:///home/claude/LabRef_v1.10.html` (or wherever you
   place it) by absolute path; update that path if you relocate the repo.
