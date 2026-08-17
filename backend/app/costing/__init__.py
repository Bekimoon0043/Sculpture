"""Costing layer — a BOM whose every line traces to a rate and a formula.

Four operator rules govern this package, and each is enforced in code rather
than by convention:

  1. Costs derive ONLY from validation numbers the platform already computed
     (drivers.py reads a ValidationReport; it never measures geometry).
  2. Multi-currency with dated FX (rates.py; every converted line carries the
     rate and its as_of date).
  3. Every line shows its formula and its source rate path — "a number I
     cannot trace is a number I cannot defend to a client".
  4. A rate is NEVER invented. A missing rate produces an explicit
     missing_rate line naming the config path, and no total at all.
"""
