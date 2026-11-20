/* ============================================================================
   METHOD 5 — stable row-identity guard
   ----------------------------------------------------------------------------
   A user's own lab values (My Lab) are stored against individual reference
   rows, in localStorage on their own device, and must survive every future
   content update. This file is what makes that safe.

   The failure it exists to prevent is specific and silent: a saved override
   keyed to a row that has since come to mean a DIFFERENT population. A
   clinician's adult-female haemoglobin range quietly becoming the newborn
   range, with nothing on screen to say so. No amount of care while editing
   the data prevents that reliably, so it is checked mechanically instead,
   on every build, as a hard gate.

   INVARIANTS
     1. Every range row has a well-formed `rid`, unique within its test.
     2. A published rid NEVER changes meaning. Its stratum dimensions
        (sex / age / preg / analyte) are frozen. Correcting the numbers in an
        interval is fine and expected — that is content maintenance. Changing
        which population a rid refers to is not.
     3. rids are append-only. A row may only disappear if it is explicitly
        listed under `retired` in rid_baseline.json, and a retired rid is
        never reused — not even by backfilling the numeric gap it left.

   A reworded label (`grp`) with unchanged dimensions is reported as a notice,
   not an error: that is cosmetic, and blocking it would tempt someone to
   "fix" the baseline the lazy way.

   Usage:
     node qa/validate_rids.js              verify (exit 1 on any violation)
     node qa/validate_rids.js --update     re-verify, then rewrite the baseline
                                           ONLY if every invariant holds
   ========================================================================= */

const fs = require('fs');
const path = require('path');

/* Glob-resolved, never version-hardcoded — see the note in validate_data.js. */
function sole(pattern, what) {
  const hits = [];
  for (const dir of ['', 'app']) {
    const d = path.join(__dirname, '..', dir);
    if (!fs.existsSync(d)) continue;
    for (const f of fs.readdirSync(d)) if (pattern.test(f)) hits.push(path.join(d, f));
  }
  if (!hits.length) { console.error(`FAIL: no ${what} found`); process.exit(1); }
  if (hits.length > 1) {
    console.error(`FAIL: ${hits.length} ${what} files found `
      + `(${hits.map(h => path.basename(h)).join(', ')}) — remove stale versions.`);
    process.exit(1);
  }
  return hits[0];
}

const DATA = sole(/^labref_data_v.+\.js$/, 'data module');
const BASELINE = path.join(__dirname, 'rid_baseline.json');
const UPDATE = process.argv.includes('--update');

/* ---- load the corpus ---- */
const g = {};
new Function('g', fs.readFileSync(DATA, 'utf8')
  .replace(/<cite[^>]*>/g, '').replace(/<\/cite>/g, '')
  + '; g.T = LABREF_TESTS; g.V = LABREF_VERSION;')(g);
const TESTS = g.T;

const errors = [];
const notices = [];
const err = m => errors.push(m);

/* The frozen meaning of a row. Deliberately excludes lo/hi/txt: an interval's
   numbers are content and may be corrected at any time without invalidating
   anyone's override of a different row. */
const fingerprint = r => ({
  grp: r.grp == null ? null : String(r.grp),
  sex: r.sex == null ? null : String(r.sex),
  age: r.age == null ? null : String(r.age),
  preg: r.preg == null ? null : String(r.preg),
  analyte: r.analyte && r.analyte.key ? String(r.analyte.key) : null
});
const DIMS = ['sex', 'age', 'preg', 'analyte'];   // identity
                                                   // 'grp' is a label, not identity

/* ---- invariant 1: presence, shape, uniqueness ---- */
const current = {};     // testId -> { rid -> fingerprint }
let rowCount = 0;

TESTS.forEach(t => {
  const seen = new Map();
  current[t.id] = {};
  (t.ranges || []).forEach((r, i) => {
    rowCount++;
    const where = `${t.id} row ${i + 1}`;
    if (!r.rid) { err(`[rid] ${where}: no rid — every range row needs one`); return; }
    if (!/^r\d+$/.test(r.rid)) { err(`[rid] ${where}: malformed rid "${r.rid}" (expected r<number>)`); return; }
    if (seen.has(r.rid)) {
      err(`[rid] ${t.id}: rid "${r.rid}" used twice (rows ${seen.get(r.rid)} and ${i + 1}) — `
        + `overrides key on (test, rid), so duplicates make a saved value ambiguous`);
      return;
    }
    seen.set(r.rid, i + 1);
    current[t.id][r.rid] = fingerprint(r);
  });
});

/* ---- invariants 2 and 3: stability against the published baseline ---- */
let baseline = null;
if (fs.existsSync(BASELINE)) {
  baseline = JSON.parse(fs.readFileSync(BASELINE, 'utf8'));
} else if (!UPDATE) {
  err(`[rid] no baseline at qa/rid_baseline.json — generate it with `
    + `\`node qa/validate_rids.js --update\` and commit it, or row identity is unguarded`);
}

let checked = 0, added = 0, relabelled = 0;

if (baseline) {
  const bTests = baseline.tests || {};
  const retired = baseline.retired || {};

  Object.keys(bTests).forEach(testId => {
    const was = bTests[testId];
    const now = current[testId];
    const gone = (retired[testId] || []);

    if (!now) {
      // The whole test is absent. Legitimate only if every one of its rids is retired.
      const unretired = Object.keys(was).filter(rid => !gone.includes(rid));
      if (unretired.length) {
        err(`[rid] test "${testId}" has disappeared, taking ${unretired.length} published `
          + `rid(s) with it (${unretired.slice(0, 5).join(', ')}) — retire them explicitly `
          + `in rid_baseline.json if this is deliberate`);
      }
      return;
    }

    Object.keys(was).forEach(rid => {
      if (!(rid in now)) {
        if (!gone.includes(rid)) {
          err(`[rid] ${testId}/${rid} was published but is now missing — a saved override `
            + `pointing at it would be orphaned. Add it to "retired" if removal is deliberate`);
        }
        return;
      }
      checked++;
      const a = was[rid], b = now[rid];
      const moved = DIMS.filter(k => (a[k] == null ? null : String(a[k])) !== b[k]);
      if (moved.length) {
        err(`[rid] ${testId}/${rid} HAS CHANGED MEANING (${moved.join(', ')}): `
          + `was ${JSON.stringify(DIMS.reduce((o, k) => (o[k] = a[k], o), {}))}, `
          + `now ${JSON.stringify(DIMS.reduce((o, k) => (o[k] = b[k], o), {}))}. `
          + `Any My Lab value saved against this row now refers to a different population. `
          + `Give the new stratum a NEW rid and retire this one.`);
      } else if (a.grp !== b.grp) {
        relabelled++;
        notices.push(`${testId}/${rid}: label reworded "${a.grp}" -> "${b.grp}" `
          + `(dimensions unchanged, so overrides stay valid)`);
      }
    });

    // A retired rid must never come back.
    gone.forEach(rid => {
      if (rid in now) {
        err(`[rid] ${testId}/${rid} is listed as retired but appears in the data again — `
          + `a retired rid is never reused; allocate a fresh number`);
      }
    });

    // New rids must sit above everything ever used in this test, so the gap a
    // retired row left behind can never be backfilled and silently inherit it.
    const everUsed = Object.keys(was).concat(gone)
      .map(r => parseInt(r.slice(1), 10)).filter(n => !isNaN(n));
    const ceiling = everUsed.length ? Math.max(...everUsed) : 0;
    Object.keys(now).forEach(rid => {
      if (rid in was) return;
      added++;
      const n = parseInt(rid.slice(1), 10);
      if (!isNaN(n) && n <= ceiling) {
        err(`[rid] ${testId}/${rid} is a new row reusing a number at or below the highest `
          + `ever published for this test (r${ceiling}) — new rows must continue above it`);
      }
    });
  });

  // Tests absent from the baseline entirely are simply new; count their rows.
  Object.keys(current).forEach(testId => {
    if (!(testId in bTests)) added += Object.keys(current[testId]).length;
  });
}

/* ---- report ---- */
console.log(`checked ${rowCount} range rows across ${TESTS.length} tests`);
if (baseline) {
  console.log(`  · ${checked} published rids verified unchanged in meaning`);
  console.log(`  · ${added} new rid(s) since the baseline`);
  if (relabelled) console.log(`  · ${relabelled} label-only rewording(s)`);
}
if (notices.length) {
  console.log('\nNOTICES (not failures):');
  notices.slice(0, 20).forEach(n => console.log('  · ' + n));
  if (notices.length > 20) console.log(`  · ...and ${notices.length - 20} more`);
}

if (errors.length) {
  console.log(`\nERRORS: ${errors.length}`);
  errors.slice(0, 40).forEach(e => console.log('  ' + e));
  if (errors.length > 40) console.log(`  ...and ${errors.length - 40} more`);
  if (UPDATE) console.log('\nbaseline NOT updated — fix the violations above first');
  process.exit(1);
}

console.log('\nERRORS: none');

if (UPDATE) {
  const out = {
    _comment: 'Published row identities. A rid here must never change meaning or be '
      + 'reused — see qa/validate_rids.js. Regenerate with: node qa/validate_rids.js --update',
    generated_for_version: g.V,
    retired: (baseline && baseline.retired) || {},
    tests: current
  };
  fs.writeFileSync(BASELINE, JSON.stringify(out, null, 1) + '\n');
  console.log(`baseline written: ${rowCount} rows across ${TESTS.length} tests`);
}
