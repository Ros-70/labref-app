# Sources & Provenance

## 1. Research standard applied

Every record was researched from authoritative sources: CLSI standards
(including GP41 7th ed. for order of draw), the major guideline bodies
(WHO, KDIGO / National Kidney Foundation, ADA, ESC/EAS, ACC/AHA, ATA,
Endocrine Society, AASLD/EASL, IDSA, ACG, ACR/EULAR, IMWG, ATS/ERS,
CFF/ECFS), national Indian programme guidance where it is what clinicians
here actually follow (NVBDCP for malaria and dengue, NTEP for tuberculosis,
NACO for HIV, DIPSI for gestational diabetes, PCPNDT for prenatal
diagnostics), FDA/MHRA safety communications for assay interference, and
peer-reviewed literature for specific numeric claims — formulas, cut-offs,
and interference mechanisms.

Where a reference interval is genuinely platform-specific rather than
universal, the record is flagged `assayDep:true` and the app says so, rather
than presenting a single borrowed number as though it were authoritative.

## 2. The `src[]` provenance field

**New in v1.10, and present on all 180 records.** Each test record carries:

```js
src:["ATA 2017 guideline — trimester-specific TSH ranges in pregnancy",
     "Standard adult TSH reference interval (assay-dependent)"]
```

`src[]` names the guideline or standard that the record's **reference limits
and decision thresholds** rest on — not a full bibliography of every
sentence in the record. The purpose is operational: when a guideline is
revised, you can find in seconds which records need re-checking, without
re-researching the whole corpus. See the re-check list in KNOWN_GAPS.md.

The field is not rendered in the UI. It is maintenance metadata for whoever
holds the data next, which is why it lives in the data file rather than in a
separate document that would drift out of sync.

`qa/validate_data.js` emits a warning for any record without `src[]`. That
check is the mechanism that keeps this from decaying: a new test added
without provenance shows up on the next validation run.

## 3. How this replaced the v1.1 citation markers

At the v1.1 freeze, twelve claims in `pearls[]` and `interf[]` carried
inline `<cite index="N-M">` markers whose underlying source URLs had not
been captured into a bibliography. The markers pointed at search-result
indices from the original research session and so were meaningless outside
it. `build.py` stripped them before shipping, so clinicians never saw them,
but they were dead weight in the source and a gap that would have compounded
across another 146 records.

v1.10 resolved it by **removing the markers from the data** and replacing
them with the structured `src[]` field above. `build.py` still strips any
`<cite>` tag it finds, and `qa/audit_build.js` fails the build if one
reaches the shipped artifact — so the old pattern cannot creep back in. The
build currently reports `cite tags remaining: 0`.

## 4. What this is and is not

**It is** a record of where each test's numbers came from, sufficient to
re-verify or update them deliberately.

**It is not** a clinician-facing citation feature. Whether LabRef should
show sources in the UI remains an open product decision:

- *Arguments for*: clinicians asked to act on a threshold may reasonably
  want to know whose threshold it is, particularly for contested values
  (vitamin D sufficiency, pregnancy TSH, LDL-C targets).
- *Arguments against*: it adds UI weight to every detail page for something
  most users will never open, and a partial citation system can read as more
  authoritative than it is.

If the decision is to surface them, `src[]` is already the right shape —
it would need only a collapsed "Sources" block on the detail page, following
the existing `block()` pattern, and no data migration.

## 5. A standing caution to carry into the native build

Reference intervals are **method- and population-dependent**. The values
here are textbook and guideline values, correct as published, and they are
the right default for a reference app — but they are not a substitute for
the ranges a particular laboratory's own analyser produces.

This is exactly why the My Lab feature exists, and it should stay prominent
in the native build rather than being treated as an advanced option. Any
release notes or Play Store description should say plainly that the app is a
clinician's reference aid and that local laboratory ranges take precedence.
