# DOPPLER_FAILURE_ANALYSIS
**ICHNOVA · SIH26147 — analysis of the SPACE-DOPPLER failure**
**Status: ANALYSIS (2026-09-25). The experiment is sealed; this document interprets it and changes nothing.**

Source of every number: `reports/space/DOPPLER_EXPERIMENT_RESULTS.md`, `results/space_doppler_rows.jsonl` (192 rows), and the post-hoc diagnostic in `results/space_doppler_diagnostic_scores.jsonl` (§4.1 — clearly marked, not pre-registered). No threshold, engine constant or production file was touched to produce this analysis.

**Two labels are used throughout and never mixed:**
- **MEASURED FACT** — read directly off the sealed run or the code.
- **ENGINEERING HYPOTHESIS** — a candidate explanation the experiment *did not test*.

**ROOT CAUSE NOT ESTABLISHED.** The failure is reproduced, bounded, and localised to one layer. The mechanism inside that layer is not proven. Six candidates are listed in §7; the experiment that discriminates them is designed in `DOPPLER_REMEDIATION_EXPERIMENT.md`.

---

## 1. What failed?

**MEASURED FACT.** Under a carrier whose frequency changes during the capture, the engine issued a `DECODED` verdict carrying a **payload that is not the transmitted payload**, in **54 of 96 treated captures (56.3%)**:

| Trajectory | n | decoded correctly | refused | **wrong payload under DECODED** | BER range of the wrong payloads |
|---|---:|---:|---:|---:|---|
| `linear` (−peak → +peak ramp) | 48 | 6 | 15 | **27** | 0.027 – 0.490 |
| `pass` (bounded arctan S-curve) | 48 | 5 | 16 | **27** | 0.212 – 0.495 |

Median wrong-payload BER **0.320** — the bits are not slightly corrupted, they are mostly unusable. Nothing in the verdict said so.

**MEASURED FACT.** Noise is not the driver: wrong payloads are flat across SNR — 18 at Es/N0 12 dB, 17 at 9 dB, 19 at 6 dB.

**MEASURED FACT.** Severity is not monotonic in the way a simple "harder ⇒ worse" story predicts. Wrong payloads peak in the *middle* of the sweep (`linear`: 7 at severity 0.25, 11 at 0.5, 8 at 1.0, 1 at 2.0; `pass`: 7 / 11 / 9 / 0). At severity 2.0 the peak offset lies outside the engine's declared search bound `CFO_MAX = 0.0125` and the engine **refuses** (35 of 48 severity-2.0 captures refused). The dangerous region is therefore **inside** the bound the engine claims to handle, not beyond it.

## 2. What did NOT fail?

Each of these is a **MEASURED FACT** from the same 192 captures, and none is weakened by §1:

| Held | Evidence |
|---|---|
| **The structural claim** | **0 wrong structures in 192 captures.** All 145 `DECODED` verdicts named the true code family (`conv_k7_r12_171_133_continuous`); `code_consistency` 145/192, the remaining 47 being refusals, not wrong claims |
| **Modulation inference** | **0 of 145** `DECODED` verdicts carried a wrong modulation |
| **The static-carrier case** | **0 wrong payloads in 96 control captures** — `zero` 48/48 correct; `static` 32 correct + 16 refusals, every refusal a severity-2.0 cell outside `CFO_MAX`, which is the pre-registered expected-refusal condition |
| **Out-of-bound refusal discipline** | 35 of 48 severity-2.0 captures refused; the engine does not pretend to search past its declared bound |
| **Symbol-rate inference** | true sps present in the candidate list on **180/192**; the accepted front end used the true sps on **146/192** |
| **Runtime** | mean **1.35 s**, max **3.02 s** — a moving carrier does not send the hypothesis search pathological (bar was mean ≤ 7.14 s) |
| **Determinism** | **192/192** files byte-identical on regeneration |
| **Every pre-existing result** | 185 tests pass (178 before + 7 additive, none changed outcome); bench-v1 sealed **30/30, 0 false accepts**; bench-v2 untouched |

**The honest summary of §1 + §2:** this is **not** a hallucinated-structure failure. It is a **payload-reliability** failure underneath a structurally correct claim. The distinction matters technically — it points at one layer instead of the whole chain — and it matters for honesty: the failure is narrower than "the engine lies about structure", and wider than "a few bits were noisy".

> **Wording note.** Summarising this result as "54/96 **false structural claims**" overstates it, in the *unfavourable* direction. The structural claims were correct in all 192 captures. The accurate phrase, used throughout this package, is **"a wrong payload published beneath a true structural claim"**. Precision here is not softening — it is what makes the failure diagnosable.

## 3. Where in the inference chain does the failure appear?

The chain, with the measured state of each stage (**MEASURED FACT** unless tagged):

```
IQ capture
  ↓  CFO candidates (x², x⁴ spectra vs exponential-periodogram null)    HELD — signal detected, log10p −22 … −30
  ↓  sps candidates (y⁴ lag-1 correlation + integer divisors)           HELD — true sps in candidates 180/192
  ↓  front ends: ONE CONSTANT CFO removed per front end,                ← the trajectory is not constant
       matched filter, M-power phase, M2M4-calibrated LLRs,
       optional block phase tracking above TRACK_MIN_SYMBOLS = 512
  ↓  F2 syndrome sign test over the continuous stream                   HELD, EMPHATICALLY — accepted at
       (blind_id / stream.scan)                                            log10p −14.8 … −29.7 vs bars ≈ −5
  ↓  F2 guards: agreement floor 0.61, decoy-code control,               DID NOT FIRE on any of the 54
       degenerate-stream rule
  ↓  Viterbi decode of the accepted hypothesis (stream.decode)          ← THE FAILURE SURFACES HERE
  ↓  verdict assembly: payload published with the verdict               ← AND IS NOT FLAGGED HERE
```

**MEASURED FACT.** The failure is localised **at and after the Viterbi/payload stage of an already-accepted, correct structural hypothesis** — not in detection, not in modulation or symbol-rate inference, not in code identification, and not in the family-wise error control, which accepted nothing that was not there.

**MEASURED FACT (from `src/stream.py`, `src/pipeline.py`).** The F2 acceptance rule is the syndrome sign test plus three guards: `F2_AGREEMENT_FLOOR = 0.61` on check agreement, a decoy-tap-pattern control, and the degenerate-stream rule (≥ 4 distinct bytes in the decoded information). `stream.decode` additionally computes **two payload-side scores — the soft `path_metric` and the hard re-encode `consistency` —** and uses them **only to break the polarity tie**. Neither is an accept/reject gate, and neither reaches the verdict as a reliability statement.

## 4. What evidence rules out generator, scoring and noise bugs?

| Alternative explanation | Ruled out by (**MEASURED FACT**) |
|---|---|
| **Generator bug** (the harness emits a signal the engine cannot read) | `payload_correctness_on_control_cells` = **24/24** decoded with BER < 0.01; `zero` trajectory **48/48** correct across the whole severity and SNR grid. The same generator, seeds and code path produce perfectly decodable captures whenever the carrier holds still |
| **Scoring misalignment** (a correct payload scored wrong through a bit offset or polarity) | Every wrong payload re-tested against the transmitted bits over **all offsets ±64 and both polarities**: the best achievable BER **equals** the scored BER at offset 0 in every case checked. No shift recovers the bits |
| **Scoring semantics drift** | The BER function is `bench2._ber`, **imported verbatim** from the bench-v2 runner — the same polarity-insensitive comparison that scored the 430-file sealed run |
| **Noise** | Wrong payloads are flat across Es/N0 (18 / 17 / 19 at 12 / 9 / 6 dB). A noise explanation predicts concentration at 6 dB; a 2× SNR range does the opposite here |
| **Non-determinism / flaky measurement** | **192/192** files regenerate byte-identically from seeds 500000–500191 |
| **A pre-existing engine regression** | 185 tests pass with none changed; bench-v1 sealed **30/30, 0 false accepts** on the same commit |

### 4.1 Post-hoc diagnostic (NOT pre-registered — an observation, never a result)

After the sealed run, the engine was re-run over the same 192 captures to record the payload-side scores it **already publishes** for the accepted F2 hypothesis (`results/space_doppler_diagnostic_scores.jsonl`). This is post-hoc. It was not in the criteria file; it cannot establish that any gate would work; and **no threshold may be chosen from it**.

Over the 145 `DECODED` captures (91 correct payload, 54 wrong):

| Published score (already computed today) | correct payload (min / median / max) | wrong payload (min / median / max) | overlap |
|---|---|---|---|
| `path_metric` (soft, Σ L·(1−2c)/Σ\|L\|) | 0.9983 / 0.9998 / 1.0000 | 0.8575 / 0.9099 / 0.9934 | **0 of 54** at or above the lowest correct value |
| `consistency` (hard re-encode agreement) | 0.9878 / 0.9975 / 1.0000 | 0.8512 / 0.9073 / 0.9954 | 1 of 54 |
| `agreement` (syndrome check ratio) | 0.9444 / 0.9925 / 1.0000 | 0.6249 / 0.7211 / 0.9900 | 1 of 54 |

**MEASURED FACT.** On this dataset the payload-side scores the engine already computes separate the wrong-payload population from the correct one almost completely, and `path_metric` separates it entirely.
**MEASURED FACT.** The existing `F2_AGREEMENT_FLOOR = 0.61` did not fire on any of the 54: their agreement values lie in **0.6249 – 0.9900**, entirely above that floor.
**MEASURED FACT.** The existing guards fired on 6 of 47 refusals and on **0 of 54** wrong payloads.

**ENGINEERING HYPOTHESIS (explicitly untested).** A gate on a payload-side score could convert these wrong answers into refusals. **Nothing here establishes that**, for three reasons that must always travel with the numbers: (a) separation on one code family, one modulation and 192 vectors is not a calibrated threshold; (b) choosing a cut from *this* data is exactly the tuning the Constitution forbids; (c) the cost in static-carrier recall — bench-v1, bench-v2, the real-signal suite, the null set — is entirely unmeasured. A pre-registered rule tested on a **new** dataset is the only thing that can settle it: `DOPPLER_REMEDIATION_EXPERIMENT.md`.

## 5. What does phase tracking successfully accomplish?

**MEASURED FACT (`pipeline._track_phase`).** Above `TRACK_MIN_SYMBOLS = 512` symbols the engine adds a tracked front end: it picks the block length from {64, 32, 16, 8} that maximises block coherence |mean(y^M)|/mean(|y^M|) (requiring ≥ 8 blocks), takes one M-power phase estimate per block, unwraps across blocks and de-rotates. It is not data-aided and adds no hypotheses of its own — it is one more front end, counted in every family's M.

**MEASURED FACT (why it exists).** bench-v2 calibration found 13 of 15 wrong payloads came from the `phase_noise` / `cfo_drift` / `amplitude` classes; the tracker was added in response, and the sealed bench-v2 run then passed 9/9 criteria.

**MEASURED FACT (what it bought here).** Treated trajectories only, split at the tracking threshold (the long captures are 1200 *info bits* = **2412 symbols**; an earlier draft of this table misstated them as ~1200 symbols, which changes nothing about the comparison since both lengths straddle 512 as intended):

| length | tracked front ends present | correct payload | refused | wrong payload |
|---|---|---:|---:|---:|
| long (2412 symbols, above 512) | 48/48 captures | **11** | 12 | **25** |
| short (412 symbols, below 512) | 29/48 captures | **0** | 19 | **29** |

Tracking is what makes *any* correct decode possible under a moving carrier: 11 correct above the threshold against **0** below it. That is a real, measured benefit, and the reason the failure rate is 56% rather than total.

## 6. Why is tracking insufficient?

**MEASURED FACT.** It does not convert wrong answers into refusals. Above the tracking threshold there are still **25 wrong payloads in 48 treated captures**. Tracking moved captures from the wrong column into the correct column and barely moved any into the refusal column (12 refusals long vs 19 short).

**MEASURED FACT.** The conditions tested lie far outside the drift class the tracker was ever measured against — bench-v2's `cfo_drift` uses rate ~ U(−2×10⁻⁷, +2×10⁻⁷) cyc/sample² (`bench2_gen.apply_channel`):

| cell | max drift rate (cyc/sample²) | × bench-v2's largest drift |
|---|---|---|
| `linear` severity 0.25 (mildest treated) | 3.7×10⁻⁶ | ≈ 18× |
| `pass` severity 1.0 | 3.8×10⁻⁵ | ≈ 190× |
| `pass` severity 2.0 (harshest) | 7.5×10⁻⁵ | ≈ 375× |

**INTERPRETATION (not a mechanism claim).** The tracker is a *correction*, not a *detector*: its output is a de-rotated symbol stream, and its residual error is never compared against anything or published. Nothing downstream asks "how well did tracking actually work on this capture?", so a partially corrected stream is indistinguishable, to the acceptance path, from a well-corrected one. That is a structural property of where the tracker sits — **MEASURED FACT from the code** — and it holds whichever of §7's mechanisms is operating.

## 7. Why can a structurally plausible hypothesis still produce an incorrect payload?

**MEASURED FACT — the repository anticipated this, in `src/stream.py`, `rank()`:**

> *"a front end with residual carrier offset flips polarity in segments, which still satisfies the parity check inside each segment (the catalogue generators have odd weight, so a complemented codeword is a codeword) but fails it at every boundary. Such a front end decodes to a segment-wise complemented, useless payload, and it always has a lower agreement ratio than the coherent front end."*

That is a precise description of "significant structure, useless payload", written before this experiment existed, with the reason it is *statistically legitimate*: for a code whose generators have odd weight, **the bitwise complement of a codeword is a codeword**, so a parity/syndrome sign test cannot distinguish a stream from a segment-wise complemented version of itself. The sign test is a statement about *code presence*. It is not, and never was, a statement about *payload correctness*.

**Consistency with the measurement (MEASURED FACT, not proof):** the wrong-payload population has median syndrome agreement **0.721** against **0.9925** for correct payloads, and wrong-payload BERs cluster at 0.21–0.50 with median **0.320** — the range a segment-wise polarity pattern produces. This is *consistent* with the mechanism above. It does not prove it.

**ROOT CAUSE NOT ESTABLISHED.** The candidates, each an **ENGINEERING HYPOTHESIS**, with what would confirm or kill it:

| # | Candidate mechanism | Would be confirmed by | Would be killed by |
|---|---|---|---|
| H1 | **Residual frequency error.** Each front end removes one *constant* CFO; a trajectory leaves a residual up to ±peak that no front end models | Ideal (ground-truth) carrier correction restoring correct payloads at all severities | Failures persisting under ideal correction |
| H2 | **Staircase correction error.** The tracker applies one phase per block (`np.repeat(phi, blk)`), so intra-block phase error grows with block length × drift rate | Failure rate scaling with the chosen block length; piecewise-linear correction fixing what piecewise-constant does not | No block-length dependence |
| H3 | **Unwrap slip.** When the per-block phase advance approaches the M-power ambiguity, `np.unwrap` can slip a branch — producing exactly a segment-wise polarity pattern | Slip events aligning with the wrong-payload segments (needs the blocked trajectory read-out) | Failures at drift rates far below any slip condition |
| H4 | **Soft-metric miscalibration.** LLRs are scaled by one M2M4 SNR estimate per capture; under a moving carrier the effective SNR is non-stationary, so LLRs may be over-confident and the Viterbi path over-committed | Correct payloads returning when LLRs are re-scaled per block | No sensitivity to LLR scaling |
| H5 | **Insufficient observation length.** Below `TRACK_MIN_SYMBOLS` there is no tracking at all | The short-length result (0/48 correct) — *partially supported already*, but it cannot explain the 25 long-capture failures | — (already known to be incomplete) |
| H6 | **Tracking × code-decoding interaction.** The tracker's residual is precisely the pattern the syndrome test is blind to (odd-weight complement invariance), so tracking can leave a stream that looks *more* structurally significant while decoding worse | Correct structure + wrong payload surviving ideal correction of amplitude and noise but not of *phase*; the agreement / `path_metric` separation persisting on a new dataset | Failures under conditions with no segment-wise phase structure |

H6 leads on documentary and statistical grounds. **It remains a hypothesis.** The discriminating comparison — ideal ground-truth correction vs estimated correction vs none — has not been run, and until it has, this document names no root cause.

## 8. What is the current safe operating boundary?

**MEASURED FACT, stated as the operating envelope:**

| Condition | Status |
|---|---|
| Carrier **static within the capture** (zero or constant offset inside `CFO_MAX = 0.0125` cyc/sample) | **Validated within documented benchmark scope** — 96/96 of this experiment's controls produced no wrong payload; bench-v2 430 files 9/9 criteria; bench-v1 30/30; 0/900 false accepts on the independent 1,350-file null set |
| Carrier offset **outside** `CFO_MAX` | **Refuses** — 35 of 48 severity-2.0 captures refused; behaves as declared |
| Carrier **varying within the capture**, drift rate ≳ 3.7×10⁻⁶ cyc/sample² (≈ 18× bench-v2's `cfo_drift`) | **UNSAFE FOR PAYLOAD USE.** Structure remains trustworthy; the payload does not, and the verdict does not say so. 54/96 wrong payloads |
| Drift rates **between** bench-v2's `cfo_drift` (2×10⁻⁷) and this experiment's mildest cell (3.7×10⁻⁶) | **NOT MEASURED.** The boundary in between is unmapped — the mildest treated cell is already 18× the largest previously tested rate |
| Orbital / real spacecraft Doppler | **NOT ESTABLISHED.** No orbit model and no real spacecraft capture exist in this project |

**The operational consequence, in one line:** a `DECODED` verdict from ICHNOVA may be relied on for *what the signal is*; it may be relied on for *what the signal says* only when the carrier is static within the capture.

## 9. What engineering would be required to move that boundary?

Nothing here is implemented, and none of it may start before §10's diagnostic. Each option names its cost, because the cheapest honest option is also the one most likely to be wrong in a way that matters.

| Option | What it would do | Cost / risk | Prerequisite |
|---|---|---|---|
| **A — publish a payload-reliability statement** | Carry the already-computed `path_metric` / `consistency` into the verdict and receipt as a reliability field, changing no decision | Lowest risk (read-out + presentation, no verdict change). Does not stop a wrong payload being *used* — only stops it being used *unknowingly* | The §10 diagnostic, to know what the number means |
| **B — gate the verdict on a payload-side score** | Downgrade `DECODED` → `SIGNAL_NO_CODE` (structure reported, payload withheld) when the score is below a **pre-registered** bar | Can convert currently-correct decodes into refusals. Must be measured against bench-v1 (30/30), bench-v2 (all 9 criteria), the real-signal suite (JJY/DCF77/MSF/WWV/DDH47) and the 1,350-file null set. Abandoned if it costs static-carrier recall | §10 diagnostic **and** a pre-registered criteria file **and** a new sealed dataset |
| **C — piecewise-linear phase correction** | Follow a ramp inside each block instead of a staircase | Touches front-end construction; changes every family's front-end set, hence M and every bar. Larger blast radius than B | Evidence that H2 is the operating mechanism |
| **D — per-block CFO re-estimation (drift-aware front end)** | Recover correct payloads instead of refusing | Changes hypothesis enumeration and therefore M in every family; the most invasive option here | Evidence that H1/H2 dominate, plus B already in place as the safety net |
| **E — trajectory read-out** (`_track_phase` → `diagnostics`) | Makes the drift a *measured, reportable* quantity; unblocks D1, D2, D8 of the experiment design | Low technical risk (the data exists and is discarded), but it is a production-file change and is **already awaiting explicit approval** (SPACE_IMPLEMENTATION_GATE.md §9.3) | Approval |

**Sequencing principle:** refusal before recovery. B makes the system honest under drift; D makes it capable. B is cheap to state and expensive to validate; D is expensive in both. Neither is authorised.

## 10. What experiments are needed before implementation?

**One experiment, designed in full in `reports/space/DOPPLER_REMEDIATION_EXPERIMENT.md` (experiment ID `SPACE-DOPPLER-MECH-01`) — a *diagnostic*, not a fix.** Its purpose is to identify the mechanism, not to make a benchmark pass. Its decisive comparison:

> **no carrier correction** vs **existing estimated correction** vs **ideal ground-truth carrier correction**

That single contrast splits the hypothesis space: if ideal correction restores correct payloads, the failure is *estimation* (H1/H2/H3) and the fix belongs in the front end; if it does not, the failure is *decoding under non-stationary conditions* (H4/H6) and no amount of carrier estimation will close it.

Hard conditions carried forward:
1. **New namespace, new criteria file, new experiment ID.** The 192-vector dataset, its manifest, its criteria and its result are **sealed historical evidence** — never regenerated, never re-scored, never overwritten.
2. **Criteria pre-registered before the first vector exists**, including what would falsify each hypothesis in §7.
3. **The ideal-correction arm is an evaluation-only oracle**, of the kind `eval/ladder.py` already uses, and must never be reachable from a production path.
4. **No production file changes** until the diagnostic names a mechanism. The read-out (option E) may be required to answer H3 and is the one production change justifiable on diagnostic grounds alone — separately approved, never bundled.
5. **Results published whatever they say**, including "the mechanism is still not established".

**What must NOT happen next:** tuning `F2_AGREEMENT_FLOOR` to the value that would have caught these 54 captures. It is the one change that would make the benchmark pass while leaving the engine no more trustworthy, and it would destroy this dataset's diagnostic value in the process.

**END OF DOPPLER FAILURE ANALYSIS**
