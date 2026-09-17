# Autonomous execution — baseline (before any engineering change)

**Date:** 2026-09-17 · **Purpose:** freeze what the repository measurably does *before* the SIH-readiness work, so every later change can be compared with it.

## Repository

| Item | Value |
|---|---|
| Commit | `acf4201` (branch `baseline-hardening`, in sync with `origin/baseline-hardening`); work continues on branch `sih-readiness` created from it |
| Working tree | Clean at start (`git status -sb` showed no changes) |
| Governing document | `sih26147-constitution/SIH26147_PROJECT_CONSTITUTION.md` v2.4 |
| Python | 3.11.14 · numpy 2.4.2 · scipy 1.17.0 · pytest 9.1.0 |
| Node | v25.0.0 locally (CI uses Node 22) |
| OS | Windows 11 Pro 10.0.26200 |

## Tests

| Command | Result |
|---|---|
| `python -m pytest -q tests` | **30 passed** in 46.7 s (9 core + 21 real-signal) |
| `cd frontend && npm run build` | Type-check + build OK (JS bundle 739.8 kB, gzip 235.0 kB) |

## Benchmarks re-run today (not copied from documents)

| Command | Result |
|---|---|
| `python sealed_test.py data/sealed 30` | **30/30**, 0 false accepts, 2.3 s total |
| `python sealed_test.py data/train 100` | **63/100**, 0 false accepts; UNKNOWN 17, SIGNAL_NO_CODE 20; 7.5 s total |
| `python eval/nullset.py run && report` (1,350 files) | 0/900 false accepts (95% Wilson UB 0.43%); 0 wrong decodes on 450 coded files; correct K7/K5/K3 = 61/37/31 of 150; noise → SIGNAL_NO_CODE 21/500 (4.2%) |

Raw outputs: `results/baseline/nullset_report.md`, `results/baseline/nullset_rows_v24.jsonl` (the `results/` directory is git-ignored; the numbers above are the record).

**One discrepancy against Constitution v2.4 §19:** uncoded QPSK → UNKNOWN is **122/150** today, while §19 says 121/150 (SIGNAL_NO_CODE 28 today). Every other null-set figure matches exactly. The difference is one file and does not change any false-accept or decode count. It is recorded rather than explained away.

## Capabilities at baseline (Constitution v2.4 §24, confirmed by reading the code)

| Area | Status | Code |
|---|---|---|
| `.iq` float32 interleaved, `.wav` int16 stereo input | IMPLEMENTED | `src/modem.py::load_iq`, `load_wav` |
| Sampling frequency | **Not identified.** WAV header or operator value; `server/app.py` silently used **1 MHz** when `fs` was absent for `.iq` | `server/app.py:176`, `src/pipeline.py::analyze_file(fs=1e6)` |
| Modulation | BPSK, QPSK (blind) | `src/pipeline.py`, `src/analyze.py` |
| FEC identification + decode | Convolutional K7 (171,133), K5 (23,35), K3 (7,5), rate ½, zero-start soft Viterbi | `src/blind_id.py`, `src/fec.py` |
| Interleaver | Single block, rows 2–16 × cols 4–24 (≤ 384 bits) | `src/blind_id.py::interleaver_candidates` |
| Acceptance | Syndrome sign test, Bonferroni over M, structural checks MC/BL/PM | `src/pipeline.py` |
| Outcomes | DECODED / SIGNAL_NO_CODE / UNKNOWN | `src/pipeline.py` |
| Real-signal receivers | Time codes, start-stop FSK, AM, MW census | `src/timecodes.py`, `src/fsk.py`, `src/broadcast.py`, `server/live.py` |
| Not implemented | QAM, 8PSK, RS, concatenated, LDPC, convolutional/diagonal/pseudo-random interleavers, frame sync / bit-stream correlation, header/payload | — |

## Known failures and limitations at baseline

1. Signal-presence test is anti-conservative: noise → SIGNAL_NO_CODE 4.2% against a 1% design target.
2. Low-Es/N0 recall: K7 correct 3/34 at 3 dB Es/N0.
3. Blocks of ≤ 32 coded bits cannot reach α = 1%.
4. Structural constants (PM floor, BL Δ) calibrated on AWGN only.
5. No real over-the-air PSK/FEC signal has ever been analysed.
6. Silent 1 MHz sample-rate default for `.iq` uploads.
7. No genuinely sealed evaluation set (bench-v1 sealed is a development-contaminated tripwire).
