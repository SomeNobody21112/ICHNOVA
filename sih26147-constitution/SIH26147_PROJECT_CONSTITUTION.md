# ICHNOVA · SIH26147 — PROJECT CONSTITUTION

**Problem statement:** SIH26147 (Smart India Hackathon 2026; sponsor listed in the problem statement: NTRO)
**Product:** ICHNOVA — *From noise to harmony* (blind signal analysis engine + operator console)
**Document:** Master Project Constitution — **the single source of truth**
**Version:** 2.5.4 (deployment invariants: one writer per results directory §9.12, reachable-is-not-fresh §9.13; TLS reverse proxy CONFIGURED but never exercised; in-memory rate limiting and revocation recorded as a limitation) · **Date:** 2026-09-20
**Verified against:** branch `sih-readiness`. v2.5 text verified against `acf4201`; the v2.5.1 status rows are measured on the engine as committed, with the default path unchanged (0 decision differences on 1,350 null-set files, sealed 30/30, train 63/100). Evidence per phase in `reports/SIH_READINESS_EXECUTION.md`
**Supersedes:** v2.0 (research-verified, 2026-09-16), v2.1–v2.4, and every earlier plan document where they disagree (§3)

> **v2.5 in one paragraph.** The engineering audit (2026-09-17) found that most explicit SIH26147 capabilities were missing: QAM, RS, concatenated coding, LDPC, three interleaver types, bit-stream correlation, sample-rate provenance. v2.5 re-prioritises the roadmap to close them (§35). It **pre-registers**, before any code or measurement, the finite catalogue to be searched (§12.1), the weighted multiple-testing families that keep the file-level false-accept bound at α = 0.01 (§13.1), the bench-v2 sealed-split policy (§18.1) and sample-rate provenance (§10). New capabilities enter §24 as **LOCKED**. They move up only with committed evidence.

---

# PART A — IDENTITY AND GOVERNANCE

## 1. Project Identity

| Item | Value |
|---|---|
| Name | **ICHNOVA** (all capitals in the wordmark; "Ichnova" acceptable in running text). **Never "THADAM"** — rejected by the team. Name and taglines live in `frontend/src/brand.ts` |
| Tagline / motto | "From noise to harmony" · "Hidden signals, brighter tomorrows" |
| Concept strip | Noise → Discovery → Harmony |
| What it is | An evidence-first blind signal-analysis engine for raw IQ captures, plus an operator console that shows the evidence behind every decision |
| What it is not | Not an official Government of India system. Not affiliated with DoT, WPC, NTRO, Prasar Bharati or any operator whose transmissions it analyses. An independent SIH prototype |
| Repository | `github.com/SomeNobody21112/SIH26147` |
| Question the product answers | Not "what does the AI think this signal is?" but **"what evidence supports this signal interpretation?"** |

## 2. Constitutional Purpose and Authority

This document defines, in one place: what the project solves, how the engine works, what has been measured, what is partial, what is refused, what the product looks like, how work is validated, what may be claimed, and what comes next.

1. **No implementation, benchmark, presentation, pitch, README or UI copy may contradict this Constitution** without first amending it (§46).
2. When this document and another file disagree, **this document governs** until the other is corrected — except that reproducible measurement always beats prose: if a command in §34 produces a different number, the number wins and this document must be amended.
3. Only implementation plus reproducible evidence can promote a capability through the status system (§7).
4. The project prioritises **measurable capability over feature count, marketing language or complexity.**

## 3. Document Map

| Document | Role | Status |
|---|---|---|
| **`sih26147-constitution/SIH26147_PROJECT_CONSTITUTION.md`** | Everything: identity, rules, architecture, evidence, product, roadmap, claims | **GOVERNING** |
| `sih26147-constitution/SIH26147_CURRENT_STATE.md` | Dated snapshot of headline numbers and verification commands; derived from §24 | Derived |
| `sih26147-constitution/SIH26147_CONSTITUTION_CHANGELOG.md` | What changed between versions and why | Governing for history |
| `reports/BASELINE_HARDENING_REPORT.md` | Leakage removal, null set, scoring comparison, oracle ladder | Evidence |
| `reports/STRUCTURAL_ACCEPTANCE_REPORT.md` | Wrong-structure null, adopted acceptance rule | Evidence |
| `reports/REAL_SIGNAL_VALIDATION.md` | Government transmissions received blind | Evidence |
| `reports/PERFORMANCE_REPORT.md` | Vectorised search, decision identity | Evidence |
| `reports/RESEARCH_LANDSCAPE.md` | Products and literature with sources | Evidence |
| `reports/TECH_STACK.md` | Stack, user flows, workflows | Reference |
| `reports/data/` | Raw evidence (JSON, ladders, null-set tables) | Evidence |
| `reports/AUTONOMOUS_EXECUTION_BASELINE.md` | Re-measured baseline before the v2.5 work | Evidence |
| `reports/SIH_READINESS_EXECUTION.md` | v2.5 execution log: what was built, measured, failed, deferred | Evidence (updated per phase) |
| `references/` | Transcribed normative constants (QPP table, CCSDS vectors) with their source documents | Reference data |
| `PROGRESS.md` | Session-by-session engineering log | History |
| `SIH26147_EXECUTION_ROADMAP.md`, `SIH26147_2DB_QPSK_RESCUE_EXPERIMENT.md` | v2.0 plan built on the 28/30 baseline and consistency acceptance | **HISTORICAL** — premise changed (§35) |
| `SIH26147_NOVELTY_AUDIT.md`, `SIH26147_RESEARCH_FRONTIER.md` | v2.0 literature audit and research directions | Reference; claims constrained by §37, priorities by §35 |
| `README.md`, `frontend/README.md` | How to run | Must agree with §33–§34 |

---

## 4. Mission

Recover communication structure from degraded, non-cooperative signal observations when transmission parameters are unknown: modulation, symbol rate, carrier offset, timing, forward error correction, interleaving, framing and payload — and **refuse, with a number attached, when the evidence does not support an answer.**

Long-term research objective (unchanged from v2.0, now gated, §36): a cross-layer receiver in which decoding evidence refines the upstream estimates responsible for failure ("decoding as a sensor").

## 5. Core Thesis

### 5.1 Evidence first (operative thesis since v2.2)

Every accepted interpretation must be backed by a statistical test whose error rate under the null is **known**, corrected for the number of hypotheses searched, and checked against structural alternatives. An answer without such evidence is reported as `SIGNAL_NO_CODE` or `UNKNOWN`, never guessed.

### 5.2 Decoding as a sensor (research direction)

```
Conventional:  Signal → Parameter estimation → Demodulation → FEC decode → Output
Research goal: Signal → Initial inference → Demodulation → Soft information → Decode
               → Consistency / residual evidence → Parameter refinement → Demodulate and decode again
```

"Decoding as a Sensor" was not found in IEEE Xplore, Google Scholar, arXiv or CrossRef (search 2026-09-16). Its mechanism has established analogues in **code-aided / turbo synchronisation** (§36.2). The feedback loop (SAGE-Lite) is **BLOCKED**, not abandoned (§36.3).

## 6. Project Principles

1. **Evidence before claims.** A capability is PROVEN only by project measurement — not by literature, mathematics, a prototype, or another product.
2. **Preserve the baseline.** Every change is compared with the current receiver; decision-changing changes need a report.
3. **Fix the measured bottleneck.** Priorities come from the oracle ladder and null sets (§21, §19), not intuition.
4. **Ambition with restraint.** New capability must show measurable benefit, feasibility, acceptable CPU cost, reproducibility and relevance.
5. **UNKNOWN is a valid result.** Refusal is a feature and is shown as one in the product.
6. **Absence of framework is evidence.** Two Python dependencies and no server framework keep every decision readable (§31).
7. **Real world over synthetic.** Where a real, lawfully receivable transmission can check a capability, it is preferred to more synthetic data.
8. **Calm product.** The console shows what an operator needs to act and folds away the rest (§29).

## 7. Evidence Classification

| Status | Meaning |
|---|---|
| **PROVEN** | Directly demonstrated by project experiments with committed artifacts |
| **PROVEN on real signal** | Demonstrated on a committed over-the-air recording with an independent check |
| **PARTIALLY PROVEN** | Demonstrated under some conditions; known to degrade or not fully validated |
| **FUNCTIONAL** | Works and is used, but its accuracy has not been measured |
| **IMPLEMENTED, UNTESTED** | Code exists; no test or measurement |
| **EXPERIMENTAL** | Shown in the product, explicitly not validated |
| **LOCKED** | Selected for implementation — does not mean proven |
| **BLOCKED** | Selected, but a named prerequisite is unmet |
| **FUTURE** | Relevant, intentionally deferred |
| **RETIRED** | Previously used; replaced by measured evidence, kept as a diagnostic |
| **SUPERSEDED** | Replaced by a different approach |
| **REJECTED** | Excluded on evidence or constraints |
| **UNKNOWN** | Insufficient evidence exists |

## 8. Claim Discipline

### 8.1 Four kinds of sentence, never interchangeable

- "The literature shows…" — established knowledge, cited.
- "Our hypothesis is…" — untested conjecture.
- "Our implementation does…" — what the code computes.
- "Our experiment measured…" — an artifact-backed number with its dataset named.

### 8.2 Provenance labels (mandatory in every document, slide and screen)

| Label | Meaning |
|---|---|
| **BENCHMARK** | Real engine output on synthetic benchmark captures |
| **LIVE** | Real engine output on a capture analysed now, or on a real over-the-air recording |
| **SIMULATED** | Generated data: monitoring network, stations, incidents, occupancy (`frontend/src/lib/sim.ts`) |
| **EXPERIMENTAL** | Implemented, not validated (e.g. genome similarity) |
| **NOT ESTABLISHED** | Not built or not validated (ML models, QAM, RS/LDPC, …) |

A figure without a label must not be shown. Simulated data must never be described as real, and benchmark data never as field data.

### 8.3 Dataset wording

- bench-v1 **sealed** is a **development-contaminated regression tripwire**, never "held-out" and never a performance claim.
- "SNR" in bench-v1 is **per-sample**; sealed "2 dB" ≈ 10 dB Es/N0 (`eval/snr.py`). Quote Es/N0 when discussing difficulty.
- Each bench-v1 file transmits only 30–60 of its 400 payload bits.

## 9. Non-Negotiable Constraints

| # | Constraint |
|---|---|
| 9.1 | **CPU only.** No GPU prerequisite. |
| 9.2 | **Air-gap compatible engine.** No cloud, API or network dependency for analysis. (Public-receiver live reception and Google sign-in are optional console features; the engine and offline replays work without them.) **v2.5:** any other cloud integration (e.g. a CRM) may only consume exported evidence one way, may never be required for an analysis, and needs its own amendment. **v2.5.3 approves exactly one: the Salesforce case hand-off (`server/crm.py`).** It satisfies the clause as written and stays bound by it: a case is written to a local append-only outbox and delivery is a separate explicit step, so no analysis waits on it or fails without it; the record carries only the decision, its statistics and the receipt hash, built from a fixed field list, and `assert_no_bulk_data` refuses any payload carrying IQ, payload bits, views, audio or oversized fields; credentials come from the environment only; and an item is marked SENT only on a Salesforce record id, so an unreachable or unconfigured CRM reports that it delivered nothing. No other cloud integration is approved. |
| 9.3 | **Reproducible.** Every experiment records data, code version, configuration, seed, estimates, metrics, runtime and failures. Datasets regenerate byte-identically from seed. |
| 9.4 | **Auditable.** Every decision carries its test statistic, threshold, hypothesis count and rejected alternatives. |
| 9.5 | **Do not modify `src/generate.py`.** |
| 9.6 | **Do not regenerate bench-v1 differently, tune on the sealed set, or game any benchmark.** |
| 9.7 | **Never fabricate or hand-type results.** Every number in the console comes from exported engine output (`server/export_frontend_data.py`) or is labelled SIMULATED. |
| 9.8 | **No dataset constants in inference** (sps lists, β lists, bonuses); guarded by `tests/test_core.py`. |
| 9.9 | **No claim of being an official government system**; no imitation of government branding, emblems or domains. |
| 9.10 | **Authorised use only** (§39). |
| 9.11 | **No feature-count competition.** One convincing capability beats many unproven ones. |
| 9.12 | **One writer per results directory** (v2.5.4). The receipt ledger and the CRM outbox are append-only files whose head is read before each append. Two processes sharing a results directory each append against the head they read, forking the evidence chain — the one thing a receipt exists to prevent. `server/store_lock.py` takes an exclusive OS lock on the directory at start-up and a second process refuses to start; `deploy/docker-compose.yml` pins `deploy.replicas: 1` with the reason. Horizontal scaling needs either a results directory per process or a different store, and is **NOT ESTABLISHED**. Two hosts against one shared network filesystem is unsafe and unaddressed. |
| 9.13 | **Reachable is not fresh** (v2.5.4). A source's health reports what this installation actually received, not merely whether the service answers. A reachable source with no recent data is STALE, never a green light. |

---

# PART B — THE ENGINE

## 10. Problem Scope and I/O

| Item | Specification |
|---|---|
| Input | `.iq` interleaved float32 I/Q; `.wav` int16 stereo I/Q (`src/modem.py::load_iq`, `load_wav`) |
| Told to the engine | Sample rate when known (and, for real signals, the tuned frequency). **v2.5:** every result records `fs_source` ∈ {`declared`, `wav_header`, `inferred`, `relative_only`, `unavailable`}. A missing sample rate must never silently become a default. Without one, the engine works in normalised units (samples per symbol, cycles per sample), reports "Absolute sample rate not established", and does not print absolute Hz values |
| Not told | Modulation, symbol rate, carrier offset, timing, roll-off, code, interleaver, framing, polarity, station, protocol |
| Output | `DECODED` · `SIGNAL_NO_CODE` · `UNKNOWN`, plus payload (when decoded) and a full evidence record |
| Families (PSK engine) | BPSK, QPSK; convolutional rate-½ K7 (171,133), K5, K3; single block interleaver; uncoded |
| Families (real-signal receivers) | Five time codes (WWV, WWVB, DCF77, MSF, JJY), start-stop FSK (ITA2/ASCII), CHU packets, AM, medium-wave carrier census |

## 11. Engine Architecture (as built)

```
Raw IQ
 ├─ Symbol-rate spectrum (|x|, |x|²) + lag-1 y⁴ quality over integer sps 2–20
 │    → sps candidates: best 3 by quality + integer divisors + raw spectral estimate
 ├─ Carrier: x² and x⁴ spectral lines with p-values, zero-padded, top candidates per order
 ├─ For each front end (sps × CFO × modulation BPSK/QPSK × rotation):
 │    RRC matched filter (β = 0.3, fixed delay) → M-power phase → symbol-domain M2M4 SNR
 │    → calibrated PSK LLRs → serial-independence check (reject dependent front ends)
 ├─ Vectorised syndrome scan over code × interleaver hypotheses (≈20,000 per capture)
 │    dual-code parity sign test, exact Binomial null
 ├─ Acceptance (§13): Bonferroni over all hypotheses, then structural checks MC, BL, PM
 ├─ Zero-start soft Viterbi on the accepted hypothesis; payload tie-break across
 │    equivalent front ends and both polarities
 └─ Decision + evidence record (§14)
```

Files: `src/pipeline.py` (orchestration, domain constants, acceptance), `src/blind_id.py` (catalogue, interleaver domain, `syndrome_scan`, `sign_test_log10p`, `decode_hypothesis`), `src/analyze.py` (spectra, matched filter, M-power, M2M4, LLRs), `src/fec.py` (encoder, vectorised soft Viterbi K7/K5/K3, block interleaver), `src/modem.py` (modulation, RRC, channel, I/O).

## 12. Declared Search Domain and Assumptions

Every assumption is **declared**, not hidden. Out-of-domain behaviour is untested unless stated.

| Assumption | Value | Status |
|---|---|---|
| Samples per symbol | Integer 2–20, ≥ 16 symbols | Declared receiver spec |
| Carrier offset | \|Δf\| ≤ 0.0125 cycles/sample | Declared; out-of-range untested |
| RRC roll-off at receiver | 0.3 (single value) | Declared; oracle shows 0 files waiting on β |
| Interleaver | Single block, rows 2–16, cols 4–24, ≤ 384 bits | Declared; repeated blocks unsupported |
| Encoder start state | Zero | Declared; real mid-stream captures need frame sync |
| Timing | Integer sps, fixed matched-filter delay | Declared; no fractional timing recovery |
| QPSK bit order | I then Q | Declared |
| Pulse | Root-raised cosine | Declared |
| Significance | α = 0.01 family-wise (Bonferroni) | Declared |

### 12.1 Catalogue v1 (LOCKED in v2.5; pre-registered before implementation)

The search is over a **finite, documented catalogue**, never over "all possible" structures. Items not listed are out of domain and are reported as such.

| Layer | Catalogue v1 | Source of definition |
|---|---|---|
| Modulation | BPSK, QPSK (always searched); **8PSK** (EXPERIMENTAL, off by default in the engine — §24 row 34), Gray-mapped (symbol k = e^{j2πk/8}, bits = k ⊕ (k≫1), MSB first), 8 rotation hypotheses, searched when the QPSK signature (y⁴ pair test) is *not* significant; **16-QAM**, square Gray-mapped (I from bits 0–1, Q from bits 2–3, per axis 00→+1, 01→+3, 10→−1, 11→−3, scaled 1/√10), 4 rotation hypotheses, searched when constant modulus is contradicted (inner-amplitude binomial test at α) | Project definition |
| Burst interleaver (joint with code, zero-start burst) | **Block** r×c (rows 2–16, cols 4–24; unchanged). **Diagonal** r×c, same domain (bits written row-wise into r×c, read along wrapped diagonals d = (c − r) mod C, in increasing d, rows top-down within a diagonal). **Convolutional** (Forney) B ∈ {2,3,4,6,8,12} branches × delay unit D ∈ {1,2,3,4,6,8}: input bit i on branch i mod B appears at output position i + (i mod B)·D·B; unfilled output positions are fill. **Pseudo-random**: 3GPP TS 36.212 Table 5.1.3-3 quadratic permutation polynomial (QPP) entries π(i) = (f1·i + f2·i²) mod K with K ≤ 384 (44 entries; all 188 table entries transcribed and verified to be permutations) | Block/diagonal/convolutional: project definitions of standard structures. QPP: 3GPP TS 36.212 v10.0.0 |
| Convolutional code | Burst: K7 (171,133), K5 (23,35), K3 (7,5), rate ½ (unchanged). Continuous stream: K7 (171,133) with and without **G2 output inversion** (CCSDS 131.0-B-5 §3.3.1), both c1/c2 pairings for BPSK | CCSDS 131.0-B-5 §3 |
| Frame synchronisation / bit-stream correlation | Catalogue markers: CCSDS ASM `1ACFFC1D` (32 bits), CCSDS 64-bit marker `034776C7272895B0` (TM rate-½/2/3/4/5 LDPC ASM and TC LDPC Start Sequence). Both polarities. Periodic markers over byte-aligned frame periods 64–16,384 bits, ≥ 2 frames. **Blind** periodic constant-field discovery for non-catalogue formats: byte-aligned periods 64–16,384 bits, window widths {16, 24, 32, 48, 64} bits, ≥ 2 frames | CCSDS 131.0-B-5 §9, CCSDS 231.0-B-4 §5.2.2 |
| Pseudo-randomizer (scrambler) | None; CCSDS TM 131071-bit h(x) = x¹⁷+x¹⁴+1, seed `11000111000111000`; CCSDS TM legacy 255-bit h(x) = x⁸+x⁷+x⁵+x³+1, all-ones seed; CCSDS TC BTG h(x) = x⁸+x⁶+x⁴+x³+x²+x+1, all-ones seed. Each checked against the first 40 published bits | CCSDS 131.0-B-5 §10, CCSDS 231.0-B-4 §6 |
| Reed-Solomon | CCSDS RS(255,223) E = 16 and RS(255,239) E = 8 over GF(2⁸), F(x) = x⁸+x⁷+x²+x+1, g(x) = Π(x − α^{11j}), j = 128−E … 127+E, **dual-basis** symbols (Annex F matrices), interleaving depth I ∈ {1,2,3,4,5,8}, virtual fill Q ∈ multiples of I (derived from the measured frame period) | CCSDS 131.0-B-5 §4, Annex F |
| Concatenated | Outer CCSDS RS (above), inner K7 rate-½ convolutional code (with or without G2 inversion), ASM convolutionally encoded, randomizer between (CCSDS order) | CCSDS 131.0-B-5 §5, §9.2.1.5, §10.2.2 |
| LDPC | **One code:** CCSDS TC LDPC (128,64). Parity-check matrix from §4.2.2 a); generator from Table 4-1 (W built from right circular shifts of each 16-bit circulant). Codeword offset ∈ [0,128) × {no randomizer, TC BTG preset per codeword} | CCSDS 231.0-B-4 §4, §6.3.2 |
| Not in catalogue v1 | Punctured convolutional rates, turbo codes, other LDPC codes, arbitrary RS parameters, arbitrary permutations, 64-QAM and higher, OFDM, differential encoding | — |

The H matrix and generator of the LDPC code come from two separate normative parts of CCSDS 231.0-B-4. They were checked against each other: H·Gᵀ = 0 over GF(2), and H has rank 64.

## 13. Acceptance Rule (adopted v2.3)

A hypothesis is accepted only if **all** hold:

1. **R0 — Syndrome sign test, Bonferroni.** Dual-code parity checks on hard decisions; exact Binomial p-value; accept if p · M ≤ 0.01 (M = number of hypotheses searched). Evidence e = log10 p + log10 M ≤ −2.
2. **MC — Modulation consistency.** Non-overlapping pairs v = y²(2m+1)·conj(y²(2m)): Re(v) > 0 for BPSK, fair coin for QPSK. Exact binomial tests reject QPSK hypotheses on BPSK-looking signals and BPSK hypotheses whose count is too low for BPSK at the measured SNR. α = 0.01, untuned.
3. **BL — Block-length consistency.** Transmission span from a two-level change-point fit to |y|²; reject if covered symbols < span − Δ, **Δ = 1.7 symbols** (99th percentile shortfall of correct hypotheses, calibration split).
4. **PM — Soft path-metric floor.** Zero-start Viterbi path metric ≥ **0.926** (99th percentile of top-1 path metric on calibration null files).

Rejected alternative: **RM** runner-up margin (cost recall). Calibration protocol: constants from even-indexed files, results on odd-indexed files, success criteria fixed before running.

**Re-encode consistency ≥ 0.98 is RETIRED as acceptance** (noise reaches 1.00; AUC 0.834; TPR 0 at zero null false positives). It remains a logged diagnostic.

### 13.1 Acceptance families (LOCKED in v2.5; pre-registered weights)

The v2.5 search has layers whose hypothesis counts differ by orders of magnitude. A few hundred burst hypotheses sit beside ~10⁸ frame-period windows. One Bonferroni bar over their sum would silently destroy the burst family's power. v2.5 therefore uses a **weighted Bonferroni** split, fixed here before any measurement:

| Family | What it tests | Weight wₓ | Per-hypothesis bar |
|---|---|---|---|
| **F1 burst code** | code × interleaver (block, diagonal, convolutional, QPP) × front end, zero-start burst; sign test + MC/BL/PM (§13) | 0.50 | p ≤ α·0.50 / M₁ |
| **F2 stream code** | continuous convolutional stream (K7, G2 inverted or not, c1/c2 pairing) × front end; the same sign test | 0.10 | p ≤ α·0.10 / M₂ |
| **F3 frame** | catalogue markers × polarity × period × offset, and blind constant-field windows × period × offset; exact binomial agreement tests | 0.20 | p ≤ α·0.20 / M₃ |
| **F4 block code** | RS profiles (E, I, Q, randomizer) on synchronised frames: exact union-bound probability that uniform random bytes decode; LDPC (128,64) offset × randomizer: sign test on satisfied parity checks | 0.20 | p ≤ α·0.20 / M₄ |

1. The weights sum to 1. By the union bound, P(any false structural claim on a file) ≤ α = 0.01. Every hypothesis actually tested in a family is counted in that family's M, including hypotheses tested only because an earlier layer was accepted (conditional testing never lowers a bar).
2. The weights are design choices, not fitted values. They may be changed only by amendment, never after looking at sealed results.
3. The F1 bar for bench-v1-type captures changes from α/M to 0.5·α/M, and M grows with the new interleaver types. **A recall loss on bench-v1 is expected and must be reported, not tuned away.**
4. Front-end selection for F3 and F4 on long captures is hierarchical (§11): front ends whose F2 stream code was accepted, plus the top front ends by symbol SNR (count declared in code and logged). Only tested hypotheses enter M.
5. An RS decode is **never** accepted on decoder success alone. The statistic is the exact tail P(≥ D successes of C codewords | uniform random bytes) with per-codeword probability V(n′, E)/256^{2E}. A structural check rejects degenerate codewords (all symbols equal), because constant bit streams (idle carriers) are codewords. The LDPC statistic is exact because the 64 rows of H are linearly independent.
6. Outcome mapping is unchanged:
   - **DECODED** requires an accepted FEC layer (F1, F2+F4, or F4).
   - A proven frame structure without an accepted code is **SIGNAL_NO_CODE**, with the frame map attached.
   - Otherwise **UNKNOWN**.

## 14. Output and Evidence Model

| Status | Condition | Payload |
|---|---|---|
| **DECODED** | A hypothesis passes §13 | Zero-start Viterbi payload |
| **SIGNAL_NO_CODE** | No hypothesis passes, but an x² or x⁴ line (or a real-signal structure) is significant | Hard decisions, explicitly **not decoded** |
| **UNKNOWN** | Neither | Empty |

Every result carries `accept{log10_p, log10_threshold, n_hypotheses}`, `accept.significant_but_rejected` (with reasons), all CFO candidates (order, peak-to-floor dB, p), the sps table (q4, q2), modulation statistic per sps candidate with margin, top-5 hypotheses (code, interleaver, sps, CFO, modulation, rotation, checks, positives, log10 p, z, covered/total bits, coverage, consistency, path metric, MDL savings), runner-up margin, front ends searched/rejected, and per-stage timers. The server packages this as an **evidence pack** (`server/evidence.py`, ~1 MB JSON per capture).

## 15. DSP Conventions and Proven Corrections (must never regress)

| Convention | Rule | Consequence if broken |
|---|---|---|
| LLR sign | LLR > 0 favours bit 0 | Every decode inverts |
| Matched-filter delay | `len(h) − 1` total (TX + RX) | Looks like noise |
| QPSK M-power phase | `(angle(mean(s⁴)) − π) / 4`; BPSK `angle(mean(s²)) / 2` | No valid rotation |
| Bit dtype | Cast to float before `1 − 2b` (uint8 wraps −1 → 255) | Plausible wrong output, no crash |
| Codeword termination | bench-v1 interleaver keeps only rows×cols of 812 coded bits → **truncated, no tail**; decode with `terminated=False` | Consistency ceiling ~0.9 |
| Terminated traceback | Starts from state 0, not argmax (bug found by exhaustive-ML test) | Not maximum likelihood |
| Encoder convention | Bit *i* of octal generator taps input delayed by *i* (LSB = current); "171" impulse response `1,0,0,1,1,1,1` — **bit-reversed vs MATLAB `poly2trellis`** (117/155 there) | Incompatible with standard tools |
| Complement-tolerant BER | min(BER, 1 − BER) < 0.01 | Under-counts recoveries |
| CFO resolution | Zero-pad x⁴ FFT 16×, keep several candidates | Misses true tone at low Es/N0 |
| Viterbi | Vectorised ACS, per-step renormalisation; equals exhaustive ML (K7/K5/K3, terminated/truncated, 150 noisy frames) | Silent decode loss |
| Syndrome scan | Vectorised with **the same factor order** as the scalar version | Non-identical p-values |

## 16. Real-Signal Receivers

Entry point `src/realsig.py` runs every receiver on one recording.

| Receiver | File | Method |
|---|---|---|
| Time codes (WWV, WWVB, DCF77, MSF, JJY) | `src/timecodes.py` | Per protocol: carrier; second epoch from the signal (fold + least-squares); per-second least-squares symbol classification; 60-s frame alignment on markers; **maximum likelihood over valid field values with parity as constraints** (DP over parity state); joint scoring of all complete frames. Detection p = P(≤ observed disagreements \| unrelated symbols) × distinct frames searchable, Bonferroni over catalogue, α = 0.01. **Every digit must beat every alternative by ≥ 100:1**, else SIGNAL_NO_CODE |
| FSK text | `src/fsk.py` | Anti-correlated tone pair; shift from coherent periodograms; baud from transition phase coherence (1.5-stop half-bit grid resolved in framing); framing hypotheses (baud × polarity × data bits × parity × stop bits) accepted by exact binomial stop-bit test, Bonferroni. ITA2/ASCII; CHU packets |
| AM | `src/broadcast.py` | Carrier offset by phase-slope fit, carrier-to-noise, coherent product detection, audio bandwidth; **one-sided receiver passbands detected and reported** instead of inventing modulation depth |
| MW census | `server/live.py::spectrum_census` | Averaged waterfall; carriers kept if topographically prominent vs ±1.5 channels; snapped to 9-kHz raster; matched to the official Prasar Bharati transmitter list |

**Independent checks, never used for the decision:** receiver GPS time vs decoded minute; RTTY text's own callsign/frequency; official AIR list.

## 17. Live Reception

- `server/kiwi.py`: stdlib websocket client for **public, volunteer-operated KiwiSDR receivers** (0–30 MHz, 12 kHz IQ, GPS block timestamps). Receivers ranked by distance to the transmitter from the public directory (deduplicated; follows HTTP redirects). IQ and waterfall streams.
- `server/live.py`: `LiveProcessor` runs the same processing incrementally (amortised buffer; epoch refit every 5 s until locked) and streams Server-Sent Events: spectrum rows, one symbol per second, digits as they become established, final blind analysis; the capture is saved as a recording.
- `server/stations.py`: station catalogue with official format references.
- Offline replays (`frontend/public/live/`) are produced by **the same `LiveProcessor`** over committed recordings (`server/export_live_replays.py`) — replays are real engine output, not animation.
- Time-code sessions capture ~3 minutes (single frames cannot meet the 100:1 digit rule).

---

# PART C — EVIDENCE

Environment of record: Windows 11, Python 3.11.14, NumPy 2.4.2, SciPy 1.17.0, 8 logical cores. CI: Ubuntu, Python 3.11, Node 22.

## 18. bench-v1 (regression tripwire)

Generator `src/generate.py` (unmodified): fs = 1 MHz, 400 random info bits, K7 (171,133), block interleaver, RRC, CFO ±0.01 cycles/sample, timing ±0.5 sample, random phase, AWGN.

| Parameter | train (seed0 1000, n = 100) | sealed (seed0 99000, n = 30) |
|---|---|---|
| Per-sample SNR (dB) | {0, 3, 6, 10, 15} | {2, 5, 8, 12} |
| sps | {4, 8} | {6} |
| Interleaver | {4×8, 8×8, 8×16} | {6×10, 10×12} |
| β | 0.35 | {0.25, 0.5} |

| Set | Pass | False accepts | UNKNOWN | SIGNAL_NO_CODE | Runtime |
|---|---|---|---|---|---|
| sealed (30) | **30** | **0** | 0 | 0 | ~1.5 s |
| train (100) | **63** | **0** | 17 | 20 | ~4.4 s |

Train by block: 32 bits (4×8) **0/24** — structurally unprovable at α = 1% (ten parity checks give p ≥ 10⁻³); 64 bits 37/41; 128 bits 26/35.
Pass = DECODED and BER < 0.01; DECODED with BER ≥ 0.01 is a false accept. CI gate: ≥ 28/30 and 0 false accepts.

### 18.1 bench-v2 policy (LOCKED in v2.5)

- Generator in `eval/` only (`src/generate.py` stays untouched).
- Three splits from disjoint seed ranges: **CALIBRATION** (constants may be fitted here), **TRAIN** (development and debugging), **SEALED** (final evaluation only).
- The SEALED manifest (per-file SHA-256 + manifest hash) is committed when first generated.
- Success criteria are committed in `eval/bench2_criteria.json` **before** SEALED is ever run.
- The SEALED runner refuses to run without an explicit final-evaluation flag, and it appends every run to a committed access log.
- A SEALED result obtained after any engine change made in response to it is reported as contaminated.
- Every result reports N, TP, FP, FN, recall, false-accept rate with a 95% Wilson upper bound, dataset and split provenance.

## 19. Null Set and Wrong-Structure Null

`eval/nullset.py` (seed0 500000, 1,350 files): sps ∈ {3,4,5,6,7,8,10,12}, β ~ U(0.2, 0.5), CFO ~ U(±0.01), timing ~ U(±0.5), Es/N0 ∈ {3,6,9,12} dB, coded lengths {30,60,120,240,384}. Classes: noise 500, uncoded BPSK 150, uncoded QPSK 150, 8PSK+K7 100 (out of family), K7/K5/K3 150 each.

| Metric (full null set, adopted rule) | Result |
|---|---|
| False accepts on 900 non-catalogue files | **0** (95% upper bound 0.43%) |
| Wrong decodes on 450 coded files | **0** |
| Correct decodes K7 / K5 / K3 | 61 / 37 / 31 of 150 each |
| Noise → UNKNOWN | 475/500 (R0 figures; SIGNAL_NO_CODE 21/500 = 4.2% vs 1% target) |
| Uncoded BPSK → SIGNAL_NO_CODE | 134/150 |
| Uncoded QPSK → UNKNOWN | 121/150 (x⁴ line too weak) |

**Wrong-structure null** (450 runs, true interleaver removed so any accept is wrong), evaluation split:

| Rule | Recall | Wrong-hypothesis accepts | Null false accepts | Wrong-structure accepts |
|---|---|---|---|---|
| R0 | 0.311 | 5/225 | 3/450 | 39/225 (17.3%) |
| **R0+MC+BL+PM (adopted)** | **0.320** | **0/225** | **0/450** | **2/225 (0.9%, ≤ 3.2%)** |

Mechanisms of R0's accepts: modulation × interleaver alias (8), partial coverage (5), barely significant (4).

## 20. Scoring Comparison

`python eval/nullset.py compare` — hypotheses decoded at the true front end, 180 coded vs 180 null files:

| Score | AUC | TPR at 0 null FP | ID accuracy |
|---|---|---|---|
| Hard re-encode consistency | 0.834 | 0.000 | 0.967 |
| **Soft path metric** | **0.994** | **0.939** | **0.989** |
| MDL savings | 0.800 | 0.000 | 0.972 |
| Sign test evidence (acceptance) | 0.960 | 0.844 | 0.900 |
| Syndrome soft z | 0.966 | 0.889 | 0.944 |

The path metric is the most powerful separator but has no analytic null; it is therefore used as a **calibrated floor on top of** the sign test, not instead of it.

## 21. Oracle Ladder (failure attribution)

`eval/ladder.py`: first oracle that makes each file pass (O0 blind … O7 interleaver).

| Stage | sealed | train |
|---|---|---|
| O0 blind | 30 | 63 |
| O1 +modulation | 0 | 0 |
| O2 +sps | 0 | 5 |
| O3 +CFO | 0 | 6 |
| O4 +β | 0 | 0 |
| O5 +fractional timing | 0 | 1 |
| O6 +phase/rotation | 0 | 0 |
| O7 +interleaver | 0 | 24 (23 are 32-bit files: the oracle lowers the Bonferroni bar, not an ID error) |
| never | 0 | 1 |

## 22. Real Transmissions (received blind, independently checked)

| Recording | Receiver | Engine answer | Evidence | Independent check |
|---|---|---|---|---|
| JJY 40 kHz (NICT) | Okegawa, 191 km, GPS | **DECODED** 2026-09-17 03:17 UTC | 2 frames, 0/120 disagree, p = 10^-32.3, all 9 digits | **+1.9 ms** vs GPS |
| DCF77 77.5 kHz (PTB) | Trémolat, 839 km | **DECODED** 03:17 UTC | 0/88, p = 10^-14.7 | **+4.7 ms** |
| MSF 60 kHz (NPL) | SW England, 466 km | **DECODED** 02:58 UTC | 11/120, p = 10^-15.0 | **+3.6 ms** |
| WWV 10 MHz (NIST) | W. Montana, 976 km | **DECODED** 02:58 UTC | 3/109, p = 10^-23.4 | **+23.4 ms** (sky-wave + receiver filter) |
| WWVB 60 kHz (NIST) | W. Montana | **SIGNAL_NO_CODE** — structure p = 10^-4.7, **time refused** | 25/119 disagree, no digit ≥ 100:1 | ML frame said 2066 — wrong; the digit rule prevented a false time |
| DDH47 147.3 kHz (DWD) | Høll Strand, 219 km | **DECODED** ITA2 | 50 Bd, 85.0 Hz, 1.5 stop, 825/828 stop bits, p = 10^-241 | Text names its own callsign and frequency |
| AIR Chennai 720 kHz (Prasar Bharati) | Bangalore, 287 km | **SIGNAL_NO_CODE** — AM | Carrier 53 dB above noise, 2.6 kHz audio; one sideband detected and reported | 720 kHz Chennai 200 kW in official list |
| AIR MW band | Bangalore, 60-s waterfall | 5 carriers | Prominence-filtered, raster fit 1.0021 | **5/5** matched official list |

Recordings: `recordings/real/` (IQ `.wav` + JSON sidecar with GPS start; MW band `.npz`). 21 tests in `tests/test_realsig.py` run them in CI. CHU decoder tested on synthetic packets only (not receivable during the session).

## 23. Performance (decision-identical)

| Set | Files | Before | After | Speed-up | Decision differences |
|---|---|---|---|---|---|
| sealed | 30 | 5.6 s | 1.5 s | 3.7× | 0 |
| train | 100 | 16.9 s | 4.4 s | 3.8× | 0 |
| null set | 1,350 | 734.6 s | 241.2 s | 3.0× | 0 (`syndrome_z` < 1e-9) |

FSK tone-pair search: one STFT per shift class (30 s → 2.5 s on 125 s). RRC taps cached.

## 24. Component Status (authoritative)

| # | Component | Status | Evidence | Next |
|---|---|---|---|---|
| 1 | `.iq` ingestion | **PROVEN** | `load_iq`, tests | — |
| 2 | `.wav` ingestion | **PROVEN on real signal** | All real recordings load via `load_wav`; CI | — |
| 3 | Signal-presence test (x²/x⁴ line vs exponential null) | **PARTIALLY PROVEN** | Anti-conservative: noise → SIGNAL_NO_CODE 4.2% vs 1% | Calibrate empirically |
| 4 | SNR / LLR scaling (symbol-domain M2M4) | **FUNCTIONAL** | Es/N0 formula vs genie median −0.64 dB sealed, −0.31 dB train | Measure estimator error |
| 5 | Symbol-rate candidates | **PARTIALLY PROVEN** | True sps in candidates 30/30 sealed, 91/100 train; 5 train files wait on sps | Better ranking |
| 6 | Modulation (BPSK/QPSK) | **PROVEN on bench-v1** | 0 files wait on modulation; MC check | Out-of-family class |
| 7 | CFO candidates + M-power phase | **PARTIALLY PROVEN** | 6 train files wait on CFO (low-Es/N0 QPSK) | CFAR candidates, interpolation |
| 8 | Demodulation (RRC MF, fixed delay) | **PROVEN on bench-v1** | Genie decodes | Fractional timing |
| 9 | Soft bits (LLR) | **PROVEN** | Convention test | — |
| 10 | Catalogue code ID (K7/K5/K3, sign test + Bonferroni + MC/BL/PM) | **PROVEN on null set** | 0/900 false accepts, 0/450 wrong decodes; wrong-structure 0.9% | Recalibrate PM for new channels |
| 11 | Block interleaver ID (≤ 384 bits) | **PARTIALLY PROVEN** | 30/30 sealed; wrong-structure 2/225; ≤ 32-bit blocks unprovable | Multi-block (bench-v2) |
| 12 | Vectorised soft Viterbi | **PROVEN (self-consistent)** | = exhaustive ML; standard conformance not verified (bit-reversed convention) | Reference vectors |
| 13 | Re-encode consistency | **RETIRED as acceptance** | AUC 0.834, TPR 0 | Diagnostic only |
| 14 | Structural acceptance (MC, BL, PM) | **PROVEN on null set** | §19 | Channel generalisation |
| 15 | bench-v1 sealed | **30/30, 0 false accepts** | Tripwire only | bench-v2 |
| 16 | bench-v1 train | **63/100, 0 false accepts** | §18 | Low Es/N0 recall |
| 17 | Vectorised hypothesis search | **PROVEN** | 3.0–3.8×, 0 decision differences on 1,480 files | — |
| 18 | Rank-based blind FEC ID | **PARTIALLY PROVEN** | Collapses at 0.1% BER | Clean-signal tool only |
| 19 | Tests + CI | **PROVEN on GitHub** | 30 tests (9 core + 21 real-signal); CI green on PR #2 (tests, sealed gate, frontend build) | — |
| 20 | Deterministic data generation | **PROVEN** | Byte-identical from seed | — |
| 21 | Reject path (3 outcomes) | **PROVEN** | Null set; WWVB time refused | — |
| 22 | Time-code receivers (5 protocols) | **PROVEN on real signal** | §22: 4 decoded ±1.9–23.4 ms, 1 correctly refused | Receiver delay calibration |
| 23 | FSK start-stop (ITA2/ASCII) | **PROVEN on real signal** | DDH47 p = 10^-241 | Synchronous FSK (SITOR-B/NAVTEX) |
| 24 | CHU packets | **IMPLEMENTED, tested synthetic** | Not received live | Receive CHU |
| 25 | AM characterisation + one-sided passband detection | **PROVEN on real signal** | AIR Chennai | DRM (AIR digital MW) |
| 26 | MW carrier census vs official list | **PROVEN on real signal** | 5/5 | Wider band, other cities |
| 27 | Live reception (KiwiSDR, SSE) | **PROVEN** | Live DWD and WWV sessions; replays from same processor | Receiver delay calibration |
| 28 | Operator console (ICHNOVA) | **FUNCTIONAL** | 16 routes, both themes, CI build (§27) | Usability testing with operators |
| 29 | Evidence packs / reports / audit trail export | **FUNCTIONAL** | PDF (print), JSON, CSV | Signed packs |
| 30 | Google sign-in | **FUNCTIONAL (prototype)** | Client-side token decode, not verified server-side | Server-side verification / on-prem IdP |
| 31 | Signal genome similarity | **EXPERIMENTAL** | Shown with label | Validation study |
| 32 | Monitoring network, incidents, occupancy | **SIMULATED** | `sim.ts` | Real station feeds |
| 33 | Frame sync / bit-stream correlation, header/payload map | **IMPLEMENTED, measured on synthetic captures** | Family F3 in the engine: ASM found blind at P = 512 and P = 2,072 with the frame map attached; a framed stream with no code is SIGNAL_NO_CODE; noise and an idle carrier refused; M₃ counts the whole declared domain | Real framed recording (row 42) |
| 34 | 8PSK, 16-QAM identification and demodulation | **EXPERIMENTAL — implemented, gated, OFF BY DEFAULT** (`pipeline.SEARCH_HIGHER_MODULATIONS = False`) | Primitives verified (BER < 1e-3 at 20 dB, gates separate the classes). Enabled, both decode blind: 8PSK with block, diagonal and convolutional interleavers and 16-QAM with block, all at payload BER 0 at 20 dB; development sweep 18/96 bursts at Es/N0 11–20 dB with 0 wrong decodes. **v2.5.3, measured over the full 1,350-capture null set** (`reports/HIGHER_MODULATION_EXPERIMENT.md`): enabling it costs 7.2× runtime and buys **nothing** — 0 of 100 8PSK captures decode, though the gate genuinely opens on 88 of them and the hypothesis count rises by a median 21.8×, because the multiple-testing bar rises by about the same factor. False accepts are **0/800 either way**, so the original concern was not the problem; the real one is that `k5_060_003`, a BPSK capture that decodes bit-perfectly with the gate off, decodes as 8PSK with a *stronger* p-value (10^−10.87 vs 10^−10.23) and a payload 40 % wrong — a structural alias (8PSK carries 3 bits/symbol, so a 9×20 interleaver explains what 3×20 truly explains) whose parity checks genuinely pass, which no statistical test can catch | Default path needs a modulation classifier confident enough to choose the constellation **before** the code search, so absent modulations never enter the pool |
| 35 | Reed-Solomon (CCSDS, dual basis, depth I), concatenated RS + K7 | **IMPLEMENTED, measured on synthetic captures** | Encoder matches reedsolo on 28 vectors, dual basis matches Annex F. Full chain decoded blind (RS(255,223) E=16 I=1 + TM 131071 randomizer + ASM P=2,072 + inner K7): every parameter identified, 4/4 codewords, payload BER 0. Accepted on the exact tail P(≥ D decodes), never on decoder success; constant fill refused as degenerate | Real recording (row 42); bench-v2 |
| 36 | Diagonal, convolutional and QPP pseudo-random interleavers; CCSDS TC LDPC (128,64) | **IMPLEMENTED, measured** | All four interleaver types are searched in the default path: bench-v1 sealed 30/30 and train 63/100 unchanged, null set 0/900 false accepts and 0/450 wrong decodes, wrong-structure accepts 0/225 (was 2/225 with block only), M₁ ≈ 2.4×. LDPC: H·Gᵀ = 0 and rank 64 at import; a TC LDPC CLTU decoded blind at offset 64 with 1,536/1,536 checks and payload BER 0 (polarity reported unresolved) | bench-v2 channel classes |
| 36a | Sample-rate provenance (`fs_source`), no silent default | **LOCKED (v2.5)** | §10 | P0 |
| 36b | Catalogue pseudo-randomizers (CCSDS TM 131071 / 255, TC BTG) | **IMPLEMENTED, verified against the standards** | Each reproduces the published first 40 bits; the randomizer is identified blind as part of an F4 hypothesis (TM 131071 on the RS chain, TC BTG on the CLTU) | — |
| 37 | Cyclic-CAF symbol-rate estimator | **BLOCKED** | Only 5/100 train failures wait on sps | §36.1 |
| 38 | SAGE-Lite feedback | **BLOCKED** | Needs calibrated soft score, frame sync/CRC, bench-v2 | §36.3 |
| 39 | 2 dB QPSK rescue experiment | **PREMISE CHANGED** | Sealed 2 dB QPSK files pass; test_020/025 failures don't reproduce | Re-target at stress set |
| 40 | Conformal prediction / formal UNKNOWN | **FUTURE** | — | Research |
| 41 | bench-v2 (catalogue v1 families, nulls, channel impairments, sealed split §18.1); adversarial benchmark | **LOCKED (v2.5)** for bench-v2; adversarial FUTURE | — | §35 |
| 42 | Real PSK/FEC recording analysed blind vs an independent published decode | **LOCKED (v2.5)** — dataset must first pass the compatibility check in §35 | — | §35 |
| 43 | Arbitrary blind LDPC, arbitrary pseudo-random interleaver | **REJECTED** (catalogue versions are LOCKED, rows 36, 36b) | Rank collapse | — |
| 44 | Generic CNN/ResNet acceptance | **REJECTED** | No per-decision error control | ML only for prioritisation (FUTURE) |
| 45 | BSS/ICA multi-signal separation | **REJECTED for MVP** | Single-signal scope | — |
| 46 | Local SDR hardware capture | **SUPERSEDED** | Public receivers used | Field hardware when authorised |
| 47 | Full SAGE / BCJR / factor graph | **FUTURE** | Research-grade | After MVP |

## 25. Known Limitations (must be disclosed when relevant)

1. Low-Es/N0 recall: K7 correct 3/34 at 3 dB, 13/40 at 6 dB, 20/40 at 9 dB, 25/36 at 12 dB (Es/N0).
2. Blocks ≤ 32 coded bits are unprovable at α = 1%.
3. Signal-presence test is anti-conservative (4.2% vs 1%); uncoded QPSK usually UNKNOWN.
4. BL assumes the burst starts at capture start; PM floor calibrated on one generator family (fading/phase noise need recalibration).
5. Payload rotation resolved by assuming zero encoder start state; no frame sync.
6. Viterbi convention bit-reversed vs MATLAB; standard conformance unverified.
7. Real signals: the operator chooses where to listen; receiver filter delay uncalibrated (WWV +23 ms); Indian receivers deliver one sideband in IQ mode; availability depends on propagation and schedules.
8. Web tier is `http.server`: single process, **no TLS of its own** — demo grade. The API is authenticated since v2.5.3 (scrypt passwords, signed session tokens, role permissions, rate limiting). Since v2.5.4 a TLS reverse proxy is **CONFIGURED** in `deploy/` (nginx, 308 redirect, forwarded headers matched to `Handler._client`, SSE buffering off, upload cap matched to `MAX_UPLOAD`) — but it has **never been exercised or served traffic**: no Docker daemon and no native nginx on the development machine. TLS status is CONFIGURED, not live. Container base-image CVEs are **NOT ESTABLISHED** (no image scanner available); Python and Node dependencies scan clean.
8a. Rate limiting and session revocation are **in-process and in memory** (v2.5.4). They protect a single process; they are not a distributed quota. A restart clears both — which invalidates every issued session when `ICHNOVA_SECRET_KEY` is unset, and is the safe direction. Deliberately no database: §9.2 keeps the engine air-gap capable.
9. Console monitoring-network data is simulated.

---

# PART D — THE PRODUCT

## 26. ICHNOVA Brand

| Element | Rule |
|---|---|
| Mark | Wave rising into a four-point star on a vertical line, a crescent, and a long gold tail. Drawn as SVG in `frontend/src/components/brand.tsx` (`BrandMark`, `Wordmark`, `Lockup`); PNG sources in `frontend/public/ichnova-*.png` |
| Wordmark | "ICHNOVA", widely spaced; the A has no crossbar (Λ) |
| Colour | Dark: gold `#f7dfb3 → #c78a4b` on near-black `#0c0b0a`. Light: ink `#17140f` on ivory `#f5f2eb` |
| Favicon | Gold mark on a dark rounded tile (`favicon.svg`, `favicon.png`) |
| Copy | Name, context, sponsor, taglines, restraint line and disclaimer only from `brand.ts` |
| Disclaimer (always present in footers) | Independent SIH prototype; not an official Government of India system |
| Forbidden | "THADAM"; government emblems (Ashoka emblem, Satyameva Jayate), ministry logos, `.gov.in` styling that implies official status |

## 27. Operator Console

React 19 + TypeScript + Vite 8 SPA (`frontend/`), served by `server/app.py` from `frontend/dist`.

| Route | Page | Purpose | Data |
|---|---|---|---|
| `/` | Landing | One primary action, headline figures (measured), four service cards, real signals, how it works, coverage | BENCHMARK / LIVE |
| `/signin` | Sign in | Role (Field / Regional / National) and station; Google or operator credentials; demo analyst | — |
| `/app/command` | Home | Welcome, four task cards, four KPIs, station map, "Needs attention", verified real transmissions; trends folded | SIMULATED + LIVE |
| `/app/analysis` | Analyse a capture | 7-step flow: Capture → Upload → Detect → Analyse → Classify → Verify → Report; samples in tabs (Real transmissions / Benchmark) | LIVE / BENCHMARK |
| `/app/monitor` | Live signals | Stations by group; Replay or Receive live; minute dial, digits, GPS check, teleprinter, AIR census | LIVE |
| `/app/review` | Review queue | Analyst decisions on non-decoded / flagged signals | Mixed |
| `/app/signals`, `/app/signals/:id` | Signal library / record | Tabs; record header with facts; evidence chain, hypotheses | Mixed |
| `/app/incidents`, `/app/incidents/:id` | Incidents | Patterns worth investigating; status, notes | SIMULATED |
| `/app/reports` | Reports | Signal/incident evidence report; PDF, JSON pack, CSV audit | Mixed |
| `/app/spectrum` | Spectrum map | Occupancy views | SIMULATED |
| `/app/intelligence` | Intelligence | Regional/national aggregation (`?view=scale`) | SIMULATED |
| `/app/genome` | Signal genome | Fingerprints, similarity | EXPERIMENTAL |
| `/app/lab` | Evidence lab | Real transmissions, benchmark, oracle ladder, null test, acceptance rules, scoring, FEC vs Es/N0, runtime, performance, landscape | BENCHMARK / LIVE |
| `/app/system` | System | Data flow, engine configuration (from evidence pack), coverage, data quality, audit trail | Mixed |

Navigation groups: **Overview** (Home) · **Work** (Analyse a capture, Live signals, Review queue) · **Records** (Signal library, Incidents, Reports) · **Insights** (Spectrum map, Intelligence, Signal genome) · **About the engine** (Evidence lab, System). Top bar: breadcrumbs, View (Field station / Regional / National), engine status pill (online, or offline · replay), Guided tour (6 scenes), user menu. Without the server the console replays stored evidence and says so.

## 28. Data Honesty in the Product

- Every panel with numbers shows a provenance label (§8.2).
- Stamps for outcomes: DECODED (green), SIGNAL · NO CODE (cyan), UNKNOWN (amber).
- Refusal is presented as a result (e.g. WWVB "time refused" is a featured case).
- The engine configuration on the System page is read from the evidence pack, not typed.
- Regenerate the real-data layer with `server/export_frontend_data.py` and `server/export_live_replays.py`; never edit `frontend/public/evidence`, `benchmark.json` or `live/` by hand.

## 29. UX, Accessibility and Themes

**Reference model (similar-work Indian government portals only):** DoT **Tarang Sanchar** (EMF/spectrum information: accessibility bar, one primary action, overview statistics, learn cards, footer with last-updated) and DoT **Saral Sanchar** (WPC licensing: short service cards with icon + title + ≤ 25-word description, grouped menus); NTIA ITS spectrum-monitoring pages for breadcrumbs and problem → approach → tools structure. UX4G (NeGD) guidance on WCAG/GIGW informs accessibility. These are **design references only**; ICHNOVA is not affiliated with them and does not copy their branding.

Rules:
1. **One primary action per screen**; at most four task cards on Home.
2. **Progressive disclosure:** secondary charts in "Show …" disclosures; long lists behind tabs; coverage details collapsed.
3. **Utility bar on every screen:** skip to content, text size A− / A / A+ (0.9, 1, 1.12, 1.25), Light / Dark.
4. **Themes:** all colours are CSS tokens (`:root[data-theme='light'|'dark']` in `styles.css`); canvases and waterfalls read the same tokens (`src/lib/theme.tsx`); choice stored in `localStorage` (`ichnova.theme`, `ichnova.textScale`) and applied before first paint.
5. **Tables:** IDs, numbers and dates never wrap; wide tables scroll inside their panel; missing values show "—".
6. **Layout checks before merge:** 1920, 1440, 1366×768 and 390 px wide, both themes, no horizontal page scroll, no console errors.
7. Plain language: name things by what operators recognise ("Analyse a capture", "Review queue"), not by internals.

### 29.1 Design system (v2.5.2; Operate-mode pass, 2026-09-18)

The console is an **Operate** surface: the operator is in a task, so scanability, one consistent
component vocabulary and the real usage scene outrank expression. Brand lives in precise details, not
in decoration. The rules below are enforced in `frontend/src/styles.css` and checked by the
Impeccable anti-pattern detector (§32).

| Axis | Rule |
|---|---|
| Type | One family (IBM Plex Sans), **fixed rem scale** `--t-xs … --t-3xl`, ratio ~1.2. No fluid headings in the app: the operator reads at a constant size. Monospace is for data and measurement (identifiers, p-values, counts), never as a costume for "technical" |
| Numerals | Tabular figures everywhere; slashed zero in monospace data, so columns of digits align and 0 never reads as O |
| Colour | Restrained. The accent marks **primary action, current selection and state**, never decoration. One interaction vocabulary shared by every component: `--surface-hover`, `--surface-selected`, `--surface-pressed` |
| Elevation | Hairlines separate; shadow is reserved for surfaces that actually float (drawer, tour, map tooltip, `.panel.raised`). A page of static panels reads as one plane |
| Motion | State only, one easing (`--ease`), `--dur-1` 160 ms for controls and `--dur-2` 220 ms for surfaces. No layout-animating properties (width/height/padding); meters scale with a transform. `prefers-reduced-motion` disables all of it |
| Browser surfaces | Focus ring, caret, selection, placeholder, list markers and scrollbars are themed from the palette in both themes. They are part of the design, not defaults |
| States | Every interactive component ships default, hover, focus, active, disabled and (where it applies) loading and error. Lists have an empty state that teaches the next action (`.empty`); slow content uses skeletons (`.skeleton`), not a spinner in the middle of the page |
| Labels | **No decorative kicker above a heading.** The heading carries itself. Identifiers and counters are set quietly (`.meta`); a group of items may carry a small label (`.section-label`) |
| Cards | Cards are not the page structure, and nested cards are never right. Regions are separated by rules and spacing |

## 30. Web Tier and API

`server/app.py` — stdlib `ThreadingHTTPServer`, hand-rolled router, SPA fallback; default `127.0.0.1:8765` (`--host 0.0.0.0` for LAN demos).

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Engine version and status |
| `POST /api/analyze` | Analyse an uploaded capture → evidence pack |
| `GET /api/recordings/…` | Committed real recordings |
| `GET /api/live/stations` | Station catalogue |
| `POST /api/live/start`, `POST /api/live/stop` | Start/stop a live session |
| `GET /api/live/events` | Server-Sent Events stream |
| `GET /api/live/sessions`, `/api/live/session/…`, `/api/live/file/…` | Session list, detail, saved capture |

| `GET /api/ledger` | Evidence receipts as stored, one raw JSON line each, for independent chain verification |
| `GET /api/sources` | Signal sources with provenance, licence, what they feed and measured health |
| `GET /api/crm/status`, `POST /api/crm/queue`, `POST /api/crm/flush` | Salesforce case hand-off through the local outbox (§9.2) |

Every endpoint requires authentication (§25.8) except `/api/health` and the sign-in routes; `ICHNOVA_OPEN_API=1` restores the old open behaviour for a single-user offline workstation. Permissions are checked server-side per endpoint against the role in the session token.

## 31. Tech Stack, Dependencies and Licensing

| Layer | Stack |
|---|---|
| Engine | Python 3.11; **numpy 2.4.2, scipy 1.17.0 — the entire `requirements.txt`**; no GNU Radio, no ML framework |
| Web tier | Python stdlib only (`http.server`, SSE, websocket client) |
| Console | React 19, TypeScript, Vite 8, react-router 7, framer-motion, d3-geo + topojson-client, IBM Plex (`@fontsource`), `@react-oauth/google`; hand-written CSS; oxlint |
| Map data | DataMeet India boundaries, Survey of India depiction (CC BY 4.0) |
| Tests / CI | pytest; GitHub Actions |

Rules: prefer MIT/BSD/Apache; pin versions; offline wheels for air-gapped installs; **never embed GPL code** in the deliverable (FFTW excluded if liquid-dsp is ever used). Optional references: AFF3CT (MIT), liquid-dsp (MIT without FFTW).

## 32. Quality Gates

| Gate | Command | Must hold |
|---|---|---|
| Tests | `python -m pytest -q tests` | 30/30 |
| Sealed tripwire | `python sealed_test.py data/sealed 30 --min-pass 28 --max-false-accept 0` | CI gate; reference machine 30/30, 0 FA |
| Train | `python sealed_test.py data/train 100` | ≥ 63/100, 0 false accepts (no silent regression) |
| Frontend | `cd frontend && npm ci && npm run build` | Type-check + build |
| Decision-changing engine change | Null set + wrong-structure null + report | Criteria fixed before running |
| Performance change | Decision-identity check on sealed + train + null set | 0 differences |
| UI change | §29.6 screenshots | No overflow, both themes |
| UI change | `npx impeccable detect frontend/src` | 0 anti-patterns (design-system rules, §29.1) |

A 4/30 commit once reached `main` unverified (v2.1); CI exists so that cannot recur.

## 33. Repository Map

| Path | Purpose |
|---|---|
| `src/pipeline.py` | `analyze_file()` / `analyze_iq()`, search domain, acceptance |
| `src/blind_id.py` | Catalogue, interleaver domain, syndrome scan, sign test, hypothesis decode |
| `src/analyze.py` | Symbol-rate spectrum, matched filter, M-power, M2M4, LLRs |
| `src/fec.py` | Encoder, vectorised soft Viterbi, block interleaver |
| `src/modem.py` | Modulation, RRC, channel, IQ/WAV I/O |
| `src/generate.py` | Deterministic bench-v1 generator (**do not modify**) |
| `src/timecodes.py`, `src/fsk.py`, `src/broadcast.py`, `src/realsig.py` | Real-signal receivers |
| `server/app.py`, `server/evidence.py` | API, evidence packs |
| `server/kiwi.py`, `server/live.py`, `server/stations.py` | Public receivers, live sessions, station catalogue |
| `server/make_recording.py`, `server/record_band.py` | Capture → recording fixture; band waterfall |
| `server/export_frontend_data.py`, `server/export_live_replays.py` | Console data layer |
| `eval/snr.py`, `eval/ladder.py`, `eval/nullset.py`, `eval/acceptance.py` | Evaluation |
| `tests/test_core.py` (9), `tests/test_realsig.py` (21) | Regression |
| `recordings/real/`, `recordings/reference/air_mw_transmitters.json` | Government transmissions (IQ + GPS sidecars); official AIR transmitter list |
| `frontend/` | ICHNOVA console |
| `reports/` | Measured reports and raw evidence |
| `sealed_test.py` | Benchmark harness |
| `.github/workflows/ci.yml` | CI |

## 34. Workflows

```bash
# Reproduce everything (from repo root)
pip install -r requirements.txt pytest
python src/generate.py sealed && python src/generate.py train
python -m pytest -q tests
python sealed_test.py && python sealed_test.py data/train 100
python eval/snr.py
python eval/ladder.py data/sealed 30 data/train 100
python eval/nullset.py generate && python eval/nullset.py run && python eval/nullset.py report && python eval/nullset.py compare

# Real signal → regression fixture
python server/kiwi.py --freq-khz 40 --seconds 185 --near 37.37,140.85 --out jjy.npz
python server/make_recording.py jjy.npz --id my-jjy --station JJY --out-rate 1500
python -m pytest -q tests/test_realsig.py

# Console
python server/export_frontend_data.py && python server/export_live_replays.py
cd frontend && npm install && npm run build && cd ..
python server/app.py            # http://127.0.0.1:8765
```

Branching: work on a feature branch (currently `baseline-hardening`, PR #2), CI-gated, fast-forward to `main`. No force pushes. Commits by Claude end with the Co-Authored-By line; PR bodies with the Claude Code line.

---

# PART E — DIRECTION

## 35. Critical Path and Priorities

The v2.0 plan (freeze 28/30 → Cyclic-CAF → SAGE-Lite → 2 dB QPSK rescue) is **historical**: the 28/30 failures do not reproduce, consistency acceptance is retired, and the oracle ladder shows sps is not the main bottleneck.

**Current critical path (engine), v2.5.** The audit showed that SIH26147 names capabilities the engine lacked, so closing them under the existing acceptance discipline comes first. bench-v2 grows alongside them.

```
fs provenance (no silent default)
→ catalogue primitives with external reference vectors: GF(2⁸)/RS dual basis, CCSDS randomizers, LDPC (128,64), QPP/diagonal/convolutional interleavers, 8PSK/16-QAM
→ acceptance families F1–F4 wired into one decision (§13.1); bench-v1 and null-set regression measured and reported
→ bench-v2 generator + nulls + sealed split (§18.1)
→ frame sync + header/payload; RS + concatenated; LDPC; QAM; interleavers — each with null and wrong-structure tests
→ detection-test calibration (4.2% → 1%); channel robustness (fading, phase noise, CFO drift)
→ real-noise null on committed recordings; real PSK/FEC recording (only if compatible with the declared domain)
→ data-quality flag; recapture guidance ("what would prove it"); console: fs provenance, elimination funnel, frame map
→ only then Cyclic-CAF (if sps misses grow) and SAGE-Lite (§36)
```

| Priority | Item |
|---|---|
| **P0** | fs provenance; frame sync / bit-stream correlation + header/payload; RS + concatenated; 8PSK/16-QAM; diagonal/convolutional/QPP interleavers; CCSDS TC LDPC (128,64); acceptance families; bench-v2 with sealed split; keep 0 false accepts |
| **P0 (validation)** | Null and wrong-structure tests per family; real-noise null on committed recordings; detection calibration; PM/structural checks under fading and phase noise |
| **P1** | Real PSK/FEC recording (compatibility check first: modulation, coding, bandwidth, sample rate, framing, published decode, representable in the declared domain); data-quality flag; recapture guidance validated by truncation; console evidence funnel; operator usability test |
| **P2** | Synchronous FSK; receiver delay calibration; DRM characterisation; genome validation; server-side auth for LAN |
| **DEFERRED (not approved)** | Salesforce/CRM workflow, official-list diff, sky canaries, multi-receiver pooling (proposals of 2026-09-17; closed no SIH requirement) |
| **Research** | SAGE-Lite; conformal UNKNOWN; full BCJR/factor graph; adversarial benchmark |

## 36. Research Frontier (references verified 2026-09-16)

### 36.1 Cyclic-CAF symbol-rate estimation — BLOCKED
Cyclostationary features at the symbol rate have **no SNR wall** (unlike energy detection; Tandra & Sahai). Start with Welch-averaged |x|/|x|² spectra + constrained sps search; add Dandawate–Giannakis significance testing only if needed; avoid the full 2-D SCF on CPU budget. Unblock when sps misses exceed a measured share of failures on bench-v2.
- W.A. Gardner, "Exploitation of Spectral Redundancy in Cyclostationary Signals," IEEE SP Magazine 8(2):14–36, 1991
- A.V. Dandawate & G.B. Giannakis, "Statistical tests for presence of cyclostationarity," IEEE Trans. SP 42(9):2355–2369, 1994
- W.A. Gardner, A. Napolitano, L. Paura, "Cyclostationarity: Half a century of research," Signal Processing 86(4):639–697, 2006
- M. Oerder & H. Meyr, "Digital filter and square timing recovery," IEEE Trans. Comms COM-36:605–612, 1988

### 36.2 Code-aided synchronisation (literature)
- N. Noels et al., "Turbo synchronization: an EM algorithm interpretation," IEEE ICC 2003, 4:2933–2937
- C. Herzet, V. Ramon, L. Vandendorpe, "A theoretical framework for iterative synchronization based on the sum-product and the EM algorithms," IEEE Trans. SP 55(5):1644–1658, 2007
- C. Herzet et al., "Code-aided turbo synchronization," Proc. IEEE 95(6):1255–1271, 2007
- N. Noels et al., "A theoretical framework for soft-information-based synchronization in iterative (turbo) receivers," EURASIP JWCN, 2005
- J.A. Fessler & A.O. Hero, "Space-alternating generalized expectation-maximization algorithm," IEEE Trans. SP 42(10):2664–2677, 1994
- B.H. Fleury et al., "Channel parameter estimation in mobile radio environments using the SAGE algorithm," IEEE JSAC 17(3):434–450, 1999
- U. Mengali & A.N. D'Andrea, *Synchronization Techniques for Digital Receivers*, Plenum, 1997

**Literature gap (v2.0 finding, still a hypothesis-level claim):** turbo-sync work assumes the code is known; blind FEC identification assumes synchronisation is achieved. Blind catalogue identification followed by decode-aided refinement was not found treated in the open literature.

### 36.3 SAGE-Lite — BLOCKED
Definition: decision-directed synchronisation refinement using FEC-corrected symbols from a **blindly identified** code; bounded updates (|Δτ| ≤ 1 symbol, |Δφ| ≤ π/2, |ΔΔf| ≤ 0.005 cycles/sample), 1–3 iterations, best iteration kept, every iteration logged. Not full SAGE, BCJR or a factor graph.
**Why blocked:** feedback would reinforce wrong-structure accepts unless acceptance is calibrated on the target channel; no frame sync or CRC to confirm a refined payload; bench-v1 leaves too few feedback-rescuable failures to measure benefit. Unblock after bench-v2 + frame sync. Required ablation when run: baseline vs feedback with decoded symbols vs feedback with raw decisions.

### 36.4 Other directions
Conformal prediction for formal UNKNOWN (Vovk et al. 2005; Bates et al. 2021); signal genome fingerprinting (currently EXPERIMENTAL in UI); BCJR (Bahl et al. 1974); factor graphs (Kschischang, Frey & Loeliger, IEEE Trans. IT 2001); adversarial benchmark.

## 37. Novelty and Claims

### 37.1 Established (not our invention)
Cyclostationary analysis, cumulant/M-power methods, Viterbi, convolutional codes, catalogue hypothesis testing (PROCITEC "revolver principle", 2003), syndrome-based recognition (Moosavi & Larsson, IEEE Trans. Commun. 62(5), 2014), interleaver detection (Sicot, Houcke & Barbier, Signal Processing 89(4), 2009), convolutional code reconstruction (Côte & Sendrier, ISIT 2009), GF(2) rank methods (Marazin et al. EURASIP JWCN 2011; Tamakuwala, DSJ 69(3):274–279, 2019, DOI 10.14429/dsj.69.13370).

### 37.2 Our defensible contributions (measured)
1. **Exact, family-wise error-controlled acceptance over the joint front-end × code × interleaver search, with structural checks against wrong-structure accepts** — 0/900 false accepts, 0/450 wrong decodes, wrong-structure 0.9%.
2. **Refusal as a measured output**, carried into every screen and report.
3. **Checked against the world:** blind decodes of government transmissions compared with GPS time, the transmission's own content and India's official transmitter list.
4. **Measured before claimed:** oracle ladder, null sets, held-out calibration, decision-identical performance work.
5. **Two-dependency, air-gap-compatible, fully auditable implementation** (engineering, not scientific, novelty).

### 37.3 May say
- "Accepts a decode only when an exact test, corrected for every hypothesis it tried, supports it — and says UNKNOWN otherwise."
- "0 false accepts on 900 non-catalogue test files (95% upper bound 0.43%)."
- "Decoded real time signals from NIST, PTB, NPL and NICT blind; decoded minute agreed with receiver GPS clocks to within 1.9–23.4 ms; refused a weak WWVB time it could not prove."
- "Matched 5/5 medium-wave carriers to Prasar Bharati's official transmitter list."
- "3–4× faster with zero decision changes on 1,480 files."
- "'Decoding as a Sensor' is our research framing; the phrase was not found in the literature."
- (v2.5) Catalogue v1 capabilities may be named only after their §24 row reaches at least PARTIALLY PROVEN, and always with the catalogue scope (e.g. "CCSDS RS(255,223)", not "Reed-Solomon codes").

### 37.4 Must not say
- "Held-out 30/30" or "93% on held-out data" (sealed is contaminated; that v2.0 sentence is withdrawn).
- "AI-powered", "uses deep learning" (no ML in acceptance).
- "Decodes any signal", "universal", "guaranteed", "real-time interception", "decryption".
- "Superior to commercial systems" (go2signals, W-CODE, R&S cover hundreds of modes).
- "First of its kind", "patented", "novel algorithms".
- "Official", "Government of India system", "deployed by DoT/NTRO/WPC".
- "Live monitoring network" for the simulated station layer.
- (v2.5) "Identifies the sampling frequency" unless `fs_source = inferred` was validated; "supports LDPC/RS/QAM" without the catalogue scope; "real-world validated" without naming the signal types.

## 38. Landscape

| System | Type | Blind ID | Full decode | Licence |
|---|---|---|---|---|
| PROCITEC go2signals (go2MONITOR, go2DECODE) | Commercial | Yes (revolver principle) | Yes (hundreds of modes) | Proprietary |
| Rohde & Schwarz CA120 / CA100 | Commercial | Yes | Yes | Proprietary |
| WAVECOM W-CODE | Commercial | Yes (300+ modes) | Yes | Proprietary |
| DeepSig OmniSIG | Commercial AI | Classification | No | Proprietary |
| GNU Radio | Open toolkit | No | Partial | GPL-3.0 |
| Universal Radio Hacker | Open tool | Partial, analyst-driven | No | GPL-3.0 (archived Mar 2026) |
| gr-satellites | Open decoders | No | Known satellites | GPL-3.0 |
| liquid-dsp / AFF3CT / scikit-dsp-comm / Sionna | Libraries | No | Primitives / FEC / teaching / GPU simulation | MIT / MIT / BSD-2 / Apache-2.0 |

India context: the Wireless Monitoring Organisation (DoT/WPC) runs monitoring stations nationwide; DLRL (DRDO, Hyderabad) works in COMINT/ELINT. No public Indian tool of this kind was found.
**Differentiation is not breadth.** It is error-controlled acceptance, measured refusal, real-world verification, auditability and air-gap simplicity.

## 39. Security, Ethics and Authorised Use

- Data sources: project-generated synthetic sets; public, lawfully receivable broadcast/standard-time/weather transmissions via public listen-only receivers; captures with explicit authorisation.
- No decryption, no interception of private communications, no targeting of individuals.
- Public receivers are used politely (one session at a time, short captures).
- Identity in the prototype stays in the browser; a real deployment replaces Google sign-in with the organisation's on-premises identity provider and verifies tokens server-side.
- No secrets in the repository (`.env.local` is ignored; `VITE_GOOGLE_CLIENT_ID` documented in `.env.example`).

## 40. India-First Framing

Possible application areas (**not deployment claims**): spectrum monitoring and interference analysis, verification of licensed/broadcast transmitters against official lists, disaster communications, telecom diagnostics, authorised defence research. The Field / Regional / National views model how evidence could flow from monitoring stations to regional and national analysts without moving raw spectrum.

## 41. Risk Register

| Risk | Consequence | Response |
|---|---|---|
| PM floor does not transfer to real channels | False accepts in the field | Recalibrate on bench-v2 channels; keep sign test as primary |
| bench-v1 overfitting perception | Credibility loss | Always call sealed a tripwire; lead with null set + real signals |
| Real-signal availability during a demo | Live demo fails | Offline replays from the same processor; committed recordings |
| Public receiver changes/outages | Live sessions fail | Ranked fallback receivers; redirect handling |
| Simulated layer mistaken for real | Honesty breach | Mandatory labels; disclaimer |
| Low-Es/N0 recall judged weak | "It refuses too much" | Show refusal as correct behaviour; Es/N0 waterfall; roadmap |
| Web tier exposed on LAN | Unauthenticated API | Localhost default; server-side auth before any deployment |
| Brand misread as official | Legal/ethical issue | No emblems, disclaimer everywhere |
| Low memory on demo machine | Server killed | Close other apps; run built console only |
| Scope creep (features over evidence) | Unproven claims | §6.4, §9.11, change control §46 |

## 42. Open Questions

1. Sampling-rate and format semantics of NTRO's own evaluation data.
2. Does PM calibration hold under fading and phase noise?
3. Minimum Es/N0 per code and block length for a decode at α = 0.01 (bench-v2 waterfall).
4. Frame sync approach that preserves error control.
5. Per-receiver delay calibration for GPS agreement.
6. SAGE-Lite convergence radius once unblocked.
7. Can ML prioritise the hypothesis search without touching acceptance?

## 43. Rejected and Retired

| Item | Status | Reason |
|---|---|---|
| Consistency ≥ 0.98 acceptance, 0.12 coded bonus | RETIRED | Noise reaches 1.00; no known null |
| sps=6 forcing, dataset sps/β lists | REMOVED | Leakage |
| Arbitrary blind LDPC / pseudo-random interleavers | REJECTED | Rank collapse at realistic BER |
| CNN/ResNet acceptance | REJECTED | No per-decision error control |
| Full 2-D SCF on CPU | REJECTED for now | Cost |
| NVIDIA Sionna integration | REJECTED | GPU dependency |
| Local SDR hardware for MVP | SUPERSEDED | Public receivers |
| Name "THADAM" | REJECTED | Team decision |

## 44. Version History

| Version | Date | Summary |
|---|---|---|
| 1.0 | 2026-09-11 | Initial constitution (Gemini audit) |
| 2.0 | 2026-09-16 | Research-verified: references checked, literature gap, competitors |
| 2.1 | 2026-09-16 | Code-verified: 30/30 sealed, truncated codeword, v2.0 failures do not reproduce |
| 2.2 | 2026-09-16 | Evidence-first hardening: leakage removed, sign test + Bonferroni, null set, oracle ladder, 63/100 train |
| 2.3 | 2026-09-17 | Structural acceptance (0/900), real government transmissions, live monitor, 3–4× faster |
| 2.4 | 2026-09-17 | Consolidated single source of truth; ICHNOVA brand; console, themes and UX rules; claims corrected; plan documents marked historical |
| 2.5 | 2026-09-17 | **SIH-readiness amendment: catalogue v1 (§12.1), weighted acceptance families (§13.1), bench-v2 sealed policy (§18.1), fs provenance (§10), P0 re-prioritisation (§35), cloud clause (§9.2); audit conflicts C1–C9 resolved** |
| **2.5.2** | **2026-09-18** | **Console design system (§29.1): fixed type scale, one interaction vocabulary, elevation and motion discipline, themed browser surfaces, complete component states, no decorative kicker labels. Detector added to the quality gates (§32). Pages, routes, copy, provenance labels and disclaimers unchanged** |
| **2.5.1** | **2026-09-18** | **Status amendment (no rule, weight or catalogue change): §24 rows 33, 35, 36, 36b move from LOCKED to IMPLEMENTED with measured evidence as families F1–F4 entered the engine; row 34 (8PSK/16-QAM) becomes EXPERIMENTAL and off by default, with the measured cost of enabling it; §12.1 marks the higher modulations as not in the default path** |
| **2.5.4** | **2026-09-20** | **Deployment amendment. §9.12: one writer per results directory — the ledger and outbox fork if two processes share one, so an OS lock makes the unsafe configuration impossible rather than merely documented, and `deploy.replicas: 1` is pinned. §9.13: a reachable source is not a fresh one; health reports what was actually received. §25.8 limitation 8 records the TLS reverse proxy as CONFIGURED and never exercised, and container base-image CVEs as NOT ESTABLISHED; limitation 8a records rate limiting and revocation as in-process and in-memory by design. No rule, weight, catalogue item or acceptance threshold changed** |
| **2.5.3** | **2026-09-19** | **Platform amendment. §25.8: the API is authenticated (scrypt passwords, signed session tokens with expiry and revocation, per-endpoint role permissions, rate limiting), so the "unauthenticated API" limitation is retired and only the missing TLS remains. §9.2: the Salesforce case hand-off is approved as the one permitted cloud integration, bound by the clause it was written under. Capture quality (`src/quality.py`), evidence sufficiency (`src/sufficiency.py`), evidence receipts (`src/receipt.py`) and the signal-source registry (`server/sources.py`) are recorded, each reported separately from the decode verdict. §24 row 34 re-measured over the full null set: the cost of enabling 8PSK/16-QAM is a wrong decode from a structural alias, not the false accepts previously feared. No rule, weight, catalogue item or acceptance threshold changed** |

Details: `SIH26147_CONSTITUTION_CHANGELOG.md`.

## 45. Doctrine

> **Do not guess when structure can provide evidence.**
> **Do not claim what has not been measured.**
> **Do not add complexity before proving necessity.**
> **Do not discard a working baseline without comparison.**
> **Do not confuse research literature with project results.**
> **Do not show a number without saying where it came from.**
> **When evidence is insufficient, UNKNOWN is a valid answer.**

The system succeeds not when it produces an answer, but when it can show why that answer is consistent with the observed signal — and when it can show why it refused.

## 46. Change Control

1. Any change to behaviour, evidence, claims, brand or product structure updates this document **in the same pull request**.
2. Amendments bump the version (minor for additions/corrections, major for a change of thesis or scope), add a §44 row and a changelog entry.
3. `SIH26147_CURRENT_STATE.md`, READMEs and UI copy are then brought into agreement.
4. New capabilities enter §24 as LOCKED/FUTURE and move up only with committed evidence.

---

**ICHNOVA · SIH26147 PROJECT CONSTITUTION v2.5.1 — COMPLETE**
