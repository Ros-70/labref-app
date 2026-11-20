/* ============================================================================
   METHOD 6 — row-selection tie-break guard
   ----------------------------------------------------------------------------
   Stage 2a found that bestRange() silently broke a tie between two or more
   ref/method rows that score identically for the current patient mode (e.g.
   ESR "male <50y" vs "male >=50y" both just match sex=male, age=adult) by
   taking whichever came first in the array — the same class of silent-
   wrong-value risk as the original My Lab bug, just in the interpreter's
   row-picker instead of the override store. shell.html now makes the user
   pick by label instead of guessing (see tiedCandidates()/activeRange()).

   Stage 2b found the same shape of problem among dx/cutoff/target rows, with
   two different correct answers: most are a genuine value-ordered ladder
   (Vitamin D's deficient/insufficient/sufficient/toxic bands), which the
   interpreter now resolves automatically from the entered number
   (classifyAgainstLadder()); a handful are NOT a ladder at all — picking
   between them needs clinical context a number can't supply (which drug,
   which indication) — and the interpreter falls back to naming the
   candidates rather than guessing.

   This file is the regression guard for BOTH: it recomputes every tie in the
   current data and fails the build if a NEW one appears in either category
   that isn't in qa/known_tie_groups.json's reviewed lists. A content change
   that happens to introduce a fresh tie (a new age-banded row, a new
   diagnostic threshold sharing a key with an existing one) gets a human
   decision — block-and-ask, or confirm it's a genuine ladder — instead of
   silently taking whichever mechanism happens to fire by default.

   Usage:  node qa/validate_ties.js
   ========================================================================= */

const fs = require('fs');
const path = require('path');

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
const KNOWN = path.join(__dirname, 'known_tie_groups.json');

const g = {};
new Function('g', fs.readFileSync(DATA, 'utf8')
  .replace(/<cite[^>]*>/g, '').replace(/<\/cite>/g, '')
  + '; g.T = LABREF_TESTS;')(g);
const TESTS = g.T;
const known = JSON.parse(fs.readFileSync(KNOWN, 'utf8'));

const keyOf = r => (r.analyte ? r.analyte.key : '_') + '|'
  + [r.sex || 'any', r.age || 'any', r.preg || 'none'].join('|');

function bounds(r) {
  const u = r.conv || {};
  return [u.lo != null ? u.lo : -Infinity, u.hi != null ? u.hi : Infinity];
}
/* Mirrors isValueLadder() in shell.html: a clean ladder is every pair either
   non-overlapping or one fully nested inside the other (a severity
   refinement); anything else needs clinical context, not a number, to pick. */
function isValueLadder(rows) {
  const withBounds = rows.filter(r => r.conv && (r.conv.lo != null || r.conv.hi != null));
  if (withBounds.length < rows.length) return false;
  for (let i = 0; i < withBounds.length; i++) {
    for (let j = i + 1; j < withBounds.length; j++) {
      const [alo, ahi] = bounds(withBounds[i]), [blo, bhi] = bounds(withBounds[j]);
      if (alo < bhi && blo < ahi) {
        const nested = (alo <= blo && bhi <= ahi) || (blo <= alo && ahi <= bhi);
        if (!nested) return false;
      }
    }
  }
  return withBounds.length > 0;
}

/* ---- category 1: ref/method ties (blocking in the UI) ---- */
const refMethodTies = [];
TESTS.forEach(t => {
  const seen = {};
  (t.ranges || []).forEach(r => {
    if (r.kind !== 'ref' && r.kind !== 'method') return;
    const k = keyOf(r);
    (seen[k] = seen[k] || []).push(r);
  });
  Object.entries(seen).forEach(([k, rows]) => {
    if (rows.length > 1) refMethodTies.push({ test: t.id, key: k, rids: rows.map(r => r.rid).sort() });
  });
});

/* ---- category 2: dx/cutoff/target groups that are NOT a clean ladder ---- */
const ladderFallbacks = [];
TESTS.forEach(t => {
  const seen = {};
  (t.ranges || []).forEach(r => {
    if (!['dx', 'cutoff', 'target'].includes(r.kind)) return;
    const k = keyOf(r);
    (seen[k] = seen[k] || []).push(r);
  });
  Object.entries(seen).forEach(([k, rows]) => {
    if (rows.length > 1 && !isValueLadder(rows)) {
      ladderFallbacks.push({ test: t.id, key: k, rids: rows.map(r => r.rid).sort() });
    }
  });
});

function sameSet(a, b) {
  if (a.length !== b.length) return false;
  const bs = new Set(b);
  return a.every(x => bs.has(x));
}

function checkAgainst(found, reviewed, label) {
  const errors = [];
  found.forEach(f => {
    const match = reviewed.find(r => r.test === f.test && r.key === f.key);
    if (!match) {
      errors.push(`[ties] NEW, unreviewed ${label} tie: ${f.test} (${f.key}) rows ${f.rids.join(', ')} — `
        + `add it to qa/known_tie_groups.json's "${label === 'ref/method' ? 'groups' : 'ladder_fallback_groups'}" `
        + `once you've confirmed it's genuine (and, for a ladder fallback, that it really isn't a value ladder).`);
      return;
    }
    if (!sameSet(f.rids, match.rids)) {
      errors.push(`[ties] ${label} tie ${f.test} (${f.key}) has changed which rows tie — `
        + `was ${match.rids.join(', ')}, now ${f.rids.join(', ')}. Review and update qa/known_tie_groups.json.`);
    }
  });
  const stale = reviewed.filter(r => !found.some(f => f.test === r.test && f.key === r.key));
  return { errors, stale };
}

const refCheck = checkAgainst(refMethodTies, known.groups || [], 'ref/method');
const ladderCheck = checkAgainst(ladderFallbacks, known.ladder_fallback_groups || [], 'ladder-fallback');

console.log(`ref/method ties found   : ${refMethodTies.length} (reviewed: ${(known.groups || []).length})`);
console.log(`ladder-fallback groups   : ${ladderFallbacks.length} (reviewed: ${(known.ladder_fallback_groups || []).length})`);

const staleAll = refCheck.stale.concat(ladderCheck.stale);
if (staleAll.length) {
  console.log('\nNOTICES (not failures) — reviewed entries no longer reproduced, probably stale:');
  staleAll.forEach(s => console.log(`  · ${s.test} (${s.key})`));
}

const errors = refCheck.errors.concat(ladderCheck.errors);
if (errors.length) {
  console.log(`\nERRORS: ${errors.length}`);
  errors.forEach(e => console.log('  ' + e));
  process.exit(1);
}
console.log('\nERRORS: none');
