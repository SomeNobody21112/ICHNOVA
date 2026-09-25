# SPACE_LINK_FAILURE_MODE_ANALYSIS
**ICHNOVA · SIH26147 — space-link failure modes and expected behaviour**
**Status: ANALYSIS (2026-09-25), grounded in measured engine behaviour.**
Each failure mode states: expected outcome (DECODED / SIGNAL_NO_CODE / UNKNOWN — *preferably refusal unless evidence earns the decode*), the **enforcing gate** that makes that outcome happen (all gates verified in code — FACT), and where relevant the measured evidence that the gate works.

---

## Failure-mode table

| # | Mode | Expected behaviour | Enforcing gate (FACT unless noted) | Measured anchor |
|---|---|---|---|---|
| 1 | Weak signal (low SNR) | Refusal with sufficiency (ACHIEVABLE n more seconds, or IMPOSSIBLE_IN_DOMAIN) | Bonferroni bar p·M ≤ α not met; `sufficiency.assess()` | bench-v2 honest refusals; 0/120 false accepts — FACT |
| 2 | High noise, structure survives, payload does not | SIGNAL_NO_CODE | F2 agreement floor 0.61 ("a bit stream too noisy for the payload to survive" — the constant's physical reading) | idle-carrier p = 10⁻¹¹ at 59% agreement correctly refused — FACT |
| 3 | Static CFO | DECODED with CFO estimate reported | CFO search bounded ±1.25% fs; x²/x⁴ line tests vs exact null | Sealed static-CFO families — FACT |
| 4 | Time-varying CFO (linear) | DECODED when tracked front end suffices; else refusal | `TRACK_MIN_SYMBOLS` 512 + coherence-adaptive block tracking; untracked fronts satisfy parity within segments but payloads complement across them — the tracked variant exists precisely for this | bench-v2 calibration: 13/15 wrong payloads were drift/phase-noise/amplitude → gate added — FACT |
| 5 | Doppler (pass-shaped trajectory) | **NOT ESTABLISHED** until DOPPLER experiment runs; expected: D-family behaviour per SPACE-BENCH | Tracking + family-D acceptance criteria (pre-registered) | Design-stage — honest label |
| 6 | Timing error (fractional) | DECODED (small offsets), refusal at extremes | Timing class in generator; front-end serial-dependence gate ≤ 0.60 kills repeated-symbol aliases (~75% agreement at 2× oversample) | Spec constant with physical basis — FACT |
| 7 | Modulation ambiguity (BPSK↔QPSK) | Wrong-modulation hypothesis structurally rejected | Modulation consistency check: y² data-free for BPSK / random for QPSK; two exact binomial tests per candidate | test_modulation_aliasing.py — FACT |
| 8 | Code ambiguity (K3 vs K5 vs K7, short window) | Wrong code fails block-length/soft-path checks or loses to corrected p-value | Structural checks: coverage within BL_DELTA_SYMBOLS 1.7, path metric ≥ PM_FLOOR 0.926; calibrated on null split, reported on held-out | wrong-structure 39/225 → 2/225, wrong-hypothesis 5 → 0 — FACT |
| 9 | Interleaver ambiguity | Wrong interleaver skips coded symbols → coverage shortfall → rejected | Same structural coverage rule across all four interleaver types | bench-v2 families — FACT |
| 10 | Short capture / incomplete frame | UNKNOWN or SIGNAL_NO_CODE; sufficiency states IMPOSSIBLE_IN_DOMAIN when no length could suffice | MIN_SYMBOLS 16 per sps candidate; MIN_FRAMES 2; best-attainable-p floor (32-bit block ⇒ ~10 checks ⇒ p ≥ 2⁻¹⁰ above bar) | sufficiency.py logic + tests — FACT |
| 11 | Partial frame (frames present, payload truncated) | Honest partial decode reported as partial (e.g. RS codewords 2/4, 12/16) — counted as not-full in criteria | Criteria count full vs not-wrong separately | CCSDS chain 10/12 with honest partials — FACT |
| 12 | Synchronization ambiguity (marker vs blind window) | Only the statistically significant, structurally consistent sync is accepted; ties → runner-up margin reported | Exact binomial over declared period domain; runner-up margin in diagnostics; FRAME_PRESENT ≥ 75% of frames | framing.py — FACT |
| 13 | Adversarial signal structure (plausible wrong hypothesis) | Refusal expected; any escape = documented gate failure + corrective gate (never hidden) | All structural checks + family-wise correction + F2 floor; adversarial family I measures residual risk | 8PSK alias experiment: enabling cost 5/30 sealed + 1/900 null + 1 wrong K5 → gate stayed OFF — FACT |
| 14 | Unsupported protocol (valid RF, unknown structure) | SIGNAL_NO_CODE | Catalogue-bounded search; null-set discipline | 0/900 false accepts on non-catalogue nulls; 0/450 wrong decodes on coded nulls — FACT |
| 15 | Out-of-domain signal (FSK, phase-mod carriers, GMSK, AM shapes) | SIGNAL_NO_CODE at most; typically UNKNOWN; FSK handled only by the *separate* real-signal receivers, not the blind PSK path | Blind path assumes constant-modulus PSK-shaped structure; everything else fails its tests | DDH47 FSK decoded by dedicated receiver (realsig path), not blind catalogue — FACT |
| 16 | Bad capture (clipping, DC, dropouts, I/Q imbalance) | Quality reported GOOD/FAIR/POOR **beside** the verdict; bad capture explains a refusal, never creates one | quality.py gate; explicit rule: "a bad capture explains a refusal, it does not create one" | Capture-gate UI + tests — FACT |

## Cross-cutting rules (restated because they are the product)

1. **No unjustified decode:** every accept carries p·M ≤ α with structural checks; the receipt records all of it.
2. **Refusals explain themselves:** the sufficiency module converts the failing statistic into what capture would settle it.
3. **A failure discovered in any space-family run is documentation, not tuning:** STOP → document → decide whether engineering reopens (Constitution rule).
4. **Quality and verdict are independent axes** — the space link's degradation shows up as evidence decay, with capture quality explaining *why*, not overriding *what*.

**END OF FAILURE-MODE ANALYSIS**
