# ICHNOVA — Blind Signal Analysis & Decoding (SIH26147)

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

Upload an .IQ/.wav capture (a benchmark capture, or a real government recording) and follow the evidence chain from raw IQ to decision; open the Live Monitor to receive WWV, DCF77, MSF, JJY, DDH47 or All India Radio live (or replay recorded sessions offline); browse the Experiment Lab for the measured numbers. Monitoring-network views use clearly labelled simulated data. The console has light, dark and system themes, a text-size control and a skip-to-content link, with a layout modelled on DoT spectrum portals (Tarang Sanchar, Saral Sanchar). It is an independent prototype, not an official Government of India system. Details, including Google sign-in setup: `frontend/README.md`.

## Running it as a service (container)

The same process serves the console and runs the engine, so a deployed instance analyses uploads
for real; it is not a playback of stored packs.

```bash
docker build -t ichnova .
docker run --rm -p 7860:7860 ichnova        # http://127.0.0.1:7860
```

`HOST` and `PORT` are read from the environment (defaults stay `127.0.0.1:8765` when run directly with
`python server/app.py`). The image contains the engine, the server, the reference constants, the
committed real recordings and the built console; benchmark data and evaluation scripts stay out.

Before putting an instance on a public URL, note the limitations (Constitution §9.2, §25.8):

- the API is **authenticated** — scrypt passwords, signed session tokens with an expiry, per-endpoint
  role permissions and rate limiting — but it terminates **no TLS**, so put it behind a proxy or a
  platform that does. Set `ICHNOVA_SECRET_KEY` so sessions survive a restart; without it a random key
  is generated at start-up. `ICHNOVA_OPEN_API=1` restores the old open behaviour for a single-user
  offline workstation;
- the engine is **air-gap capable by design**. A hosted instance is a convenience for reviewers, not
  the deployment model, and the page keeps the "independent SIH prototype, not an official Government
  of India system" disclaimer.

Live reception from public KiwiSDR receivers needs outbound WebSocket access; hosts that restrict
outbound traffic will still run uploads, replays and the benchmark evidence.

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
| `src/quality.py` | Capture gate: GOOD / DEGRADED / FAILED on clipping, DC, dropouts, I/Q balance — reported beside the verdict, never part of it |
| `src/sufficiency.py` | What would settle a refusal, in parity checks derived from the test that refused it |
| `src/receipt.py`, `server/verify_receipt.py` | SHA-256 receipt chain over decisions, and a CLI to verify a ledger independently |
| `server/auth.py` | scrypt passwords, signed session tokens, role permissions, rate limiting |
| `server/sources.py` | Signal sources with provenance, licence, what they feed (ENGINE / REFERENCE ONLY / METADATA ONLY) and measured health |
| `server/crm.py` | Salesforce case hand-off through a local outbox: idempotent, retrying, and never reports a sync that did not happen |
| `server/kiwi.py`, `server/live.py`, `server/stations.py` | Public-receiver IQ/waterfall clients, live sessions (SSE), station catalogue with official references |
| `recordings/` | Real-signal recordings (IQ .wav + GPS sidecar) and official reference data (AIR transmitter list) |
| `server/` | Local analysis API (`app.py`), evidence packs, frontend data export |
| `frontend/` | Operator console (React + Vite) |
| `eval/` | SNR utility, oracle ladder, null set / calibration / scoring comparison |
| `reports/` | Measured reports and their raw evidence |
| `PROGRESS.md` | Session-by-session engineering log |
| `sih26147-constitution/` | **Project constitution — the single source of truth** (`SIH26147_PROJECT_CONSTITUTION.md`), changelog, current-state snapshot, historical plans |
