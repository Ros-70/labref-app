/* ============================================================================
   METHOD 5b — self-test of the row-identity guard
   ----------------------------------------------------------------------------
   validate_rids.js is the only thing standing between a future content edit
   and a clinician's saved lab values silently re-pointing at the wrong
   population. A guard that has never been observed to FAIL is not evidence of
   anything, so this drives it through each violation it claims to catch and
   asserts it rejects them.

   It runs against a small synthetic corpus in a temp directory, never the real
   data — so it is fast, readable, and cannot touch the clinical content.
   ========================================================================= */

const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

const GUARD = path.join(__dirname, 'validate_rids.js');

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'labref-rid-selftest-'));
fs.mkdirSync(path.join(root, 'qa'));
fs.mkdirSync(path.join(root, 'app'));
fs.copyFileSync(GUARD, path.join(root, 'qa', 'validate_rids.js'));

/* A deliberately tiny corpus: one single-analyte test, one panel test. */
const baseRows = [
  { rid: 'r1', grp: 'Adult male',   sex: 'M', age: 'adult', preg: null },
  { rid: 'r2', grp: 'Adult female', sex: 'F', age: 'adult', preg: null },
  { rid: 'r3', grp: 'Newborn',      sex: 'any', age: 'newborn', preg: null }
];

function writeCorpus(rows) {
  const tests = [{ id: 'demo', name: 'Demo', ranges: rows }];
  const js = 'const LABREF_VERSION = "9.9-test";\n'
    + 'const LABREF_TESTS = ' + JSON.stringify(tests, null, 1) + ';\n';
  fs.writeFileSync(path.join(root, 'app', 'labref_data_v9.9.js'), js);
}

function runGuard(args) {
  try {
    const out = execFileSync('node', [path.join(root, 'qa', 'validate_rids.js'), ...(args || [])],
      { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
    return { code: 0, out };
  } catch (e) {
    return { code: e.status == null ? 1 : e.status, out: (e.stdout || '') + (e.stderr || '') };
  }
}

/* Establish the baseline the mutations will be judged against. */
writeCorpus(baseRows);
const seed = runGuard(['--update']);
if (seed.code !== 0) {
  console.error('SELF-TEST SETUP FAILED — guard rejected a clean corpus:\n' + seed.out);
  process.exit(1);
}

const clone = () => JSON.parse(JSON.stringify(baseRows));
let pass = 0;
const failures = [];

/* Each case: mutate, run, expect a specific verdict. */
const cases = [
  {
    label: 'a row with no rid is rejected',
    rows: () => { const r = clone(); delete r[1].rid; return r; },
    expect: 'reject', match: /no rid/i
  },
  {
    label: 'a duplicate rid is rejected',
    rows: () => { const r = clone(); r[2].rid = 'r1'; return r; },
    expect: 'reject', match: /used twice/i
  },
  {
    label: 'a malformed rid is rejected',
    rows: () => { const r = clone(); r[0].rid = 'adult-male'; return r; },
    expect: 'reject', match: /malformed/i
  },
  {
    label: 'REPOINTING a published rid at another population is rejected',
    rows: () => { const r = clone(); r[0].sex = 'F'; return r; },   // r1: male -> female
    expect: 'reject', match: /CHANGED MEANING/
  },
  {
    label: 'repointing across age bands is rejected',
    rows: () => { const r = clone(); r[1].age = 'newborn'; return r; },
    expect: 'reject', match: /CHANGED MEANING/
  },
  {
    label: 'silently deleting a published row is rejected',
    rows: () => clone().slice(0, 2),                                 // r3 vanishes
    expect: 'reject', match: /published but is now missing/i
  },
  {
    label: 'a new row reusing a low rid number is rejected',
    rows: () => { const r = clone(); r.push({ rid: 'r2', grp: 'Extra', sex: 'any', age: 'child', preg: null }); return r; },
    expect: 'reject', match: /used twice|at or below/i
  },
  {
    label: 'correcting an interval\'s NUMBERS is allowed',
    rows: () => { const r = clone(); r[0].conv = { lo: 13.5, hi: 17.5 }; return r; },
    expect: 'accept'
  },
  {
    label: 'rewording a label is allowed, and reported as a notice',
    rows: () => { const r = clone(); r[1].grp = 'Adult female (non-pregnant)'; return r; },
    expect: 'accept', match: /reworded/i
  },
  {
    label: 'appending a row above the ceiling is allowed',
    rows: () => { const r = clone(); r.push({ rid: 'r4', grp: 'Child', sex: 'any', age: 'child', preg: null }); return r; },
    expect: 'accept'
  }
];

for (const c of cases) {
  writeCorpus(c.rows());
  const res = runGuard();
  const rejected = res.code !== 0;
  const wanted = c.expect === 'reject';

  if (rejected !== wanted) {
    failures.push(`${c.label}\n      expected the guard to ${c.expect.toUpperCase()}, `
      + `but it exited ${res.code}\n      output: ${res.out.trim().split('\n').slice(-4).join(' | ')}`);
    continue;
  }
  if (c.match && !c.match.test(res.out)) {
    failures.push(`${c.label}\n      verdict was right but the message did not match `
      + `${c.match}\n      output: ${res.out.trim().split('\n').slice(-4).join(' | ')}`);
    continue;
  }
  pass++;
  console.log(`  PASS  ${c.label}`);
}

/* The retirement path: a deliberate removal, declared, is accepted. */
writeCorpus(clone().slice(0, 2));
const bPath = path.join(root, 'qa', 'rid_baseline.json');
const b = JSON.parse(fs.readFileSync(bPath, 'utf8'));
b.retired = { demo: ['r3'] };
fs.writeFileSync(bPath, JSON.stringify(b, null, 1));
let res = runGuard();
if (res.code === 0) { pass++; console.log('  PASS  a removal declared under "retired" is accepted'); }
else failures.push('a removal declared under "retired" should be accepted\n      output: ' + res.out.trim());

/* ...but a retired rid may never return. */
writeCorpus(clone());   // r3 is back
res = runGuard();
if (res.code !== 0 && /retired/i.test(res.out)) {
  pass++; console.log('  PASS  reviving a retired rid is rejected');
} else {
  failures.push('reviving a retired rid should be rejected\n      output: ' + res.out.trim());
}

fs.rmSync(root, { recursive: true, force: true });

console.log(`\n${pass} guard behaviours verified`);
if (failures.length) {
  console.log(`\nERRORS: ${failures.length}`);
  failures.forEach(f => console.log('  ' + f));
  console.log('\nThe row-identity guard is not behaving as documented. Until this passes, '
    + 'a content edit could silently re-point a saved My Lab value at the wrong population.');
  process.exit(1);
}
console.log('\nERRORS: none');
