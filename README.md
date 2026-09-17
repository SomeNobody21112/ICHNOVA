# SIH26147 — Blind Signal Analysis & Decoding

Takes a raw IQ capture and, without being told any signal parameters, searches carrier offset, symbol rate, modulation (BPSK/QPSK) and phase. It then tests every convolutional code (K=7/5/3, rate ½) × block-interleaver hypothesis with a dual-code syndrome test. A payload is returned only when the best hypothesis is statistically significant after accounting for how many hypotheses were tried; otherwise the receiver says so.

Outcomes: **DECODED** (code accepted, Viterbi payload) · **SIGNAL_NO_CODE** (PSK signal detected, no code accepted) · **UNKNOWN** (no evidence).

**Real transmissions.** The same evidence-first rules run on real, over-the-air government signals received through public KiwiSDR receivers: NIST WWV/WWVB, PTB DCF77, NPL MSF and NICT JJY time codes (decoded blind; decoded minute matches each receiver's GPS clock to within 2–23 ms), the German Weather Service's DDH47 teleprinter (blind 50 Bd / 85 Hz ITA2 decode of its own callsign and frequency) and All India Radio medium-wave carriers matched to Prasar Bharati's official transmitter list. A weak WWVB capture is detected but its time refused. See `reports/REAL_SIGNAL_VALIDATION.md`.

## Quick start

```bash
pip install -r requirements.txt pytest
python src/generate.py sealed        # bench-v1 sealed: 30 files -> data/sealed (seed0=99000)
python src/generate.py train         # bench-v1 train: 100 files -> data/train (seed0=1000)

python -m pytest -q tests                # 30 tests: engine + real-signal receivers (recordings/real)
python sealed_test.py                    # 30/30, 0 false accepts, ~1.5 s
python sealed_test.py data/train 100     # 63/100, 0 false accepts, ~4.5 s
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

Latest results and limitations: `reports/BASELINE_HARDENING_REPORT.md`, `reports/STRUCTURAL_ACCEPTANCE_REPORT.md`, `reports/PERFORMANCE_REPORT.md` (3–4× faster, decision-identical on 1,480 files).

## Real signals

```bash
python server/kiwi.py --freq-khz 40 --seconds 185 --near 37.37,140.85 --out jjy.npz   # capture from the nearest public receiver
python server/make_recording.py jjy.npz --id my-jjy --station JJY --out-rate 1500      # -> recordings/real/my-jjy.wav + .json
python -m pytest -q tests/test_realsig.py                                             # decodes the committed recordings
python server/export_live_replays.py                                                  # replay timelines for the Live Monitor
```

`recordings/real/` holds IQ `.wav` recordings of WWV, WWVB, DCF77, MSF, JJY, DDH47 and All India Radio with GPS start times; any of them can be uploaded in the console's Analysis page. With the server running, the Live Monitor receives these stations live. Method, results and limitations: `reports/REAL_SIGNAL_VALIDATION.md`; related products and literature: `reports/RESEARCH_LANDSCAPE.md`.

## Operator console

```bash
cd frontend && npm install && npm run build && cd ..
python server/app.py      # http://127.0.0.1:8765
```

Upload an .IQ/.wav capture (a benchmark capture, or a real government recording) and follow the evidence chain from raw IQ to decision; open the Live Monitor to receive WWV, DCF77, MSF, JJY, DDH47 or All India Radio live (or replay recorded sessions offline); browse the Experiment Lab for the measured numbers. Monitoring-network views use clearly labelled simulated data. Details, including Google sign-in setup: `frontend/README.md`.

## Stack & documentation

| Layer | What it is |
|---|---|
| Engine (`src/`) | Python 3.11 with NumPy + SciPy only — hand-derived estimation theory (Viterbi, cumulants, CFO), no ML framework, no GNU Radio |
| Web tier (`server/`) | Python stdlib end to end: `http.server` + hand-rolled SSE for live updates, stdlib websocket client for public KiwiSDR receivers |
| Console (`frontend/`) | **ICHNOVA** operator console: React 19 + TypeScript + Vite 8, d3-geo spectrum maps, framer-motion, IBM Plex |

The complete compiled brief — tech stack, user flows, workflows (data export, field capture, CI) and assessment — is in [`reports/TECH_STACK.md`](reports/TECH_STACK.md).

## Layout

| Path | Purpose |
|---|---|
| `src/pipeline.py` | `analyze_file()` / `analyze_iq()`: blind receiver, search domain constants, accept/reject |
| `src/blind_id.py` | Code catalogue, interleaver domain, syndrome sign test, Viterbi hypothesis decode |
| `src/analyze.py` | Symbol-rate spectrum, matched filter, M-power phase, symbol M2M4, PSK LLRs |
| `src/fec.py` | Conv encoder, vectorized soft Viterbi, block interleaver |
| `src/modem.py` | Modulation, RRC, channel model, IQ/WAV I/O |
| `src/generate.py` | Deterministic bench-v1 generator |
| `src/timecodes.py` | Blind time-code receiver: WWV, WWVB, DCF77, MSF, JJY (epoch, symbols, ML frame decode, digit reliability) |
| `src/fsk.py` | Blind FSK: tone pair, shift, baud, framing, ITA2/ASCII; CHU packets |
| `src/broadcast.py`, `src/realsig.py` | AM characterisation; one entry point running every real-signal receiver |
| `server/kiwi.py`, `server/live.py`, `server/stations.py` | Public-receiver IQ/waterfall clients, live sessions (SSE), station catalogue with official references |
| `recordings/` | Real-signal recordings (IQ .wav + GPS sidecar) and official reference data (AIR transmitter list) |
| `server/` | Local analysis API (`app.py`), evidence packs, frontend data export |
| `frontend/` | Operator console (React + Vite) |
| `eval/` | SNR utility, oracle ladder, null set / calibration / scoring comparison |
| `reports/` | Measured reports and their raw evidence |
| `PROGRESS.md` | Session-by-session engineering log |
| `sih26147-constitution/` | Project constitution, roadmap, research docs (`SIH26147_CURRENT_STATE.md` is the live status) |
