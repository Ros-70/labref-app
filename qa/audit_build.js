/* ============================================================================
   LabRef — built-artifact structural audit   (test method 3: static analysis)

   Neither the browser tests nor the data validator look at the shipped file
   itself. This does: it reads the built LabRef_v*.html as text and checks the things
   that make it a correct, self-contained, offline single-file app.
       node audit_build.js [path-to-built-html]
   Exits non-zero on any ERROR.
   ========================================================================== */
const fs = require('fs');
const path = require('path');

/* Glob-resolved, never version-hardcoded — see the note in validate_data.js. */
function sole(patterns, what){
  const hits = [];
  for(const dir of ['', 'app']){
    const d = path.join(__dirname, '..', dir);
    if(!fs.existsSync(d)) continue;
    for(const f of fs.readdirSync(d)) if(patterns.test(f)) hits.push(path.join(d, f));
  }
  if(!hits.length){ console.error(`FAIL: no ${what} found — run build.py first`); process.exit(1); }
  if(hits.length > 1){
    console.error(`FAIL: ${hits.length} ${what} files found (${hits.map(h=>path.basename(h)).join(', ')})`
      + ` — remove stale versions so the suite cannot verify the wrong one`);
    process.exit(1);
  }
  return hits[0];
}
const FILE = process.argv[2] || sole(/^LabRef_v.+\.html$/, 'built app');
const html = fs.readFileSync(FILE, 'utf8');
const errors = [], warns = [], notes = [];
const err  = (t,m) => errors.push(`[${t}] ${m}`);
const warn = (t,m) => warns.push(`[${t}] ${m}`);

/* ---- 1. build completed cleanly ---- */
['/*__LABREF_DATA__*/','/*__MEDREF_DATA__*/'].forEach(ph=>{
  if(html.includes(ph)) err('build', `unreplaced data placeholder ${ph} in output`);
});
if(!/LABREF_TESTS\s*=/.test(html)) err('build','data module not present in output');
if(/<cite[\s>]/.test(html)) err('build','raw <cite> citation markup reached the shipped file');

/* ---- 2. OFFLINE GUARANTEE: nothing may be fetched from the network ---- */
const ext = [...html.matchAll(/(?:src|href)\s*=\s*["'](https?:)?\/\/[^"']+["']/gi)].map(m=>m[0]);
if(ext.length) err('offline', `${ext.length} external resource reference(s): ${ext.slice(0,3).join(', ')}`);
[/@import\s+url\(/i, /fetch\s*\(/, /XMLHttpRequest/, /navigator\.sendBeacon/].forEach(rx=>{
  if(rx.test(html)) err('offline', `network/remote-loading construct found: ${rx}`);
});
const fontFace = /@font-face/i.test(html);
if(fontFace) warn('offline','@font-face present — confirm the font is embedded, not fetched');

/* ---- 3. no duplicate element ids in the static shell ----
   (ids inside JS template literals are rendered one view at a time, so only
   the static markup above the <script> is checked) */
const staticPart = html.slice(0, html.indexOf('<script'));
const ids = [...staticPart.matchAll(/\bid\s*=\s*"([^"]+)"/g)].map(m=>m[1]);
const dupes = ids.filter((v,i)=>ids.indexOf(v)!==i);
if(dupes.length) err('dom', `duplicate id(s) in static markup: ${[...new Set(dupes)].join(', ')}`);

/* ---- 4. every nav tab has a view section, and vice versa ---- */
const navs  = [...staticPart.matchAll(/data-nav="([a-z]+)"/g)].map(m=>m[1]);
const views = [...staticPart.matchAll(/id="v-([a-z]+)"/g)].map(m=>m[1]);
navs.forEach(n=>{ if(!views.includes(n)) err('nav', `tab "${n}" has no #v-${n} section`); });
views.filter(v=>v!=='detail').forEach(v=>{
  if(!navs.includes(v)) warn('nav', `view #v-${v} has no nav tab (reachable only in code?)`);
});

/* ---- 5. CSS custom properties: everything used is defined ---- */
const used    = new Set([...html.matchAll(/var\((--[a-z0-9-]+)/gi)].map(m=>m[1]));
const defined = new Set([...html.matchAll(/(--[a-z0-9-]+)\s*:/gi)].map(m=>m[1]));
[...used].forEach(v=>{ if(!defined.has(v)) err('css', `var(${v}) used but never defined`); });
[...defined].forEach(v=>{ if(!used.has(v)) warn('css', `${v} defined but never used`); });

/* ---- 6. themes are complete: CSS block + crumb colour + meta colour ---- */
const labels = [...html.matchAll(/\["([a-z]+)","[^"]+"\]/g)].map(m=>m[1])
  .filter(t=>html.includes(`[data-theme="${t}"]`) || t==='light');
const themeColorMap = (html.match(/const tc = \{([^}]+)\}/)||[])[1] || '';
labels.forEach(t=>{
  if(t!=='light' && !html.includes(`[data-theme="${t}"]{`))
    err('theme', `theme "${t}" listed but has no CSS block`);
  if(!new RegExp(`\\b${t}\\s*:`).test(themeColorMap))
    err('theme', `theme "${t}" missing from the theme-color meta map`);
});
/* every theme must resolve --crumb-now (explicitly or via the #appbar default) */
if(!/#appbar\{--crumb-now:/.test(html))
  err('theme','no default --crumb-now on #appbar; a new theme would render the current crumb unstyled');
notes.push(`themes found: ${labels.join(', ')}`);

/* ---- 7. event wiring: every data-* hook used in markup is bound in script ---- */
const scriptPart = html.slice(html.indexOf('<script'));
['data-nav','data-cat','data-test','data-tool','data-th','data-crumb','data-blk','data-mode'].forEach(attr=>{
  const inMarkup = new RegExp(`${attr}=`).test(html);
  const bound = new RegExp(`${attr}|dataset\\.${attr.replace('data-','')}`).test(scriptPart);
  if(inMarkup && !bound) err('wiring', `${attr} appears in markup but is never read in script`);
});

/* ---- 8. hygiene ---- */
const logs = (scriptPart.match(/console\.(log|debug|warn)\(/g)||[]).length;
if(logs) warn('hygiene', `${logs} console.log/debug/warn call(s) left in the shipped script`);
const todos = (html.match(/\b(TODO|FIXME|XXX|HACK)\b/g)||[]).length;
if(todos) warn('hygiene', `${todos} TODO/FIXME marker(s) in the shipped file`);
if(!/<meta name="viewport"/i.test(html)) err('mobile','viewport meta tag missing');
if(!/<meta name="theme-color"/i.test(html)) warn('mobile','theme-color meta tag missing');
if(!/^<!DOCTYPE html>/i.test(html.trim())) err('html','missing DOCTYPE');

/* legacy name should survive ONLY as the storage-migration fallback */
/* widen the window enough to capture the surrounding comment or identifier
   that marks an occurrence as part of the deliberate migration/compat path */
const medrefHits = [...html.matchAll(/.{0,120}medref.{0,120}/gi)].map(m=>m[0].trim());
const legit = medrefHits.filter(h=>
  /LS_LEGACY|medref_v1|medref-backup|medref-lab-profile|pre-rename|legacy|migrat|lose them|accept .*builds/i.test(h));
if(medrefHits.length !== legit.length)
  warn('rename', `${medrefHits.length-legit.length} MedRef mention(s) outside the migration path`);
notes.push(`legacy MedRef references: ${medrefHits.length} (all in migration/compat paths: ${medrefHits.length===legit.length})`);

/* ---- 9. tag balance ---- */
['script','style','header','main','nav'].forEach(tag=>{
  const open  = (html.match(new RegExp(`<${tag}[\\s>]`,'gi'))||[]).length;
  const close = (html.match(new RegExp(`</${tag}>`,'gi'))||[]).length;
  if(open!==close) err('html', `<${tag}> opened ${open}x but closed ${close}x`);
});

/* ---- report ---- */
const kb = (Buffer.byteLength(html,'utf8')/1024).toFixed(0);
console.log(`audited ${path.basename(FILE)} — ${kb} KB, self-contained single file`);
notes.forEach(n=>console.log('  · '+n));
console.log();
if(warns.length){ console.log(`WARNINGS (${warns.length}):`); warns.forEach(w=>console.log('  '+w)); console.log(); }
console.log(errors.length ? `ERRORS (${errors.length}):` : 'ERRORS: none');
errors.forEach(e=>console.log('  '+e));
process.exit(errors.length ? 1 : 0);
