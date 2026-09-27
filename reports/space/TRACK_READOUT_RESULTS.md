# TRACK_READOUT_RESULTS

**ICHNOVA · SIH26147 — `SPACE-TRACK-READOUT-01`: what does the shipped `_track_phase` estimate on a time-varying carrier?**

**Status: EXECUTED (2026-09-27). First approved production instrumentation change: one optional write-only `_trace` parameter. Verdicts verified unchanged; read-out verified deterministic.**

> **Headline — MEASURED FACT.** The tracker's unwrap **does** slip, exactly as the code implies, and the slip is **perfectly separating** among the claims it produced: of the 35 time-varying captures whose published claim came from a tracked front end, **all 24 that slipped produced a wrong payload and all 11 that did not produced a correct one**. But the tracker cannot be the explanation of the Doppler limitation: **30 of the 54 recorded failures came from *untracked* front ends**, and severity-for-severity the tracked front end fails **less** often than the untracked one (severity 0.25: 2/12 vs 12/12). **The tracker is a net benefit that fails hard past its own unwrap limit.**
>
> **H3: SUPPORTED as a mechanism, for at most 24 of 54 failures (44 %). REFUTED as a complete explanation of the Doppler limitation.**

**Labels:** **MEASURED FACT** · **ENGINEERING INTERPRETATION** · **HYPOTHESIS**

---

## 1. What `_track_phase` actually does

**MEASURED FACT, read off `src/pipeline.py`.** It estimates a **piecewise-constant carrier phase**, not a frequency and not a trajectory:

1. splits the symbol stream into blocks of `blk` symbols and forms `z = mean(y**M)` per block (M = 2 BPSK, 4 QPSK);
2. takes `angle(z)`, **unwraps across blocks**, divides by M;
3. de-rotates every symbol of a block by that single value;
4. returns `None` when the stream has fewer than `TRACK_MIN_SYMBOLS = 512` symbols;
5. picks `blk` from (64, 32, 16, 8) by highest coherence `mean|z| / mean|y^M|`, requiring ≥ 8 blocks.

Two consequences follow from the code alone, before any measurement:

- **It has no model of a trajectory.** It follows phase block by block; nothing extrapolates, and nothing constrains the estimate to be smooth.
- **`np.unwrap` assumes the block-to-block change is below π.** The true M-power advance per block is `2π·M·f̄·blk·sps`. Once that exceeds π the unwrap takes the wrong branch and the recovered phase acquires a step of **2π/M that persists to the end of the capture**. A constant phase step preserves structure while corrupting bits — which is the exact shape of the measured Doppler failure (wrong payload beneath a **TRUE** structural claim).

**The 512-symbol gate is on the *front end*, not the signal.** A candidate at a smaller sps has more symbols, so tracking can run on captures whose true symbol count is 412.

## 2. What was exposed, and why a production change was needed

**The change (the entire production diff):** `_track_phase(y, mod, _trace=None)`. When a dict is passed it is filled with `m_power`, the chosen `block`, `n_blocks`, `coherence`, `coherence_by_block`, `n_symbols`, **`block_angles` (before unwrap)** and **`phase` (after unwrap, ÷ M)**. Write-only; nothing reads it; no caller in `src/` passes it.

**Why it was necessary.** The returned stream is `y·exp(−j·per_symbol)`, so `per_symbol` is recoverable only **modulo 2π**. For BPSK a slip is exactly π — precisely on the re-unwrap boundary, so it is ambiguous by construction. **The pre-unwrap `block_angles` are what make a slip observable at all.** Everything else in this experiment is read-only.

**Verified safety** (`tests/test_track_readout.py`, 6 tests): the returned array is identical with and without a trace; the trace reproduces exactly what the function applied (`unwrap(block_angles)/M == phase`); the trace is deterministic; the positional two-argument signature still works; the tracker still declines short captures and reports nothing when it does; and the sealed verdict is unchanged. The harness additionally re-checked all 192 sealed statuses: **VERDICTS UNCHANGED**.

## 3. The tracker vs the known trajectory — MEASURED FACT

192 sealed Doppler captures; trajectory reconstructed with the generator's own `space_doppler.trajectory`. The tracker ran on the claim's front end in **96 of 192** (the long captures).

| trajectory | n | median max \|err\| | median final \|err\| | captures with a slip | truth predicts a slip |
|---|---:|---:|---:|---:|---:|
| zero (control) | 24 | **0.330 rad** | 0.078 | **0** | 0 |
| static (control) | 24 | **0.321 rad** | 0.140 | **0** | 0 |
| linear | 24 | **273.6 rad** | 19.6 | 18 | 17 |
| pass | 24 | **470.4 rad** | 115.1 | 19 | 19 |

**The controls are clean:** across all 48 static/zero captures the worst error is **0.643 rad** and there are **zero** slips. The tracker does what it claims on a constant carrier.

**On a moving carrier it fails catastrophically and systematically**, and the failure is the predicted one: at the capture level, "truth says the M-power advance exceeds π" agrees with "a slip was observed" in **47 of 48** time-varying captures. Slips are not single events — the observed orders include ±1, ±2 and ±3 steps within one capture.

**The error is systematic, not incidental** — it scales monotonically with severity:

| severity | n | median max \|err\| | median max true increment | total slips |
|---|---:|---:|---:|---:|
| 0.25 | 12 | 1.02 rad | 1.16 rad | 101 |
| 0.5 | 12 | 285.8 rad | 2.51 rad | 878 |
| 1.0 | 12 | 543.8 rad | 4.57 rad | 1345 |
| 2.0 | 12 | 742.9 rad | 7.87 rad | 2000 |

**The block-length adaptation is saturated.** In **96 of 96** captures the tracker chose **blk = 8**, the shortest length available — coherence falls monotonically with block length (median 0.827 at 8, 0.767 at 16, 0.670 at 32, 0.609 at 64). **ENGINEERING INTERPRETATION: the adaptive block rule is already pinned at its finest time resolution and still slips, so it has no remaining headroom against faster carriers.**

## 4. Successful vs failed time-varying captures — MEASURED FACT

Restricted to the 35 time-varying captures whose published claim was mapped to a **tracked** front end (mapping validated: **145/145** claims resolved, with cfo, sps and modulation all matching the published hypothesis):

| | slipped | did not slip |
|---|---:|---:|
| **wrong payload** (FALSE_DECODE) | **24** | 0 |
| **correct payload** (DECODED_CORRECT) | 0 | **11** |

**A perfect 35/35 separation.** Every tracked claim that slipped was wrong; every tracked claim that did not slip was right. The 11 correct ones are the low-severity captures (10 at severity 0.25, 1 at 0.5).

**But this is not the whole failure population.** Of the 54 recorded FALSE_DECODEs:

- **30 came from `static` (untracked) front ends** — the tracker's output was not used in those claims and cannot have produced them;
- **16 had no tracked front end anywhere** (`phase_tracked_front_ends == 0`);
- **29 are short captures** (412 true symbols) where the tracker never ran on the winning front end.

**And the tracker helps on net.** Severity-for-severity, claims from tracked front ends are wrong *less* often than claims from untracked ones:

| severity | tracked claim wrong | untracked claim wrong |
|---|---|---|
| 0.25 | **2 / 12** | **12 / 12** |
| 0.5 | 10 / 11 | 12 / 12 |
| 1.0 | 11 / 11 | 6 / 6 |

All 11 correct time-varying decodes in the entire sealed set came from tracked front ends.

## 5. H3 status

**H3 (unwrap slip near the M-power ambiguity): SUPPORTED as a mechanism — REFUTED as an explanation of the Doppler limitation.**

- **SUPPORTED, and now measured rather than inferred.** Slips occur; they occur where the truth says the unwrap must slip (47/48); they are absent on 48 static controls; and among tracked claims the association with a wrong payload is perfect (24/24 and 11/11). `DOPPLER_MECHANISM_RESULTS.md`'s "not directly tested" is now discharged.
- **REFUTED as the explanation.** It can account for **at most 24 of 54** failures (44 %). The remaining 30 came from untracked front ends. The pre-registered ceiling — 16 failures with no tracked front end at all — held and was in fact exceeded.

**On causality.** The severity-controlled table rules out the simplest confound: if severity alone drove failure, tracked and untracked claims would fail equally at the same severity, and they do not (2/12 vs 12/12 at severity 0.25). Within tracked claims, slip status predicts the outcome perfectly. **ENGINEERING INTERPRETATION: for those 24 captures the slip is the proximate mechanism of the wrong payload.** It remains observational — the true cause upstream is carrier motion exceeding the tracker's unwrap limit, and the slip is how that motion becomes a wrong payload. **For the other 30 failures this experiment establishes nothing; they are untracked-front-end failures and remain explained by H1 (carrier-estimation error) as previously measured.**

## 6. Does this change any engineering decision?

**No decision changes.**

- **`SPACE-CARRIER-EST-01` remains INTEGRATION NOT SUPPORTED.** Nothing here touches that evidence.
- **`SPACE-DOPPLER`'s failed headline criterion stands**, unchanged and unregenerated.
- **No remediation is proposed.** In particular this report does **not** propose changing the unwrap, the block rule, `TRACK_MIN_SYMBOLS`, or anything else. It makes the tracker observable, which is what was authorised.
- `SPACE_CLAIM_FIREWALL.md` §2a is unchanged; nothing here licenses a space capability claim.

**What it does change is the diagnosis.** The previous framing treated the tracker as a possible cause of the Doppler limitation. The measurement says the opposite: **the tracker is the only thing producing correct time-varying decodes at all**, and it fails only past a limit that is explicit in its own code.

## 7. What remains unknown

- **The 30 untracked-claim failures are not explained by this work.** They are consistent with H1 but were not tested here.
- **Why the winning front end is sometimes the untracked variant** even when a tracked one exists was not investigated; both are ranked by the same family statistics.
- **Only BPSK captures were exercised** (the sealed Doppler set is BPSK). For QPSK the ambiguity step is 2π/4, so slips should begin at half the drift rate — **untested HYPOTHESIS**.
- **The synthetic `pass` trajectory is not a real orbit**, and the whole set is synthetic data at a normalised sample rate.
- **Whether a slip is repairable** — for example whether the persistent step is detectable from the engine's own statistics — was not examined, because that would be remediation.

## 8. Are further Space experiments justified?

**Not on H3 — it is now measured as far as this evidence base allows.** The honest remaining gap is the **30 untracked-claim failures**, which are an H1 question already characterised by `SPACE-DOPPLER-MECH-01`.

One question is newly well-posed **if** the project wants it, and it is a *design* question rather than an experiment: the tracker's unwrap limit (`|2π·M·f̄·blk·sps| < π`) is an explicit, computable bound, and the engine currently does not know when it has crossed it. Whether that bound should be **observable in the engine's own diagnostics** — not corrected, just reported — is a decision for the next authorisation, not something this experiment recommends.

## Method note

`eval/track_readout.py`, criteria `eval/track_readout_criteria.json` (sha256 `fef76449e18ca9c5…`). Reproduce with `python eval/track_readout.py run` then `report`; two consecutive runs produced **byte-identical** row files. Evidence: `results/track_readout_rows.jsonl` (192), `results/track_readout_blocks.jsonl` (14,496 per-block samples). Production diff: `src/pipeline.py`, 17 insertions, 2 deletions, confined to `_track_phase`. Full suite **239 passed**. Sealed datasets re-verified byte-identical (192/192, 144/144, 288/288); no prior rows, manifests, criteria or reports were altered.

**END OF TRACK READOUT RESULTS**
