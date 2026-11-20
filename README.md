# LabRef — Handover Package (v1.10, FROZEN)

**The prototype is frozen at v1.10.** The v1.1 freeze settled the data model,
the UI/UX flow and the feature set; v1.10 completed the clinical content —
all 180 planned tests, populated, verified and sourced — and added the native
Android scaffold.

Nothing in `app/` should change from here except by deliberate clinical
revision. The remaining work is building and shipping the Android app from the
scaffold in `android/`, which is designed so that doing so requires **no
change to the frozen web app at all**.

This document is the map for whoever (or whichever Claude Code session) picks
this up next.

## What LabRef is

An offline, single-file reference app for clinicians covering common
laboratory test values: both SI and conventional/US units, reference ranges
with paediatric/sex/pregnancy-specific variants where relevant, causes of
raised/lowered values, vacutainer/collection requirements, pre-test patient
instructions, and a "My Lab" feature so a department can record its own
local reference ranges and critical values over the textbook defaults.

Audience is clinicians, not patients. Conventional/US units are the default,
with a one-tap switch to SI.

## Current state in one line

**180 tests across 26 categories, 759 reference-range rows, 11 collection
tubes, 96 tests with critical-value thresholds, 840 interpretation notes, and
a recorded source on every single record.** Four independent verification
methods pass with zero errors. The app is feature-complete and
content-complete; nothing is stubbed, and no category is empty.

## Read these in order

1. **SCHEMA.md** — the full data model: every field on a test record, the
   tube/category records, and — most important — how multi-analyte "panel"
   tests are modeled. 32 of the 180 tests are panels. Read this before
   touching the data file.
2. **EXTENSION_GUIDE.md** — how to add or amend a test: naming/id
   conventions, how to decide if a new test is a "panel", how patient-mode
   matching works, a worked example. Needed for maintenance rather than
   for bulk population now.
3. **UNIT_CONVERSIONS.md** — the SI↔conventional conversion factors in use,
   and the rule for when a test needs a per-component factor instead of one
   test-level factor.
4. **SOURCES.md** — the research standard applied, and the `src[]`
   provenance field now present on all 180 records.
5. **BUILD.md** — how `build.py` turns the data file + shell into the
   shipped single-file HTML, and how to rebuild after any change.
6. **QA.md** — the four independent verification methods (browser
   behaviour, full-corpus sweep, data integrity, built-artifact audit), what
   each catches, and how to run them.
7. **ANDROID_PACKAGING.md** — **read this before writing any Android code.**
   The packaging decision (native, not Capacitor — reversed from v1.1 and the
   reasoning is in there), plus the four decisions that would otherwise ship
   broken and silent. `android/README.md` is the shorter working companion.
8. **KNOWN_GAPS.md** — what is still open. Much shorter than in v1.1.
9. **CHANGELOG.md** — what changed across the v1.0, v1.1 and v1.10 freezes,
   including the clinical corrections found during verification.

## What's in this package

```
handover/
  README.md                  (this file)
  SCHEMA.md
  UNIT_CONVERSIONS.md
  EXTENSION_GUIDE.md
  SOURCES.md
  BUILD.md
  QA.md
  ANDROID_PACKAGING.md
  KNOWN_GAPS.md
  CHANGELOG.md
  app/
    labref_data_v1.10.js      (THE COMPLETE CLINICAL DATA — all 180 tests)
    shell.html                 (UI shell — CSS + JS, data injected at build)
    build.py                   (build script: shell + data -> LabRef_v1.10.html)
    LabRef_v1.10.html          (the built, frozen app — open this in a
                                browser to see exactly what was signed off)
  android/                     (native Android host — see its own README)
    README.md
    settings.gradle.kts, build.gradle.kts, gradle.properties
    gradle/libs.versions.toml  (every version, pinned)
    app/build.gradle.kts, app/proguard-rules.pro
    app/src/main/AndroidManifest.xml      (NO internet permission, by design)
    app/src/main/java/com/labref/app/     (MainActivity, NativeBridge, Application)
    app/src/main/res/                     (layout, theme, backup rules)
    app/src/androidTest/                  (on-device smoke test)
  .github/workflows/build.yml  (clinical QA gates the Android build)
  qa/
    run_all.sh                 (runs all four verification methods)
    validate_data.js           (method 2 — data integrity, no browser)
    audit_build.js             (method 3 — built-artifact static audit)
    test_v11_features.py       (method 1 — Playwright feature regression)
    test_all_tests.py          (method 4 — full 180-test corpus sweep)
    test_panel.py, test5.py, test3.py, ...
                               (further Playwright behaviour suites)
  icons/
    icon_master.svg, icon_adaptive_*.svg          (source vector art)
    android/, pwa/, play_store/                    (rendered PNG assets)
    render_icons.py                                (regenerates everything
                                                     from the SVGs)
```

## About the clinical data in this package — please read

`app/labref_data_v1.10.js` is **the complete clinical database**. There is no
larger or fuller dataset held anywhere else, and nothing in it has been
compressed, trimmed or summarised for this package: the file here is
byte-for-byte the one the app is built from.

It contains **180 tests**, which is the full planned corpus. Every record
carries the same field set — reference ranges (with sex, age and pregnancy
variants where clinically real), causes of raised and lowered values,
interference and assay caveats, interpretation notes, the collection tube,
clinician pre-test instructions, patient-facing instructions where useful,
related tests, and a `src[]` array naming where its numbers came from.

Verification evidence for that claim is in QA.md: method 4 opens all 180
detail pages in a real browser and asserts each one actually renders ranges,
causes, notes, prep and a tube, with no console error anywhere in the walk.

## What is left to do

1. **Build and ship the Android app.** The scaffold in `android/` is written
   and ready; `./gradlew assembleDebug` is the next command. Section 9 of
   ANDROID_PACKAGING.md is the pre-release checklist — launcher icons need
   copying in, the signing keystore needs generating, and `targetSdk` should
   be checked against Play's current minimum.
2. **Periodic clinical review** — reference ranges and guideline thresholds
   change. KNOWN_GAPS.md lists the specific items worth re-checking against
   their sources at each release, and SOURCES.md records what each number
   rests on so re-checking is cheap.
3. **Local-laboratory calibration** — the shipped ranges are textbook and
   guideline values. Any department using this should enter its own analyser's
   ranges through the My Lab feature; that is what the feature exists for.

## If you only read one thing

`MainActivity.ASSET_DOMAIN` and `START_URL` must never change. Clinicians'
saved My Lab reference ranges live in `localStorage`, which is keyed to origin;
changing the origin silently wipes them on update while the app continues to
look perfectly healthy. ANDROID_PACKAGING.md §4 explains it, and an
instrumented test exists solely to fail if it happens.
