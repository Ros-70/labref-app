import re, io, sys

DATA  = 'labref_data_v1.10.js'
SHELL = 'shell.html'
OUT   = 'LabRef_v1.10.html'

data = io.open(DATA, encoding='utf-8').read()
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
