# QA — four independent verification methods

The client's requirement was that the code be tested by **at least two
different methods**. There are four, and they are genuinely independent:
each could catch a class of defect the others structurally cannot. Run them
all with:

```bash
cd handover/app && python3 -I build.py && cd .. && bash qa/run_all.sh
```

`run_all.sh` exits non-zero if any method fails, so it works as a CI gate.

---

## Method 1 — behaviour in a real browser (Playwright)

`qa/test_v11_features.py` and the companion suites
(`test_panel.py`, `test5.py`, `test3.py`, `test6.py`, `checkbc.py`,
`fstest.py`, `test_themes.py`).

**What it does:** drives the shipped HTML in headless Chrome at a 390×844
phone viewport, using real clicks, real typing and real page reloads — never
by calling internal functions. Most of the app's logic lives inside an IIFE
and is deliberately not reachable from the test, which is what makes this a
behavioural rather than a unit test.

**What only this method can catch:** anything that depends on the browser —
event wiring, CSS that clips text, localStorage persistence across reloads,
collapse state surviving navigation, migration from the legacy `medref_v1`
key, computed font sizes, console errors at runtime.

**Representative coverage:** the MedRef→LabRef rename including lossless
localStorage migration; detail-page block collapse defaults (only Reference
ranges and Interpretation notes open); the breadcrumb's content, navigation
and freedom from truncation at 390 px; the Tests-tab panels' default-open
state and persisted collapse; the app-bar version label and that it renders
smaller than the app name; patient-mode range matching across a 24-case
specificity matrix; all six themes; the blood-culture tube's
brand-specific-caps handling; the clinician/patient split in the prep
handout.

---

## Method 2 — data integrity, without a browser

`qa/validate_data.js` — plain Node, reads the data module directly.

**What it does:** walks all 180 records and 759 range rows and checks the
data against itself.

**What only this method can catch:** arithmetic and referential errors that
render perfectly. A conversion factor that disagrees with the SI and
conventional numbers quoted beside it looks completely normal on screen.

**Checks performed:**

- **Unit-conversion consistency** — for every range row, recompute the SI
  value from the conventional value and the record's `factor`, and compare.
  Tolerance is **precision-aware**: half of the last decimal place quoted,
  or 3%, whichever is larger. This is what caught the cortisol error
  (15 µg/dL quoted against 400 nmol/L, where 400 nmol/L is 14.5 µg/dL) while
  not false-positiving on correctly rounded conversions such as bilirubin
  1.2 mg/dL → 21 µmol/L.
- **Referential integrity** — every `cat`, `tube.id` and `rel[]` entry
  resolves to a real record. This caught a `fluor` tube id that should have
  been `fluoride`, and two `rel[]` entries pointing at `hcg` rather than
  `bhcg`.
- **Logical coherence** — `lo` not above `hi`; every range row carries
  either numeric bounds or descriptive `txt` in both unit systems; no
  duplicate ids; critical values consistent with the range they qualify.
- **Panel structure** — if any row in a test carries an `analyte`, report
  how many do, so a half-tagged panel (where untagged rows silently become
  info-only "Also note" rows) is visible rather than a surprise. Flag
  unscoped `critical` values on panel tests, since those display for every
  component.
- **Provenance** — warn on any record without `src[]`. Currently zero.

---

## Method 3 — built-artifact structural audit

`qa/audit_build.js` — static analysis of the shipped `LabRef_v1.10.html`.

**What it does:** treats the built file as the artifact under test, not the
sources it came from.

**What only this method can catch:** anything that goes wrong *in the
build*, or that only exists once data and shell are spliced together. A
correct data file and a correct shell can still produce a broken output.

**Checks performed:**

- **The offline guarantee** — fails on any external resource reference
  (`http:`, `//`, `src=`, `@import`, remote fonts). This is the check that
  makes "fully offline" a property that cannot regress silently.
- Build placeholder consumed; no `<cite>` tags surviving into the artifact.
- No duplicate element ids; every `data-nav` has a matching view, and every
  view a nav target.
- Every CSS custom property that is *used* is also *defined*, for all six
  themes — so a theme can't ship with a missing variable and an invisible
  control.
- Every `data-*` attribute the JS reads is actually emitted by the markup
  that produces it.
- Rename hygiene: counts remaining `MedRef`/`medref` strings and asserts
  each one is in a migration or backward-compatibility path.
- Tag balance and self-containment; reports the final byte size.

---

## Method 4 — full-corpus sweep (new in v1.10)

`qa/test_all_tests.py` — Playwright again, but aimed at content rather than
features.

**Why it exists:** methods 1–3 verify the shell, the data and the build.
None of them answers "does every one of the 180 tests actually work?"
Methods 1 and 2 could both pass with a record that renders an empty detail
page. This method walks the whole corpus.

**What it does, per run:**

1. **Content completeness, from the data module** — for all 180 records:
   at least one reference range; at least one cause of a raised value and
   one of a lowered value; at least three interpretation notes; clinician
   pre-test instructions; an assigned tube; a recorded source.
2. **All 180 detail pages, in the browser** — for each test, navigate the
   way a clinician would (open Tests, type the test's own name into the
   search box, tap the result), then assert the detail page renders a
   reference-range table, a `rng` block, a breadcrumb naming the page, and
   enough text to be useful.
3. **The Result Interpreter, exhaustively** — switch to patient mode, then
   for every test the interpreter offers: assert panels present a component
   picker and single-analyte tests do not; assert every declared component
   appears in the picker; select each component, enter a value, interpret,
   and assert output is produced. **243 test/component combinations.**
4. **Search coverage** — assert every synonym on every test resolves to its
   own record, so no test is unreachable by a term it claims to answer to.

Console and page errors are collected across the entire walk and fail the
run.

**A note on its first run:** it initially reported 46 tests as unreachable
by search. That was the harness waiting 60 ms after typing against the
search box's 120 ms input debounce — confirmed by direct measurement (0
results at 60 ms, 1 result at 250 ms) before changing anything in the app.
The harness waits were corrected; no app change was needed. Worth knowing
if the suite is extended.

---

## Method 5 — stable row identity (new in v2.0)

`qa/validate_rids.js` — Node, no browser.

**Why it exists:** a user's own lab values are stored against individual
reference rows, in localStorage on their own device, and must survive every
future content update. The failure this guards is silent and the worst the
app could have: a saved override that comes to refer to a *different
population* — a clinician's adult-female haemoglobin range quietly becoming
the newborn range, with nothing on screen to say so. Careful editing does
not prevent that reliably, so it is checked mechanically on every build.

**What it enforces:**

1. Every range row has a well-formed `rid`, unique within its test.
2. No published rid has changed meaning — its `sex`/`age`/`preg`/analyte
   dimensions are compared against `qa/rid_baseline.json` and frozen.
   Correcting an interval's **numbers** is explicitly allowed; that is
   content maintenance. Re-pointing a rid at another population is an error.
3. rids are append-only: a row may only disappear if listed under `retired`
   in the baseline, a retired rid is never revived, and a new row may not
   take a number at or below the highest ever published for that test.

A reworded `grp` label with unchanged dimensions is reported as a notice,
not an error — it is cosmetic, and failing it would tempt someone to "fix"
the baseline the lazy way.

Regenerate the baseline deliberately, and commit the diff, with
`node qa/validate_rids.js --update`. The update path runs the same checks
first and refuses to write if any invariant is violated.

## Method 5b — self-test of the identity guard

`qa/test_rid_guard.js` — Node, no browser.

**Why it exists:** method 5 is the only thing protecting saved clinical
values from silent re-pointing, and a guard that has never been *observed
to fail* is not evidence of anything. This drives it through each violation
it claims to catch, against a small synthetic corpus in a temp directory
(never the real data), and asserts it rejects them — and, just as
importantly, that it still *accepts* the legitimate edits:

```
rejected: missing rid · duplicate rid · malformed rid · rid repointed to
          another sex · rid repointed across age bands · row deleted
          silently · new row reusing a low number · retired rid revived
accepted: interval numbers corrected · label reworded (reported as a
          notice) · row appended above the ceiling · removal declared
          under "retired"
```

12 behaviours, all verified.

## Method 6 — row-selection tie-break guard (new in v2.0, Stage 2b)

`qa/validate_ties.js` — Node, no browser.

**Why it exists:** two distinct silent-wrong-value bugs, both in the
interpreter's row-picker rather than the override store (see CHANGELOG's
Stage 2a/2b): `bestRange()` used to break a genuine *demographic* tie
(ESR "male <50y" vs "male ≥50y" both just matching sex=male, age=adult) by
array order, and the ref/method tie-chooser built to fix that in turn
wrongly fired on `dx`/`cutoff`/`target` rows that form a clean
*value*-ordered ladder (Vitamin D's four bands all apply to "any adult" —
the entered number picks the band, not a demographic guess). Both classes
need a human review gate the same way the rid guard does, because a
future content change (a new age-banded row, a new diagnostic threshold
sharing a key with an existing one) can silently reintroduce either failure
mode.

**What it enforces:**

1. Recomputes every `ref`/`method` collision (same `(analyte, sex, age,
   preg)` key, two or more rows) and checks each against
   `qa/known_tie_groups.json`'s `groups` array. A new or changed one fails
   the build.
2. Recomputes every `dx`/`cutoff`/`target` group sharing a key and runs the
   same `isValueLadder()` nesting-aware disjoint-interval check `shell.html`
   uses (every row has numeric bounds, every pair of intervals disjoint or
   nested) to tell a clean ladder (needs no review — the interpreter
   resolves it from the entered value) from a genuine ladder-fallback
   (needs clinical context a number can't supply). Checks every
   ladder-fallback group against `known_tie_groups.json`'s
   `ladder_fallback_groups` array; a new or changed one fails the build.

A reviewed entry that no longer reproduces (because a later content fix
resolved it, e.g. splitting a bundled measurand into its own analyte key)
is reported as a non-fatal **notice**, so stale baseline rows surface for
cleanup without blocking a build that made things strictly better.

Regenerating the baseline is manual and deliberate: add or edit the
relevant entry in `qa/known_tie_groups.json` directly, with a `_why`
explaining the clinical reasoning, rather than an `--update` flag — unlike
the rid guard, a tie's correctness can't be verified mechanically from the
data alone; it needs a human judgment call about whether the group is a
genuine ladder, a genuine ambiguity, or a bundled-measurand bug in
disguise.

---

## Current status

All six methods pass against the built `LabRef_v*.html`:

```
METHOD 2  validate_data.js   ERRORS: none   (180 tests, 26 categories, 11 tubes, 759 range rows)
METHOD 5  validate_rids.js   ERRORS: none   (759 rids verified unchanged in meaning)
METHOD 5b test_rid_guard.js  ERRORS: none   (12 guard behaviours verified)
METHOD 6  validate_ties.js   ERRORS: none   (22 ref/method ties, 8 ladder-fallback groups, all reviewed)
METHOD 3  audit_build.js     ERRORS: none   (734 KB, self-contained, 6 themes, cite tags: 0)
METHOD 1  test_v11_features   PASS          (feature regression, console errors: none)
METHOD 4  test_all_tests      PASS          (180 pages, 243 interpreter combinations, errors: none)
```

Remaining validator output is **warnings only**, and each is a deliberate
design choice rather than a defect — see KNOWN_GAPS.md:

- Two tubes share a draw-order number (`sst`/`plain` at 3, `esr`/`trace` at
  7). Correct: CLSI GP41 places them at the same step.
- Eleven panel tests carry an unscoped `critical` value. Intentional: these
  are narrative test-wide warnings that apply however the test is used.
- A few panels have one untagged info-only row, which renders in the "Also
  note" section by design.

## Running in CI

`.github/workflows/build.yml` runs this suite as **job 1**, and the Android
build depends on it. Nothing is packaged unless all six methods pass, so a
clinical data error cannot reach an installable artifact. For a clinical
reference app that ordering matters more than build speed.

The Playwright suites resolve Chrome from `CHROME_PATH`, then from the usual
system locations, and finally fall back to Playwright's own bundled Chromium —
which is what happens on a GitHub runner. The Node validators and the Python
suites also resolve the built HTML by glob in either layout (repo root or `app/`),
asserting exactly one build exists so a stale artifact is a hard error, so
`bash qa/run_all.sh` works unchanged from inside this package.

One more check runs on-device rather than here: `android/app/src/androidTest`
asserts that the APK actually contains all 180 tests, that the version matches,
that localStorage works at the pinned origin, and that the JavaScript bridge
survived R8. Those are host failures this suite structurally cannot see — see
ANDROID_PACKAGING.md §5.

## Extending the suites

Add a new test record and method 2 checks it immediately — no suite changes
needed. Method 4 also picks it up automatically, since it enumerates the
corpus from the data module rather than from a fixture list. Only a new
*feature* needs a new assertion, and those belong in
`qa/test_v11_features.py` alongside the existing ones.

The superseded prototype-era scripts (`test2.py`, `test4.py`,
`test_app.py`, `final.py`, `shots.py`) are kept for reference but are not
part of `run_all.sh`.
