#!/usr/bin/env bash
# LabRef full verification — six independent methods.
# Usage:  bash qa/run_all.sh        (run from the repo root, after build.py)
set -u
cd "$(dirname "$0")/.."
fail=0
hr(){ printf '\n\033[1m%s\033[0m\n' "── $* ─────────────────────────────────────────"; }

hr "METHOD 2 — data integrity (node, no browser)"
node qa/validate_data.js            || fail=1

# Row identity is checked before anything else looks at behaviour: if a rid has
# changed meaning, every saved My Lab value in that test is already suspect, and
# no amount of UI testing would reveal it.
hr "METHOD 5 — stable row identity (My Lab overrides depend on this)"
node qa/validate_rids.js            || fail=1

hr "METHOD 5b — self-test: the identity guard rejects what it claims to"
node qa/test_rid_guard.js           || fail=1

hr "METHOD 6 — row-selection tie-break guard (ref/method + ladder-fallback)"
node qa/validate_ties.js            || fail=1

hr "METHOD 3 — built-artifact structural audit (static analysis)"
node qa/audit_build.js              || fail=1

hr "METHOD 1 & 4 — behaviour in a real browser + full 180-test corpus sweep"
for t in test_v11_features test_all_tests test_panel test5 test3 test6 checkbc fstest test_themes; do
  printf '  %-20s ' "$t"
  if out=$(timeout 300 python3 -I "qa/$t.py" 2>&1); then
    if echo "$out" | grep -qiE "^FAIL|FAILURES|ERRORS: \[|Traceback"; then
      echo "FAIL"; echo "$out" | tail -20; fail=1
    else
      echo "pass"
    fi
  else
    echo "FAIL"; echo "$out" | tail -20; fail=1
  fi
done

hr "RESULT"
if [ "$fail" -eq 0 ]; then echo "All six methods passed."; else echo "FAILURES ABOVE"; fi
exit $fail
