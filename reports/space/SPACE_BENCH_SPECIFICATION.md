# SPACE_BENCH_SPECIFICATION
**ICHNOVA · SIH26147 — SPACE-BENCH: a new sealed benchmark for spacecraft-to-ground channel conditions**
**Status: SPECIFICATION, PRE-REGISTERED BEFORE ANY EVALUATION (2026-09-25). No vectors generated, no code written.**

---

## 1. Independence from bench-v2 (non-negotiable)

- bench-v2 (430 sealed files, 9/9 criteria, pre-registered) is **untouched**: same directory, same seeds, same criteria file, same one-run discipline.
- SPACE-BENCH is a **separate generator module, separate data directory, separate criteria file, separate sealed run** — modelled on the existing bench-v2 discipline (eval/bench2.py, bench2_criteria.json, bench2_gen.py — FACT).
- The sealing protocol is identical in spirit: criteria frozen and committed **before** the sealed evaluation; one logged run; results published whatever they are; failures documented, never tuned away (Constitution §18 discipline — FACT).

## 2. Generator basis

SPACE-BENCH reuses the *validated channel machinery* in `eval/bench2_gen.py` — FACT: channels `awgn`, `phase_noise` (Wiener), `cfo_drift` (linear), `rician` (block flat fading), `amplitude` (slow variation), `timing` (fractional delay). The one genuinely new impairment class is a **Doppler trajectory generator** (non-linear, pass-shaped frequency profile) — DESIGN PROPOSAL, with its own unit tests before any benchmark use. All payloads/framing come from the existing catalogue generators (RS, conv, concatenated, TC-LDPC, ASMs, randomizers).

## 3. Families

Each family defines: **ground truth, hidden parameters, impairments, expected system outcome, acceptance criterion, failure condition.** Common rules: hidden parameters are drawn in `hidden.json` (not shipped with results); expected outcomes use the three-outcome model; a *false decode* (DECODED on structure that is not the ground truth, or wrong payload) is always a failure condition regardless of family.

### FAMILY A — clean telemetry
- Ground truth: catalogue-coded CCSDS-shaped TM stream (ASM + coded frames + randomizer), known payload.
- Hidden: code, interleaver, sps, β, randomizer seed.
- Impairments: AWGN only, Es/N0 ≥ 9 dB.
- Expected: DECODED with payload verified.
- Accept: ≥ 90% full decodes, 0 wrong payloads.
- Fail: any wrong payload; refusal rate > 10%.

### FAMILY B — low-SNR telemetry
- Ground truth: same as A.
- Impairments: AWGN, Es/N0 swept **below the sealed coded-family floor** (4–6 dB).
- Expected: honest transition to SIGNAL_NO_CODE/UNKNOWN; **no false decodes**.
- Accept: 0 false decodes across the sweep; refusals carry sufficiency reasons (ACHIEVABLE or IMPOSSIBLE_IN_DOMAIN — FACT from sufficiency.py).
- Fail: any DECODED with wrong payload; refusal without a measured reason.

### FAMILY C — static carrier frequency offset
- Ground truth: A's signal; hidden static CFO within the existing ±1.25% fs bound.
- Impairments: C + AWGN at moderate SNR.
- Expected: DECODED (static CFO is a validated capability).
- Accept: ≥ 90% decodes, CFO estimates within tolerance vs hidden truth.
- Fail: wrong payload; systematic CFO bias unreported.

### FAMILY D — time-varying Doppler (the headline family)
- Ground truth: A's signal with a **pass-shaped frequency trajectory** (S-curve, |df/dt| ≤ 32 Hz/s equivalent scaled to fs — FACT-sourced magnitude from research).
- Impairments: trajectory + AWGN.
- Expected: DECODED on captures where the existing tracked front end suffices; honest refusal where it does not — **both outcomes acceptable, only lying is not**.
- Accept: 0 wrong payloads; every non-decode carries a measured drift-related refusal reason; **the receipt preserves the measured trajectory**.
- Fail: any false DECODED; refusal whose stated reason contradicts the injected trajectory.

### FAMILY E — Doppler + noise
- Ground truth: D's trajectory at lower SNR.
- Expected: migration DECODED → refusal as conditions degrade (the verdict must *move*, not lie).
- Accept: monotonic refusal migration across the severity sweep; 0 false decodes.
- Fail: a DECODED at severity s+1 where s refused on the same capture class with a *structural* reason (indicates luck, not evidence).

### FAMILY F — fading
- Ground truth: A's signal through the existing `rician` block-flat-fading class (K-factor hidden).
- Expected: DECODED at high K; honest refusal at deep fades.
- Accept: 0 false decodes; fade-block metadata preserved in evidence.
- Fail: false decode during a fade block.

### FAMILY G — timing offset
- Ground truth: A's signal with fractional timing offset up to ±0.5 symbol (existing `timing` class).
- Expected: DECODED (timing class already exercised in bench-v2 calibration — FACT).
- Accept: ≥ 90% decodes.
- Fail: any wrong payload.

### FAMILY H — short observation window
- Ground truth: A's signal truncated to span < 2 frames (and < TRACK_MIN_SYMBOLS variants).
- Expected: **UNKNOWN or SIGNAL_NO_CODE** — the structural minimum is not met; sufficiency must say IMPOSSIBLE_IN_DOMAIN where no capture length could suffice (FACT: a 32-bit block yields ~10 checks, best p = 2⁻¹⁰ above the bar).
- Accept: ≥ 95% honest short-capture outcomes; 0 false decodes.
- Fail: any DECODED claiming structure it could not have verified.

### FAMILY I — misleading / adversarial hypotheses
- Ground truth: a capture engineered so a **plausible wrong hypothesis scores strongly** — the space-link analogue of the measured 8PSK structural alias (reports/HIGHER_MODULATION_EXPERIMENT.md — FACT): e.g. QPSK carrying a periodic payload that satisfies a wrong interleaver's parity checks, or K3 truth vs K5 hypothesis on a short window.
- Expected: **refusal** — the structural checks (modulation consistency, block length, soft-path floor, runner-up margin, F2 agreement floor) must catch it.
- Accept: 0 false decodes across the family; every escape is documented as a gate failure with a proposed corrective gate (a documented failure + gate is a *valid outcome of the benchmark*; a hidden failure is not).
- Fail: any silent false decode discovered post-run.

### FAMILY J — unsupported / insufficient evidence
- Ground truth: structurally valid signals **outside** the catalogue (unknown coding, unknown frame format, idle/periodic carriers).
- Expected: SIGNAL_NO_CODE (signal present, no catalogue structure earned) or UNKNOWN — exactly the null-set discipline that already achieved 0/900 (FACT).
- Accept: 0 false accepts.
- Fail: any DECODED.

## 4. Pre-registration and sealing protocol

1. This file (families, acceptance criteria, vector counts, severity sweeps) is committed **before** generator implementation begins.
2. The generator + criteria file are committed; a **calibration split** (explicitly excluded from judging) is used once to shake out generator bugs — any criterion change is dated and justified in the criteria file exactly as bench-v2's was (FACT: bench2_criteria.json records such a revision "Revised before SEALED existed").
3. The sealed split is generated with fresh seeds; the sealed run executes **once**, logged; results (whatever they are) are committed to `reports/space/SPACE_BENCH_RESULTS.md`.
4. Any failure triggers the Constitution rule: STOP → document → determine whether the failure reopens engineering. Thresholds are never moved to pass.

## 5. Scale (pre-registered)

~60 vectors/family × 10 families ≈ 600 files (vs bench-v2's 430), plus null/adversarial splits for I/J. Runtime budget: identical per-file analysis to bench-v2 (pipeline is CPU-only; 178-test suite unaffected).

**END OF SPACE-BENCH SPECIFICATION**
