# Changelog

## 1.0.0 — 2026-11-13

- Three fixture chains (fixtures/v1): `harbour-light` (PNG image, 5
  steps), `field-notes` (text, 4 steps), `disclosure-card` (text, 3
  steps) — 12 transformation steps, 60 assertion-status expectations.
- Hash-chained step records: every step records its asset hash, its
  payload hash, and the previous step's record hash.
- Reference checker (`python -m provenance_fixtures`): recomputes every
  hash from the files on disk, verifies the chain, and reports each
  assertion as verified / unknown / lost, compared against the expected
  status in the manifest.
- Deterministic generator (`tools/build_fixtures.py`): every fixture is
  rebuilt from recipes in code; regeneration is byte-identical and the
  test suite proves it.
- 23 tests, all passing (see README for the actual output).
