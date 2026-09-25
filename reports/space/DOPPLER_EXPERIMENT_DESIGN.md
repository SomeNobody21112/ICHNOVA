# DOPPLER_EXPERIMENT_DESIGN
**ICHNOVA · SIH26147 — the controlled Doppler engineering study (design only)**
**Status: EXPERIMENT DESIGN, pre-registered before execution (2026-09-25).**
Purpose: answer the eight questions below with measured numbers **before** any orbital-mechanics modelling is considered. If the experiment fails, the orbital pass model stays deferred — no exceptions.

---

## 1. Principle: controlled trajectory first, orbital mechanics later

The experiment uses a **synthetic link with known everything**: known signal, symbol rate, modulation, coding — the only variable is a **frequency-offset trajectory** plus controlled noise. Nothing data-aided; the system must notice the drift the way it notices everything else, from the samples.

**Trajectory generator (DESIGN PROPOSAL, new impairment class):**
- `static`: f(t) = Δf₀ — the existing CFO case (control group).
- `linear`: f(t) = Δf₀ + r·t — the existing `cfo_drift` channel class (FACT, bench2_gen.py) (control group 2).
- `pass`: f(t) = Δf_max · (2/π)·atan2-style S-curve parameterised by peak shift (scaled from the sourced LEO magnitudes: ±5 kHz at S-band equivalent, normalized to fs; peak rate ≤ 32 Hz/s equivalent) — the treatment group.
- Severity sweep: peak shift ∈ {0.25, 0.5, 1, 2} × the static search bound (±1.25% fs), rate ∈ {8, 16, 32} Hz/s-equivalent; Es/N0 ∈ {6, 9, 12} dB; ≥ 20 vectors per cell; same payload/hidden parameters across cells where possible so differences are attributable to the trajectory.

## 2. The eight pre-registered questions and how each is answered

**D1 — Can ICHNOVA detect the frequency drift?**
Measure: per-block phase estimates from the tracked front end (`_track_phase` already unwraps phase across coherence-sized blocks — FACT) vs injected f(t). Metric: trajectory RMSE in Hz-equivalent; detection = trajectory slope significantly ≠ 0. **Report even when the verdict is refusal** — detection is independent of decode.

**D2 — Can it distinguish static CFO from time-varying CFO?**
Measure: fit both models (constant, linear, S-curve) to the estimated trajectory; report which the data supports (ΔBIC or plain residual comparison — an engineering choice, declared here, not tuned later). Success = static classified static, pass classified time-varying, ≥ 90% of cells.

**D3 — Does Doppler degrade modulation inference?**
Measure: modulation-gate statistics (`diagnostics.modulation_gates` — FACT) and modulation consistency check across severity cells vs static control.

**D4 — Does Doppler degrade symbol-rate estimation?**
Measure: sps-candidate ranking (`sps_table`) stability vs static control; sps error rate per cell.

**D5 — Does Doppler degrade FEC identification?**
Measure: hypothesis rank of the true (code, interleaver); p-value of the true hypothesis vs severity; count of cells where the true hypothesis falls out of the significant set.

**D6 — Does Doppler increase false decodes?**
Measure: wrong-payload decodes per cell. **This is the family-D headline criterion**: any false decode is a failure condition (SPACE_BENCH_SPECIFICATION.md family D), triggering STOP-and-document, never tuning.

**D7 — Does the system migrate from DECODED to refusal as evidence degrades?**
Measure: verdict distribution across the severity sweep; expected migration DECODED → SIGNAL_NO_CODE/UNKNOWN with drift-referenced refusal reasons. A *non-monotonic* migration (decode at severity s+1 after refusal at s with structural reason) is reported as an anomaly.

**D8 — Can evidence receipts preserve the measured trajectory?**
Measure: whether the receipt/evidence pack carries the per-block trajectory (or its fitted parameters + residuals) so a third party can re-derive D1–D2. DESIGN PROPOSAL: trajectory enters the space-domain receipt fields (SPACE_EVIDENCE_RECEIPT_DESIGN.md). Nothing exists today — FACT — which is exactly why D8 is a deliverable and not an assumption.

## 3. What already exists vs what is new (honest tags)

| Component | Status |
|---|---|
| Static CFO search ±1.25% fs | EXISTING |
| Linear drift channel class + tracked front ends (coherence-adaptive block, ≥ 512 symbols) | EXISTING (bench-v2 calibration measured 13/15 wrong payloads on drift/phase-noise/amplitude classes — FACT — which is *why* tracking exists) |
| Pass-shaped (S-curve) trajectory generator | NEW (small, pure function + unit tests) |
| Trajectory extraction/reporting as evidence | NEW (read-out of existing internal state + packaging) |
| Static-vs-dynamic classification | NEW (declared fit comparison, above) |
| Orbital propagation (TLE, elevation, azimuth) | NOT ESTABLISHED — deliberately deferred until D1–D8 pass |

## 4. Decision rule after the experiment

- All eight answered cleanly → SPACE-BENCH families D/E proceed; orbital pass model (SATELLITE_PASS_REPLAY_DESIGN.md) may be designed as SIMULATED.
- D6 false decode or D7 non-monotonic → STOP, document in `reports/space/DOPPLER_EXPERIMENT_RESULTS.md`, treat as the discovery it is (it would mean the drift-tracking guarantees have a measurable boundary — worth knowing, honestly reported).
- D1/D2 weak → trajectory reporting becomes an explicit UNKNOWN contributor rather than a claimed capability.

**END OF DOPPLER EXPERIMENT DESIGN**
