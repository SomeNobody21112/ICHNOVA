# ICHNOVA · SIH26147 — CURRENT STATE (snapshot)

**Date:** 2026-09-20 · **Constitution:** v2.5.4 · **Branch:** `sih-readiness` (`origin/main` at the same commit)

> Derived document. The authoritative component table, evidence and rules are in
> `SIH26147_PROJECT_CONSTITUTION.md` (§24 status, §18–§23 evidence). If this snapshot disagrees, the
> Constitution governs. Figures here were measured on 2026-09-20 or read from a committed result file.

## Headline numbers

| Measure | Value | Constitution |
|---|---|---|
| **bench-v2 sealed** (430 files, criteria pre-registered, one logged run) | **9/9 criteria pass**; 0/120 false accepts on non-catalogue signals; 3/310 wrong structure or payload = 0.97% | §18.1 |
| bench-v1 sealed (regression tripwire, not held-out) | 30/30, 0 false accepts | §18 |
| bench-v1 train | 63/100, 0 false accepts | §18 |
| Null set, 900 non-catalogue files | 0 false accepts (95% upper bound 0.43%) | §19 |
| Null set, 450 coded files | 0 wrong decodes | §19 |
| CCSDS concatenated chain (sealed) | 10/12 decoded to the RS payload at Es/N0 ≥ 9 dB | §18.1 |
| CCSDS TC LDPC CLTU (sealed) | 8/8 at Es/N0 ≥ 6 dB | §18.1 |
| Continuous K7 stream (sealed) | 16/16 at Es/N0 ≥ 6 dB | §18.1 |
| Real time codes decoded blind | JJY, DCF77, MSF, WWV; GPS agreement +1.9 to +23.4 ms; WWVB time refused | §22 |
| Real FSK text | DWD DDH47, 50 Bd / 85 Hz ITA2, p = 10^-241 | §22 |
| AIR medium wave | 5/5 carriers matched to Prasar Bharati's official list | §22 |
| Live capture through the full chain (2026-09-20) | 720 kHz, 144,384 samples @ 11,998.881 Hz, GPS-timed → quality GOOD → carrier 61.3 dB above noise → **SIGNAL_NO_CODE** → receipt verified. Station identity **NOT ESTABLISHED** (nearest receiver 2,135 km) | §22 |
| 8PSK / 16-QAM | **EXPERIMENTAL, off by default.** Enabling it: 0/100 8PSK captures decoded, search ×21.8, one BPSK capture decoded 40% wrong through a structural alias | §24 row 34 |
| Tests | **178**, all passing (re-measured 2026-09-24) | §32 |
| Dependency CVEs | Python 0, Node 0. Container base images **NOT ESTABLISHED** | §25.8 |
| Console | ICHNOVA, light/dark themes, accessibility bar; 120 pages measured across 4 viewports × 2 themes | §26–§29 |

## Platform state

| Area | Status |
|---|---|
| API authentication, RBAC, rate limiting | **VALIDATED** — scrypt, signed expiring tokens, per-endpoint roles; 0 of 2,709 forged signatures accepted |
| Evidence receipts | **VALIDATED** — SHA-256 chain; CLI and browser verifiers both driven against a real tamper |
| One writer per results directory | **ENFORCED** (§9.12) — a second process refuses to start; proven with two interpreters |
| Source freshness | **ENFORCED** (§9.13) — reachable ≠ fresh; STALE is reported honestly |
| TLS reverse proxy | **CONFIGURED**, never exercised, not live — no Docker daemon, no native nginx |
| Salesforce hand-off | **IMPLEMENTED**, never connected to a real org |
| Field deployment | **NOT ESTABLISHED** |
| External penetration test | **NOT ESTABLISHED** — the only adversarial testing is our own |

## Critical path

```
detection calibration (4.2% → 1%) → Es/N0 waterfall
→ modulation classifier that picks the constellation BEFORE the code search
   (the only route to taking 8PSK/16-QAM out of EXPERIMENTAL)
→ only then Cyclic-CAF and SAGE-Lite
```

## Verification commands

```bash
# Data is not committed; regenerate deterministically from repo root:
python src/generate.py sealed        # data/sealed, seed0=99000
python src/generate.py train         # data/train,  seed0=1000

python -m pytest -q tests                 # must be 178 passed
python sealed_test.py                     # must be 30/30, 0 false accepts
python sealed_test.py data/train 100      # currently 63/100, 0 false accepts

python server/verify_receipt.py --ledger frontend/public/evidence/ledger.jsonl   # exit 0
python server/sources.py                  # measured source health, honest freshness
```

**CURRENT STATE COMPLETE**
