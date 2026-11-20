# Changelog

## v1.10 — FINAL FREEZE

The prototype is frozen here. This entry covers both the content completion
and the packaging decision; the earlier v1.10 notes below it describe the data
work in detail.

### Packaging decision reversed: native Android, not Capacitor

The v1.1 recommendation was Capacitor. It is now **native Android with a
WebView host**, because a constraint changed: the app will be built by Claude
Code autonomously through a connected GitHub repo, with no human watching the
build.

Capacitor's characteristic failure is a version mismatch across Capacitor ↔
AGP ↔ Gradle ↔ Kotlin ↔ JDK, where the root cause is not in the repository,
not in the error message, and lands inside generated code. Native's
characteristic failure is a compile error in a hand-written file with a line
number. Full reasoning in ANDROID_PACKAGING.md §1.

What this cost: about 200 lines of Kotlin for the file picker, print and share
capabilities Capacitor would have supplied as plugins. What it bought: one
dependency ecosystem instead of two, fully pinned versions, reviewable diffs,
and — the substantive win — **no `INTERNET` permission at all**, which turns
the offline guarantee into something Android enforces rather than something a
README claims.

### New: `android/` — the native host

Nineteen hand-written files, nothing generated:

- `MainActivity.kt` — WebView configuration, `WebViewAssetLoader`, back-button
  handling, and the injected script that adds native capability without
  touching the frozen web app.
- `NativeBridge.kt` — the only JS-facing surface: `saveFile`, `printPage`,
  the file chooser, and an unused-but-ready `shareText`.
- Pinned Gradle setup with a version catalog; no version ranges anywhere.
- `stageClinicalAsset`, wired into `preBuild`, which copies the built HTML into
  assets and **fails the build** if it is missing, so an APK can never ship
  without clinical content.
- An instrumented `SmokeTest` covering the four things that would otherwise
  fail silently on a device.

**The frozen web app is not modified at all.** Every integration point was read
out of `shell.html` rather than assumed:

- Back: the app keeps its own `navStack` and pushes no history entries, so
  `canGoBack()` is always false. The host asks the page whether `#backBtn` is
  visible, clicks it if so, and exits only if not.
- Export/backup: the app builds a `Blob`, attaches it to `<a download>`, clicks
  it, and revokes the object URL after 500 ms. WebView cannot fetch a `blob:`
  URL, so a **capture-phase** click listener reads it synchronously and hands it
  to the bridge. Capture phase is load-bearing — deferring past the revoke
  would lose the data.
- Print: `window.print()` is ignored by WebView, so it is replaced by injection
  and routed to `PrintManager`.

### Four hazards identified and guarded

1. **localStorage origin.** My Lab values are keyed to origin. The asset is
   served over a fixed `https://appassets.androidplatform.net/assets/index.html`
   and renamed to a version-free `index.html` precisely so the origin can never
   drift; `file://` was rejected because its origin is opaque. An instrumented
   test exists solely to fail if this changes.
2. **Algorithmic darkening.** Android 13+ auto-inverts WebView content in dark
   mode, which would destroy the sepia, pista and beige themes. Explicitly
   disabled. A light-mode debug build would never reveal it.
3. **R8 stripping the bridge.** Nothing in Kotlin calls `NativeBridge`, so R8
   would remove it; the release build would install fine and break the first
   time a clinician tapped Export or Print. Kept by a ProGuard rule, with a
   test to catch its removal.
4. **`allowBackup`.** Set to `false` deliberately rather than inherited — the
   default would copy local reference ranges to the user's Google account.
   Backup rules are written and scoped if a hospital chooses to enable it.

### New: CI

`.github/workflows/build.yml`. The ordering is the point: **the four-method
clinical QA suite runs first and gates everything else**, so a data error
cannot reach an installable artifact. Then the debug APK with lint and unit
tests; then an emulator smoke test on pull requests; then a manual release
bundle whose signing material comes from repository secrets and never from the
repo.

The QA suite was made portable to support this — Chrome resolves from
`CHROME_PATH` with a fallback to Playwright's bundled Chromium, and both the
Node validators and the Python suites now find the built HTML in either the
development or the handover layout.

### Still to do before the first release

Launcher icons need copying into the Android project (the build will not
succeed until they are), a Gradle wrapper needs generating, a signing keystore
needs creating, `applicationId` and `targetSdk` need confirming, and the
release build should be checked once on a physical device. The full list is
KNOWN_GAPS.md and ANDROID_PACKAGING.md §9.

---

## v1.10 — content completion (detail)

### Scope

The clinical corpus went from **34 tests to 180** — the full planned set.
Every one of the 26 categories now holds content. No design decisions were
reopened; the schema settled at v1.1 absorbed all 146 new records without
change, which was the point of freezing it first.

Corpus at this freeze:

| | |
|---|---|
| Tests | 180 |
| Categories | 26 (none empty) |
| Reference-range rows | 759 |
| Multi-analyte panel tests | 32 |
| Collection tubes | 11 |
| Tests with critical-value thresholds | 96 |
| Interpretation notes | 840 |
| Tests with patient-facing instructions | 132 |
| Records with recorded provenance | 180 / 180 |

### New in the UI

- **Version number in the app bar**, as `v 1.10` in a smaller, lighter font
  beside the app name. It is written at runtime from `LABREF_VERSION` in the
  data module, so the displayed number has exactly one source of truth and
  cannot drift from the file it was built from.
- **Long descriptive range text wraps** instead of being clipped. Range
  values over 24 characters get a `.wrap` class that drops
  `white-space:nowrap`, which matters now that many records express a range
  as a sentence ("Non-reactive; if reactive, report a quantitative titre")
  rather than two numbers.

### Data-model additions (backward compatible)

- **`src[]` on every record** — an array naming the guideline or standard
  each record's reference limits and decision thresholds rest on. This
  replaces the v1.1 inline citation markers, whose source URLs had not been
  captured into a bibliography. `qa/validate_data.js` warns on any record
  without it, so the gap cannot silently reopen. All 180 records carry one,
  including the original 34, which were backfilled.
- **An eleventh tube: `sterile`** — a sterile universal container for
  non-blood specimens, with notes on boric acid urine transport, 24-hour
  collection preservatives, and splitting a fluid tap across EDTA, plain and
  sterile containers. The 13 urine, stool, CSF and body-fluid tests
  previously (and misleadingly) shown as "Plain Serum — red" now point here.
  It carries `order:8` and its notes state explicitly that it is not part of
  the CLSI GP41 draw sequence.

### Clinical data corrections found during this pass

- **Cortisol unit mismatch** — the 9 am adrenal-insufficiency-unlikely
  threshold read 15 µg/dL against 400 nmol/L; 400 nmol/L is 14.5 µg/dL.
  Corrected to 14.5. Caught by the conversion check in
  `qa/validate_data.js`, not by eye.
- **Wrong tube id** on one record (`fluor` instead of `fluoride`), which
  would have rendered no tube at all. Caught by the referential check.
- **Lipid panel critical value was unscoped** — the triglyceride
  pancreatitis threshold (>1000 mg/dL) appeared when interpreting HDL or
  LDL. Now scoped with `critical.analyte:["trig"]`.
- **LDL-C high-risk target added** (<70 mg/dL / 1.8 mmol/L), which the v1.1
  record omitted despite being the number most often needed at the bedside.
- **Calcium renamed** to "Calcium (Total & Ionised)" to make the panel's
  contents visible in search results and lists.
- **Two `rel[]` typos** (`hcg` → `bhcg`) that pointed at no record.

### Verification

Now **four** independent methods, all passing with zero errors — see QA.md.
New in v1.10:

- **Method 4, `qa/test_all_tests.py`** — a full-corpus sweep. It opens all
  180 detail pages in a real browser by searching for each test by its own
  name, and asserts each renders a reference-range table, a breadcrumb
  naming the page, and enough content to be useful; then drives the Result
  Interpreter through **all 243 test/component combinations**, checking that
  panels offer a component picker, that single-analyte tests do not, that
  every declared component appears in the picker, and that each produces
  output; then verifies every synonym on every test resolves to its own
  record. Console and page errors are collected across the entire walk.
- The data validator gained the **provenance check** and a
  **precision-aware conversion tolerance** (half of the last decimal place,
  or 3%, whichever is larger), which removed false positives on correctly
  rounded conversions such as bilirubin 1.2 mg/dL → 21 µmol/L.

A harness bug was also found and fixed: `test_v11_features.py` was still
pointing at `LabRef_v1.10.html`, so it had been passing against the previous
build. All QA scripts now target `LabRef_v1.10.html`. Method 4 initially
reported 46 tests as unreachable by search; this was its own 60 ms wait
against the search box's 120 ms input debounce, not an app defect — it was
confirmed by direct measurement before the harness was corrected.

### Icons

Unchanged. The artwork carries no version or product name.

---

## v1.1 — second freeze

### Clinical data corrections

These came out of a full re-verification pass over all 34 records: a
programmatic sweep (`qa/validate_data.js`) plus a value-by-value domain
review, with authoritative-source checks on the highest-consequence and
most-likely-to-have-moved figures.

- **TSH pregnancy ranges corrected — this one mattered.** The trimester
  ranges were the superseded 2011 ATA / 2014 ETA values (T1 upper limit
  2.5, T2–T3 3.0 mIU/L). ATA 2017 replaced these after studies in Asia,
  India and the Netherlands found only a modest fall in the upper limit,
  and sets ~4.0 mIU/L where a local trimester-specific interval is not
  available. Corrected to T1 0.1–4.0, T2 0.2–4.0, T3 0.3–4.0, with two new
  interpretation notes: one explaining the change explicitly (so a
  clinician taught 2.5 understands why this reads 4.0), one noting the
  shift applies from weeks 7–12 and returns gradually toward the
  non-pregnant range. **Using the old 2.5 cutoff over-diagnoses subclinical
  hypothyroidism in pregnancy and leads to unnecessary levothyroxine** —
  the reason this was worth catching.
- **LDL-C high-risk target added.** The panel carried the optimal (<100)
  and very-high-risk (<55 mg/dL) targets but omitted the widely-used
  high-risk target of <70 mg/dL / <1.8 mmol/L (ESC/EAS). Added.
- **D-dimer pregnancy safety note added.** The stored trimester ranges
  match a published study exactly, but published intervals vary several-
  fold between assays and populations, and the ranges describe what is
  physiologically expected rather than an exclusion threshold. A reader
  could otherwise take a value inside the third-trimester range as ruling
  out PE at term. Now stated explicitly.
- **GDM criteria expanded.** DIPSI (non-fasting 75 g, 2 h ≥140 mg/dL) is
  correct and MoHFW-endorsed, but validation studies in Indian women show
  low sensitivity against WHO 1999 and IADPSG. Added that caveat plus the
  IADPSG/WHO 2013 fasting alternative (fasting ≥92, 1 h ≥180, 2 h ≥153).
- **Troponin assay nuance added.** hs-cTnT carries two different "overall"
  cutoffs — 19 ng/L on the US FDA label versus 14 ng/L in most published
  studies and European practice. The overall row is now labelled as the
  guideline/non-US figure and a note explains the discrepancy.
- **Calcium renamed** from "Calcium, Total & Corrected" to "Calcium (Total
  & Ionised)" — the record's two components are total and ionised; the
  corrected-calcium formula lives in the interpretation notes, and both
  remain findable through the existing synonyms.

Verified-correct and left unchanged (worth recording so the next pass does
not redo them): total and direct bilirubin SI ranges, vitamin D
deficiency/insufficiency/sufficiency thresholds, hs-cTnI Abbott 99th
percentiles (26 / 34 male / 16 female ng/L), hs-cTnT Roche sex-specific
(22 male / 14 female ng/L), ESC/EAS LDL-C very-high-risk target, HbA1c
DCCT↔IFCC conversions (checked arithmetically against the affine formula),
and the neonatal bilirubin thresholds with their hour-specific-nomogram
caveat.

### Renamed MedRef → LabRef

Throughout: UI, document title, data module constants (`LABREF_*`), file
names (`labref_data_v1.10.js`, `LabRef_v1.10.html`), export file types, and
documentation.

Two compatibility paths were kept deliberately, and are the only places the
old name survives:

- **localStorage** reads `labref_v1`, falling back once to `medref_v1` and
  immediately rewriting under the new key, so an existing user's themes,
  favourites, text size and My Lab values carry over instead of silently
  vanishing. The old key is left in place rather than deleted.
- **Import** accepts both `labref-*` and `medref-*` lab-profile and backup
  files, so anything already exported still restores.

### UI changes

- **Detail pages open collapsed** except *Reference ranges* and
  *Interpretation notes*. "Your lab's values" no longer auto-opens when a
  local value exists — the override already shows in the open Reference
  ranges block with a "Your lab" badge, so nothing is hidden.
- **Breadcrumb page address** in the app bar (`Tests › Lipids › Lipid
  Profile`): small type on its own full-width row, ancestors tappable and
  underlined, current page in a distinct colour. The highlight colour is
  per-theme because a single colour cannot clear 4.5:1 contrast on all six
  app-bar backgrounds — sepia's mid-brown tops out at 4.85:1 even against
  pure white. Each value is the most saturated warm tone that still clears
  4.5:1 on that theme.
- **Tests-tab panels are collapsible** (Favourites, Recently viewed,
  Categories), open by default, with collapse state persisted in
  `S.panels` so it survives navigation and reload. Detail-page blocks
  deliberately do *not* persist — they reset to the defaults above every
  time.
- Detail header de-duplicates abbreviation and category when they are the
  same string (Lipid Profile is abbr "Lipids" in category "Lipids", which
  rendered as "Lipids · Lipids").

### Verification

Three independent methods, all passing — see QA.md. Two are new in v1.1:
`validate_data.js` (data integrity without a browser) and `audit_build.js`
(static audit of the shipped artifact, including the offline guarantee).
`test_v11_features.py` adds 30 browser assertions for the changes above.

### Icons

Unchanged from v1.0 — the artwork carries no product name, so the rename
required no re-export.

---

## v1.0 — first freeze

Initial prototype: 34 tests across 26 categories, 10 tube types, six
multi-analyte panels, My Lab local overrides with export/import, six
themes, tube picker, result interpreter, reverse lookup, printable prep
handout, patient-mode range matching.
