# ICHNOVA · SIH26147 — CURRENT STATE (snapshot)

**Date:** 2026-09-17 · **Constitution:** v2.4 · **Branch:** `baseline-hardening` (PR #2, CI green)

> Derived document. The authoritative component table, evidence and rules are in `SIH26147_PROJECT_CONSTITUTION.md` (§24 status, §18–§23 evidence). If this snapshot disagrees, the Constitution governs.

## Headline numbers

| Measure | Value | Constitution |
|---|---|---|
| bench-v1 sealed (regression tripwire, not held-out) | 30/30, 0 false accepts, ~1.5 s | §18 |
| bench-v1 train | 63/100, 0 false accepts, ~4.4 s | §18 |
| Null set, 900 non-catalogue files | 0 false accepts (95% upper bound 0.43%) | §19 |
| Null set, 450 coded files | 0 wrong decodes | §19 |
| Wrong-structure null (evaluation split of the null-set generator) | 2/225 = 0.9% | §19 |
| Real time codes decoded blind | JJY, DCF77, MSF, WWV; GPS agreement +1.9 to +23.4 ms; WWVB time refused | §22 |
| Real FSK text | DWD DDH47, 50 Bd / 85 Hz ITA2, p = 10^-241 | §22 |
| AIR medium wave | 5/5 carriers matched to Prasar Bharati's official list | §22 |
| Speed-up | 3.0–3.8×, 0 decision differences on 1,480 files | §23 |
| Tests | 30 (9 core + 21 real-signal), CI green | §32 |
| Console | ICHNOVA, 16 routes, light/dark themes, accessibility bar | §26–§29 |

## Critical path

```
bench-v2 (full payload, CRC, multi-block, fading) → detection calibration (4.2% → 1%)
→ Es/N0 waterfall → frame sync / CRC → only then Cyclic-CAF and SAGE-Lite
```

## Verification commands

```bash
# Data is not committed; regenerate deterministically from repo root:
python src/generate.py sealed        # data/sealed, seed0=99000
python src/generate.py train         # data/train,  seed0=1000

python -m pytest -q tests                # must be 30/30
python sealed_test.py                    # must be 30/30, 0 false accepts
python sealed_test.py data/train 100     # currently 63/100, 0 false accepts
```

**CURRENT STATE COMPLETE**
