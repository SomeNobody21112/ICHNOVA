# SIH26147 — Blind Signal Analysis & Decoding

Recovers the payload bits from a raw IQ capture with no prior knowledge of the signal. The pipeline estimates the symbol rate, CFO, modulation (BPSK/QPSK), and pulse roll-off, then identifies the FEC (K=7 r1/2 convolutional) and block interleaver. Each hypothesis is decoded, and re-encode consistency picks the winner.

## Quick start

```bash
pip install numpy scipy
python src/generate.py sealed        # 30 files -> data/sealed (seed0=99000)
python src/generate.py train         # 100 files -> data/train (seed0=1000)

python tests/test_core.py            # 4/4
python sealed_test.py                # 30/30, ~2 min
python sealed_test.py data/train 100 # held-out check, ~10 min
```

Results are written to `results/<dataset>_results.json`. A file passes if BER < 0.01 (tolerant of bit complements) and consistency ≥ 0.98.

## Layout

| Path | Purpose |
|---|---|
| `src/pipeline.py` | `analyze_file()`: the end-to-end blind pipeline |
| `src/analyze.py` | Detection, SNR, symbol rate, modulation ID, matched filter |
| `src/decode_search.py` | Search over sps × β × phase rotation |
| `src/blind_id.py` | Code + interleaver catalogue search, re-encode consistency |
| `src/fec.py` | Conv encoder, vectorized soft Viterbi, block interleaver |
| `src/modem.py` | Modulation, RRC, channel model, IQ/WAV I/O |
| `src/generate.py` | Deterministic benchmark generator |
| `PROGRESS.md` | Session-by-session engineering log |
| `sih26147-constitution/` | Project constitution, roadmap, research docs (`SIH26147_CURRENT_STATE.md` is the live status) |
