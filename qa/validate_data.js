/* ============================================================================
   LabRef — data integrity validator  (test method 2: no browser, no DOM)
   Checks the content database for mechanical errors that are invisible in the
   UI: wrong conversion factors, impossible ranges, broken cross-references,
   schema violations, duplicated ids.
       node validate_data.js
   Exits non-zero if any ERROR is found. WARNs are advisory.
   ========================================================================== */
const fs = require('fs');
const path = require('path');

const DATA = process.argv[2] || ['labref_data_v1.10.js', 'app/labref_data_v1.10.js']
  .map(r=>path.join(__dirname,'..',r)).find(p=>fs.existsSync(p));
let code = fs.readFileSync(DATA, 'utf8')
  .replace(/<cite[^>]*>/g, '').replace(/<\/cite>/g, '');
code += '\nmodule.exports={LABREF_VERSION,LABREF_CATEGORIES,LABREF_TUBES,LABREF_TESTS};';
const tmp = path.join(require('os').tmpdir(), 'labref_validate_' + process.pid + '.js');
fs.writeFileSync(tmp, code);
const { LABREF_VERSION, LABREF_CATEGORIES, LABREF_TUBES, LABREF_TESTS } = require(tmp);
fs.unlinkSync(tmp);

const errors = [], warns = [];
const err  = (t, m) => errors.push(`[${t}] ${m}`);
const warn = (t, m) => warns.push(`[${t}] ${m}`);

const AGES = ['neonate','infant','child','adolescent','adult'];
const SEXES = ['M','F','any'];
const PREGS = [null,'any','T1','T2','T3'];
const REQUIRED = ['id','name','abbr','syn','cat','specimen','tube','prep','units','ranges',
                  'inc','dec','interf','pearls','rel'];

const catIds  = new Set(LABREF_CATEGORIES.map(c=>c.id));
const tubeIds = new Set(LABREF_TUBES.map(t=>t.id));
const testIds = new Set(LABREF_TESTS.map(t=>t.id));

/* ---- categories & tubes ---- */
const seenCat = new Set();
LABREF_CATEGORIES.forEach(c=>{
  if(seenCat.has(c.id)) err('cat', `duplicate category id "${c.id}"`);
  seenCat.add(c.id);
  ['id','name','icon','color'].forEach(f=>{ if(!c[f]) err('cat', `${c.id}: missing ${f}`); });
  if(c.color && !/^#[0-9a-f]{6}$/i.test(c.color)) err('cat', `${c.id}: bad colour ${c.color}`);
});
const seenTube = new Set(), seenOrder = new Map();
LABREF_TUBES.forEach(t=>{
  if(seenTube.has(t.id)) err('tube', `duplicate tube id "${t.id}"`);
  seenTube.add(t.id);
  ['id','name','colors','additive','inv','uses','notes'].forEach(f=>{
    if(!t[f]) err('tube', `${t.id}: missing ${f}`); });
  if(typeof t.order !== 'number') err('tube', `${t.id}: order must be a number`);
  if(t.order > 0){
    if(seenOrder.has(t.order)) warn('tube',
      `draw-order ${t.order} shared by "${seenOrder.get(t.order)}" and "${t.id}"`);
    seenOrder.set(t.order, t.id);
  }
});

/* ---- tests ---- */
const seenTest = new Set();
LABREF_TESTS.forEach(t=>{
  const T = t.id || '(no id)';
  if(seenTest.has(t.id)) err('test', `duplicate test id "${t.id}"`);
  seenTest.add(t.id);

  REQUIRED.forEach(f=>{ if(t[f]===undefined) err('schema', `${T}: missing field "${f}"`); });
  if(t.id && !/^[a-z0-9]+$/.test(t.id)) err('schema', `${T}: id must be lowercase alphanumeric`);
  if(t.cat && !catIds.has(t.cat)) err('ref', `${T}: unknown category "${t.cat}"`);
  if(t.tube && t.tube.id && !tubeIds.has(t.tube.id)) err('ref', `${T}: unknown tube "${t.tube.id}"`);
  if(t.tube && !t.tube.vol) err('schema', `${T}: tube.vol missing`);
  if(t.tube && !t.tube.handling) err('schema', `${T}: tube.handling missing`);
  (t.rel||[]).forEach(r=>{ if(!testIds.has(r)) warn('ref', `${T}: rel -> unknown test "${r}"`); });
  if(t.prep){
    if(!t.prep.fasting) err('schema', `${T}: prep.fasting missing`);
    if(!Array.isArray(t.prep.items)) err('schema', `${T}: prep.items must be an array`);
    if(t.prep.patient && !Array.isArray(t.prep.patient))
      err('schema', `${T}: prep.patient must be an array`);
  }
  ['syn','inc','dec','interf','pearls','rel'].forEach(f=>{
    if(t[f]!==undefined && !Array.isArray(t[f])) err('schema', `${T}: ${f} must be an array`); });
  if(Array.isArray(t.inc) && !t.inc.length) warn('content', `${T}: no causes of raised value`);
  if(Array.isArray(t.dec) && !t.dec.length) warn('content', `${T}: no causes of low value`);
  if(Array.isArray(t.pearls) && !t.pearls.length) warn('content', `${T}: no interpretation notes`);
  /* provenance: every record should name the source its numbers came from,
     so a later reader can tell a guideline-backed value from a recalled one */
  if(!t.src || !Array.isArray(t.src) || !t.src.length)
    warn('provenance', `${T}: no src[] — reference values have no recorded source`);

  if(!t.units) { err('schema', `${T}: units missing`); return; }
  if(!t.units.conv || !t.units.si) err('schema', `${T}: units.conv/si missing`);

  /* ---- ranges ---- */
  if(!Array.isArray(t.ranges) || !t.ranges.length){ err('schema', `${T}: no ranges`); return; }
  const keys = new Map();           // analyte key -> label, for consistency checks
  t.ranges.forEach((r,i)=>{
    const R = `${T} range[${i}] "${r.grp||'?'}"`;
    if(!r.grp) err('schema', `${R}: missing grp`);
    if(!SEXES.includes(r.sex)) err('schema', `${R}: bad sex "${r.sex}"`);
    if(!AGES.includes(r.age))  err('schema', `${R}: bad age "${r.age}"`);
    if(!PREGS.includes(r.preg===undefined?null:r.preg)) err('schema', `${R}: bad preg "${r.preg}"`);
    if(r.preg && r.preg!==null && r.sex==='M')
      err('logic', `${R}: pregnancy range marked sex "M"`);
    if(!r.conv || !r.si) { err('schema', `${R}: missing conv/si block`); return; }

    ['conv','si'].forEach(sys=>{
      const u = r[sys];
      if(u.lo!=null && typeof u.lo!=='number') err('schema', `${R}: ${sys}.lo not numeric`);
      if(u.hi!=null && typeof u.hi!=='number') err('schema', `${R}: ${sys}.hi not numeric`);
      if(u.lo!=null && u.hi!=null && u.lo>u.hi) err('logic', `${R}: ${sys} lo>hi (${u.lo}>${u.hi})`);
      if(u.lo==null && u.hi==null && !u.txt)
        err('logic', `${R}: ${sys} has neither bounds nor txt`);
    });

    /* analyte metadata consistency */
    if(r.analyte){
      const a = r.analyte;
      if(!a.key)   err('schema', `${R}: analyte missing key`);
      if(!a.label) err('schema', `${R}: analyte missing label`);
      if(a.key){
        if(keys.has(a.key) && keys.get(a.key)!==a.label)
          err('logic', `${T}: analyte key "${a.key}" used with two labels `
            + `("${keys.get(a.key)}" and "${a.label}")`);
        keys.set(a.key, a.label);
      }
    }

    /* conversion factor check: stored SI must match conv x factor */
    const an = r.analyte || {};
    const noConv = !!an.noConvert;
    const factor = an.factor!=null ? an.factor : t.units.factor;
    if(!noConv && factor!=null){
      ['lo','hi'].forEach(k=>{
        const c = r.conv[k], s = r.si[k];
        if(c==null || s==null || c===0) return;
        const implied = c*factor;
        /* Tolerance has to allow for the fact that reference intervals are
           PUBLISHED independently in each unit system and rounded to the
           precision labs report, rather than being computed by multiplication.
           Real examples that are correct but not arithmetically exact:
             bilirubin 1.2 mg/dL -> published 21 umol/L (x17.1 gives 20.52)
             vitamin D  29 ng/mL -> published 74 nmol/L (Endocrine Society
                                    insufficiency band 51-74; x2.496 gives 72.4)
           So: allow half a unit of the stored value's own last significant
           digit, or 3% — whichever is larger. A genuinely wrong factor is off
           by tens of percent or more (the triglycerides bug this check was
           written for was 2.3x), so sensitivity to real errors is unaffected. */
        const decimals = (String(s).split('.')[1] || '').length;
        const halfStep = 0.5 * Math.pow(10, -decimals);
        const tol = Math.max(Math.abs(s)*0.03, halfStep);
        if(Math.abs(implied-s) > tol){
          err('units', `${R}: ${k} conv ${c} x factor ${factor} = ${implied.toFixed(4)} `
            + `but si says ${s}  (implied factor ${(s/c).toFixed(5)})`);
        }
      });
    }
  });

  /* panel coherence: a test either tags every numeric row or none of them */
  const tagged = t.ranges.filter(r=>r.analyte).length;
  if(tagged>0 && tagged<t.ranges.length){
    const untagged = t.ranges.filter(r=>!r.analyte).map(r=>r.grp);
    warn('panel', `${T}: ${tagged}/${t.ranges.length} rows tagged; untagged treated as `
      + `info-only rows -> ${JSON.stringify(untagged)}`);
  }

  /* critical value coherence */
  if(t.critical){
    if(!t.critical.txt) err('schema', `${T}: critical.txt missing`);
    if(t.critical.analyte){
      if(!Array.isArray(t.critical.analyte)) err('schema', `${T}: critical.analyte must be an array`);
      else t.critical.analyte.forEach(k=>{
        if(!keys.has(k)) err('ref', `${T}: critical.analyte references unknown component "${k}"`);
      });
    }
    if(tagged>0 && !t.critical.analyte)
      warn('panel', `${T}: panel test has an unscoped critical value `
        + `(fine only if it applies to every component or names them inline)`);
  }
});

/* ---- report ---- */
console.log(`LabRef data v${LABREF_VERSION}: `
  + `${LABREF_TESTS.length} tests, ${LABREF_CATEGORIES.length} categories, ${LABREF_TUBES.length} tubes`);
console.log(`checked ${LABREF_TESTS.reduce((n,t)=>n+t.ranges.length,0)} range rows\n`);
if(warns.length){ console.log(`WARNINGS (${warns.length}):`); warns.forEach(w=>console.log('  '+w)); console.log(); }
if(errors.length){ console.log(`ERRORS (${errors.length}):`); errors.forEach(e=>console.log('  '+e)); }
else console.log('ERRORS: none');
process.exit(errors.length ? 1 : 0);
