# SIH26147 — Blind Signal Analysis & Decoding

Takes a raw IQ capture and, without being told any signal parameters, searches carrier offset, symbol rate, modulation (BPSK/QPSK) and phase. It then tests every convolutional code (K=7/5/3, rate ½) × block-interleaver hypothesis with a dual-code syndrome test. A payload is returned only when the best hypothesis is statistically significant after accounting for how many hypotheses were tried; otherwise the receiver says so.

Outcomes: **DECODED** (code accepted, Viterbi payload) · **SIGNAL_NO_CODE** (PSK signal detected, no code accepted) · **UNKNOWN** (no evidence).

## Quick start

```bash
pip install -r requirements.txt pytest
python src/generate.py sealed        # bench-v1 sealed: 30 files -> data/sealed (seed0=99000)
python src/generate.py train         # bench-v1 train: 100 files -> data/train (seed0=1000)

python -m pytest -q tests/test_core.py   # 9 tests
python sealed_test.py                    # 30/30, 0 false accepts, ~20 s
python sealed_test.py data/train 100     # 63/100, 0 false accepts, ~40 s
```

A file passes if the status is DECODED and payload BER < 0.01 (tolerant of bit complements). DECODED with BER ≥ 0.01 is counted as a false accept. Results go to `results/<dataset>_results.json`, with full per-file diagnostics in `results/<dataset>_diagnostics.jsonl`.

**bench-v1 is a regression tripwire, not a performance claim:** the sealed set was inspected during development, each file transmits only 30–60 of its 400 payload bits, and the "SNR" label is per-sample (sealed "2 dB" ≈ 10 dB Es/N0; see `eval/snr.py`).

## Evaluation

```bash
python eval/snr.py                                     # Es/N0 / Eb/N0 definitions vs measurement
python eval/ladder.py data/sealed 30 data/train 100    # oracle ladder: which estimate each failure needs
python eval/nullset.py generate && python eval/nullset.py run && python eval/nullset.py report
python eval/nullset.py compare                         # scoring-method comparison
```

Latest results and limitations: `reports/BASELINE_HARDENING_REPORT.md`.

## Operator console

```bash
cd frontend && npm install && npm run build && cd ..
python server/app.py      # http://127.0.0.1:8765
```

Upload an .IQ/.wav capture (or pick a benchmark capture) and follow the evidence chain from raw IQ to decision; browse the Experiment Lab for the measured numbers. Monitoring-network views use clearly labelled simulated data. Details, including Google sign-in setup: `frontend/README.md`.

## Layout

| Path | Purpose |
|---|---|
| `src/pipeline.py` | `analyze_file()` / `analyze_iq()`: blind receiver, search domain constants, accept/reject |
| `src/blind_id.py` | Code catalogue, interleaver domain, syndrome sign test, Viterbi hypothesis decode |
| `src/analyze.py` | Symbol-rate spectrum, matched filter, M-power phase, symbol M2M4, PSK LLRs |
| `src/fec.py` | Conv encoder, vectorized soft Viterbi, block interleaver |
| `src/modem.py` | Modulation, RRC, channel model, IQ/WAV I/O |
| `src/generate.py` | Deterministic bench-v1 generator |
| `server/` | Local analysis API (`app.py`), evidence packs, frontend data export |
| `frontend/` | Operator console (React + Vite) |
| `eval/` | SNR utility, oracle ladder, null set / calibration / scoring comparison |
| `reports/` | Measured reports and their raw evidence |
| `PROGRESS.md` | Session-by-session engineering log |
| `sih26147-constitution/` | Project constitution, roadmap, research docs (`SIH26147_CURRENT_STATE.md` is the live status) |
