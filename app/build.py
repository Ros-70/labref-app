import re, io, sys, glob, os

# The data file and the build output are resolved by glob, never hardcoded.
# Hardcoding the version into these paths once let the QA suite pass against a
# stale build from a previous version while the current data sat unverified.
# Globbing with a strict "exactly one" assertion makes that failure impossible:
# a leftover file from an older version is a hard error, not a silent fallback.
def sole(pattern, what):
    hits = sorted(glob.glob(pattern))
    if not hits:
        sys.exit('ERROR: no %s matching %s' % (what, pattern))
    if len(hits) > 1:
        sys.exit('ERROR: %d files match %s (%s) — remove stale versions so the '
                 'build and the QA suite cannot disagree about which is current'
                 % (len(hits), pattern, ', '.join(os.path.basename(h) for h in hits)))
    return hits[0]

DATA  = sole('labref_data_v*.js', 'data module')
SHELL = 'shell.html'

data = io.open(DATA, encoding='utf-8').read()

# The output filename tracks the data module's version token, so the two can
# never drift apart.
m = re.search(r'labref_data_v(.+)\.js$', os.path.basename(DATA))
if not m:
    sys.exit('ERROR: cannot read a version token from ' + DATA)
OUT = 'LabRef_v%s.html' % m.group(1)
shell = io.open(SHELL, encoding='utf-8').read()

# strip research citation markup from content strings
data = re.sub(r'<\\?/?cite[^>]*>', '', data)
data = re.sub(r'<cite index=\\"[^"]*\\">', '', data)
data = data.replace('</cite>', '')

if '/*__LABREF_DATA__*/' not in shell:
    sys.exit('ERROR: data placeholder /*__LABREF_DATA__*/ not found in ' + SHELL)

out = shell.replace('/*__LABREF_DATA__*/', data)
io.open(OUT, 'w', encoding='utf-8').write(out)
print("built", OUT, " bytes:", len(out.encode('utf-8')))
print("cite tags remaining:", out.count('<cite'))
