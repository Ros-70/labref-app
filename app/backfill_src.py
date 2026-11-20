#!/usr/bin/env python3
"""Backfill src[] provenance onto the 34 original LabRef records.

Each entry names the authoritative source(s) the record's reference limits and
decision thresholds were taken from, so every reference value in the database
has a recorded origin for the handover.
"""
import re, sys

SRC = {
 "hb":        ["WHO haemoglobin thresholds for anaemia (2011, VMNIS)",
               "ICMR-NIN / NFHS anaemia cut-offs used in Indian practice"],
 "mcv":       ["Standard adult and paediatric MCV reference intervals (Dacie & Lewis Practical Haematology)",
               "Mentzer index for thalassaemia trait vs iron deficiency"],
 "tlc":       ["Standard adult and age-stratified WBC reference intervals (Dacie & Lewis)",
               "Severe neutropenia threshold per IDSA febrile neutropenia guidance"],
 "ptinr":     ["WHO/ISTH INR standardisation (ISI-calibrated PT)",
               "Standard therapeutic INR targets for warfarin by indication"],
 "aptt":      ["Standard aPTT reference interval (reagent-dependent; Dacie & Lewis)",
               "Unfractionated heparin aPTT ratio target 1.5–2.5x control"],
 "ddimer":    ["Age-adjusted D-dimer cut-off (age x 10 ng/mL FEU over 50 years) — ADJUST-PE study",
               "ISTH overt DIC scoring system"],
 "platelet":  ["Standard platelet reference interval (Dacie & Lewis)",
               "Prophylactic and procedural platelet transfusion thresholds (AABB)"],
 "sodium":    ["Standard serum sodium reference interval",
               "European and US hyponatraemia guidelines — severity bands and correction-rate limits"],
 "potassium": ["Standard serum potassium reference interval",
               "Critical-value limits per CAP/CLSI critical result practice"],
 "creatinine": ["CKD-EPI 2021 creatinine equation (race-free)",
               "KDIGO 2012 AKI creatinine criteria and CKD GFR categories"],
 "glucosef":  ["ADA Standards of Care diagnostic thresholds for diabetes and prediabetes",
               "WHO/IDF diagnostic criteria for diabetes mellitus"],
 "hba1c":     ["ADA diagnostic HbA1c thresholds (IFCC/NGSP aligned)",
               "IFCC mmol/mol to NGSP % conversion"],
 "calcium":   ["Standard total and ionised calcium reference intervals",
               "Albumin-corrected calcium formula; hypercalcaemia severity bands"],
 "lactate":   ["Sepsis-3 / Surviving Sepsis Campaign lactate threshold (>2 mmol/L; >4 mmol/L high risk)"],
 "abgpanel":  ["Standard arterial blood gas reference intervals",
               "Compensation formulae (Winter's formula and expected-compensation rules)"],
 "alt":       ["ACG clinical guideline on abnormal liver chemistries — true healthy upper limits",
               "Standard laboratory ALT reference intervals"],
 "alp":       ["Standard adult and age-stratified alkaline phosphatase reference intervals",
               "Isoenzyme interpretation with GGT (hepatic vs bony origin)"],
 "albumin":   ["Standard serum albumin reference interval (bromocresol green/purple)",
               "Child-Pugh and albumin-corrected calcium use"],
 "troponin":  ["Fourth Universal Definition of Myocardial Infarction — 99th percentile URL and rise/fall criteria",
               "ESC 0/1-hour high-sensitivity troponin rule-out and rule-in algorithm"],
 "ntprobnp":  ["ESC heart failure guideline NT-proBNP rule-out thresholds (acute and non-acute)",
               "Age-stratified NT-proBNP rule-in thresholds"],
 "pct":       ["Procalcitonin antibiotic stewardship thresholds (0.25 / 0.5 ng/mL) from the ProHOSP/PRORATA trial programme"],
 "crp":       ["Standard high-sensitivity and conventional CRP reference limits",
               "hs-CRP cardiovascular risk strata (<1, 1-3, >3 mg/L)"],
 "bloodculture": ["CLSI M47 blood culture collection standard — volume, sets and timing",
               "IDSA/ASM laboratory diagnosis of infectious diseases guidance"],
 "bilirubin": ["Standard total, direct and indirect bilirubin reference intervals",
               "AAP hyperbilirubinaemia phototherapy and exchange-transfusion thresholds (neonatal)"],
 "lipid":     ["ESC/EAS dyslipidaemia guideline risk-based LDL-C goals",
               "NCEP ATP III / ACC-AHA lipid reference categories; triglyceride pancreatitis threshold"],
 "tsh":       ["Standard adult TSH reference interval (assay-dependent)",
               "ATA 2017 guideline — trimester-specific TSH ranges in pregnancy"],
 "ft4":       ["Standard adult free T4 reference interval (assay- and platform-dependent)",
               "Trimester-specific free T4 interpretation per ATA 2017"],
 "vitd":      ["Endocrine Society 25-hydroxyvitamin D sufficiency, insufficiency and deficiency thresholds",
               "IOM/NAM dietary reference intake adequacy threshold"],
 "ferritin":  ["WHO serum ferritin thresholds for iron deficiency (2020), including the inflammation-adjusted cut-off",
               "KDIGO anaemia-of-CKD ferritin and transferrin saturation targets"],
 "b12":       ["Standard serum vitamin B12 reference interval with the indeterminate zone",
               "Use of methylmalonic acid and homocysteine for borderline results (BCSH cobalamin guidance)"],
 "ana":       ["ACR/EULAR 2019 SLE classification criteria — ANA entry criterion at 1:80 on HEp-2",
               "International Consensus on ANA Patterns (ICAP) nomenclature"],
 "phenytoin": ["Standard total and free phenytoin therapeutic ranges",
               "Sheiner-Tozer albumin correction equation"],
 "urineacr":  ["KDIGO 2012 albuminuria categories A1-A3 (ACR <3, 3-30, >30 mg/mmol)",
               "ADA Standards of Care albuminuria screening thresholds"],
 "saag":      ["Serum-ascites albumin gradient 1.1 g/dL threshold (Runyon; AASLD ascites guideline)",
               "AASLD spontaneous bacterial peritonitis neutrophil count threshold"],
}

def main(path):
    s = open(path, encoding="utf-8").read()
    patched, missed = 0, []
    for tid, srcs in SRC.items():
        i = s.find('id:"%s"' % tid)
        if i < 0:
            missed.append(tid); continue
        # find this record's final rel:[...] line (last one before the record closes)
        m = re.compile(r'\n(\s*)rel:\[[^\]]*\](,?)\n(\s*)\},').search(s, i)
        if not m:
            missed.append(tid); continue
        # guard: the match must belong to THIS record (no other id: in between)
        if 'id:"' in s[i+10:m.start()]:
            missed.append(tid); continue
        if m.group(2) == ",":
            missed.append(tid + " (already has a trailing field)"); continue
        indent = m.group(1)
        lines = ",\n%ssrc:[%s]" % (indent, ",".join('"%s"' % x for x in srcs))
        end = m.start() + 1 + len(m.group(1)) + len(m.group(0)) - len(m.group(0))
        # rebuild: insert src after the rel array
        rel_end = s.index("]", s.index("rel:[", m.start())) + 1
        s = s[:rel_end] + lines + s[rel_end:]
        patched += 1
    open(path, "w", encoding="utf-8").write(s)
    print("src[] added to %d record(s)" % patched)
    if missed:
        print("not patched:", ", ".join(missed))

if __name__ == "__main__":
    import glob as _glob
    _hits = sorted(_glob.glob("labref_data_v*.js"))
    assert len(_hits) == 1, "expected exactly one data module, found: %s" % _hits
    main(sys.argv[1] if len(sys.argv) > 1 else _hits[0])
