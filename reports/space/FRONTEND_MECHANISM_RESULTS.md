# FRONTEND_MECHANISM_RESULTS
**ICHNOVA · SIH26147 — `SPACE-FRONTEND-MECH-01`: why does a small IQ correction change the hypothesis search space?**
**Status: EXECUTED (2026-09-26). Read-only; production functions called, never modified. Replication verified against the engine's own published counts in 14/14 conditions.**

---

## 1. What we learned

**MEASURED FACT.** On the canonical regression capture the engine offers **six CFO candidates in every condition**. Uncorrected, all six lie near the true carrier (+0.00101 … +0.00995, clustered at +0.00584; true CFO 0.00584). After **any** correction that moves or perturbs the carrier, the weakest candidate **jumps far away** — to −0.012377 (estimator), +0.012277 (`constant` m=1), −0.006539 (`varying_only` m=1), −0.006635 (`pass_mean` m=0.01) — and **all 18 surviving front ends are built on that one far-off candidate**, at the three largest symbol rates (sps 18, 19, 20), with neighbouring-decision agreement **0.500–0.556**.

Uncorrected, **every one of the 396 candidate front ends has agreement ≥ 0.613** and is therefore rejected. So the original refusal was never "no signal": detection was significant at log₁₀p **−141.50**. It was *"every front end I can build has serially dependent decisions."*

The false accept is therefore not a failure of F4 and not an estimator error. It is the **admission of an off-carrier, noise-like front end** that the correction brought into existence, followed by a 2048-hypothesis block-code search on what is effectively noise.

## 2. The earliest meaningful divergence

**The output of `pipeline._cfo_candidates` — specifically the placement of the weakest of its six candidates.**

| Condition | CFO candidates | survivors | where survivors sit |
|---|---|---:|---|
| A original | +0.00584, +0.00587, +0.00581, +0.00101, +0.00995, +0.00724 | **0** | — |
| B zero correction | identical to A | **0** | — |
| C estimator exact | +2.6e-6, −2.7e-5, −5.1e-5, −0.00483, +0.00412, **−0.012377** | **18** | all at **−0.012377** |
| `constant` m=0.5 | +0.00292 … +0.00432 (all on-carrier) | **0** | — |
| `constant` m=1.0 | +1.3e-6, +3.1e-5, −2.9e-5, −0.00483, +0.00412, **+0.012277** | **18** | all at **+0.012277** |
| `varying_only` m=0.5 | +0.00584 … +0.00724 (all on-carrier) | **0** | — |
| `varying_only` m=1.0 | +0.00584, +0.00581, +0.00579, +0.00101, +0.00996, **−0.006539** | **18** | all at **−0.006539** |
| `pass_mean` m=0.01 | +0.00581, +0.00574, +0.00571, **−0.006635**, +0.00833, +0.00993 | **18** | all at **−0.006635** |

`CFO_MAX = 0.0125`, so −0.012377 and +0.012277 are **band-edge** candidates. **MEASURED FACT: in every surviving condition the survivor set is exactly the front ends built on the one candidate that is far from the true carrier, and in every 0-survivor condition all six candidates are near it.**

This is earlier than the serial gate and earlier than the sps ranking, and it is the earliest stage at which the conditions diverge at all — the sample statistics feeding it (`detection_log10_p`, the sps table's domain) are otherwise unchanged.

## 3. How the divergence propagates

**MEASURED FACT at each step; the arrows are the production control flow, not an inference.**

```
corrected IQ
  → x²/x⁴ spectra: the weakest of 6 CFO candidates moves off-carrier (band edge or mid-band)
  → that candidate's front ends de-rotate an on-carrier signal by a far-off frequency
     ⇒ no coherent carrier remains: hard decisions become serially INDEPENDENT
       (agreement 0.500–0.556, against 0.613–0.975 for every on-carrier candidate)
  → the serial-independence gate (SERIAL_AGREEMENT_MAX = 0.60) ADMITS exactly those 18
  → F4's hypothesis count goes 0 → 2048 (M = 0 iff no front end exists)
  → the LDPC scan tries 2048 codeword offsets against a noise stream;
     one clears the bar by 0.112 log units with 0 of 18 codewords converging
```

Median agreement by sps under A: 0.624 (sps 2) rising monotonically to **0.867** (sps 20) — the higher the sps, the more coherent the stream and the more dependent the decisions. Under the estimator correction the same curve is 0.624 → **0.831**, essentially unchanged; what changed is that a **new, off-carrier branch** appeared whose sps-18/19/20 decisions sit at 0.50.

**The gate behaved exactly as specified.** Its documented purpose is to reject front ends whose neighbouring decisions are *dependent* (oversampling repeats symbols; 2× gives ~75%). A pure-noise front end is serially *independent*, so it passes. **Nothing downstream requires a front end to carry signal energy** — that is the structural gap, and it is a design property, not an error in the gate's arithmetic.

## 4. Established vs hypothesised

**MEASURED FACT (replication verified: the eval-side recomputation reproduces the engine's published `n_front_ends` and `front_ends_rejected_serial_dependence` in 14/14 conditions):**

- **M1 — SUPPORTED.** The gate flip *is* the agreement rate crossing 0.60. In 0-survivor conditions the minimum over 396 candidates is 0.613; in surviving conditions it drops to 0.500–0.502, and the count at or below 0.60 equals the survivor count **exactly** (18 = 18) in all four surviving conditions.
- **M2 — SUPPORTED.** The sps **domain** is identical (19 entries) in every condition of every capture. On `k3_120_008` the q4 values change at 19/19 sps and the **top-3 ordering** changes (`13, 19, 6` → `13, 7, 4`), so the candidate list changes by **re-ranking**, not by domain membership: `[13,19,6,3,2]` → `[13,7,4,2]`, F4 M 80 → 2048, verdict TP → refusal, with the front-end count identical at 24.
- **M4 — SUPPORTED**, and it is the earliest divergence (§2).
- **M3 — REFUTED as stated.** The two gates are **dissociable**: on the primary capture the sps candidate list is **identical** in all eight conditions while the serial survivors flip 0 ↔ 18; on `k3_120_008` the front-end count is **identical** while the sps list flips. They are not one quantity. They *are* both consequences of one **input** change — the corrected stream's second/fourth-order statistics — but they are two independent routes from that input to the search space.
- **Negative control.** `static_0000` has almost no CFO to remove (estimator mean 4.9×10⁻⁴); its CFO list barely moves, its q4 top-3 ordering is unchanged, its sps list and front count are identical (60/120) under all three conditions, and its verdict is unchanged. **Where the correction is small, nothing propagates.**

**ENGINEERING INTERPRETATION (not established).** Why a correction relocates the weakest spectral candidate is not proven here. The plausible account — that removing the carrier lowers the x²/x⁴ peak so the third-ranked peak of each order is drawn from the noise floor, where its position is arbitrary — is consistent with the recorded `peak_to_floor_db` values but was not tested by manipulating the peak structure directly.

**UNRESOLVED.** Whether this generalises beyond these three captures; how often an off-carrier front end passes the gate on *catalogue* signals (here it happened on an idle carrier at Es/N0 3 dB with Rician fading); and whether the sps re-ranking route has its own distinct trigger.

## 5. What this means for the safety of carrier correction

**MEASURED FACT.** Any pre-correction — including one that is physically correct — perturbs the second- and fourth-order spectra that seed both the CFO candidate list and the sps ranking. Both seeds feed candidate *generation*, not just candidate *ordering*, so the hypothesis space itself changes, and with it every family's multiplicity and bar.

**ENGINEERING INTERPRETATION.** This is why `SPACE-CARRIER-EST-01` could not be integrated: the estimator's benefit (a coherent front end where the engine had only incoherent ones) and its harm (an off-carrier front end admitted on a structureless capture; a re-ranked sps list losing a real decode) are **the same operation seen from two sides**. Reducing the correction's magnitude reduces both together — measured at m = 0.1, where neither the benefit nor the harm appears.

**The structural observation, offered as the engineering-relevant one:** the pipeline has no requirement that an admitted front end carry signal energy. Serial independence is necessary for the syndrome null to be valid, but it is not sufficient for the front end to be *meaningful* — and noise satisfies it perfectly. **No change is proposed here.**

## 6. Is another experiment scientifically justified?

**Not on this question.** The chain from correction to false accept is now measured end to end at every branch the production code takes, with the replication verified against the engine's own published counts. A further experiment would add captures, not understanding.

One question *is* newly well-posed and would be worth its own pre-registration **if** the project wants it: **how often does the shipped engine admit an off-carrier, noise-like front end without any correction at all?** The band-edge candidate is produced by `_cfo_candidates` on every capture; here it was on-carrier only because the carrier was strong. That is a property of the shipped engine, testable read-only on existing sealed data, and it bears directly on the F4 margin question `SPACE-F4-MARGIN-01` left PARTIALLY RESOLVED.

## 7. / 8. What should be frozen

**Freeze as the engineering conclusion:**

1. A carrier pre-correction changes ICHNOVA's hypothesis search space because it changes the **CFO candidate set** and the **sps ranking**, both computed from the corrected samples and both driving candidate **generation**.
2. The canonical false accept is fully explained: an off-carrier band-edge candidate → noise-like decisions → the serial-independence gate admits (per its own valid specification) → F4 M 0 → 2048 → a 0.112-log coincidence with 0/18 codewords converged.
3. The recall losses are explained by the second route: q4 re-ranking changes sps candidate membership, which changes the searched streams even when the front-end count does not move.
4. **`SPACE-CARRIER-EST-01` stays INTEGRATION NOT SUPPORTED.** The mechanism makes clear this is not a tuning problem: the benefit and the harm are one operation.
5. Nothing here licenses any space capability claim, and `SPACE_CLAIM_FIREWALL.md` §2a is unchanged.

## Method note

`eval/frontend_mechanism.py` **calls** `pipeline._cfo_candidates`, `_sps_table`, `_sps_candidates`, `_track_phase`, `analyze.matched_filter_demod / estimate_carrier_phase / estimate_symbol_rate / symbol_snr_m2m4 / psk_llrs / lag1_correlation`, `modem.rrc_filter`, and imports the production constants (`SERIAL_AGREEMENT_MAX`, `ALPHA`, `RX_BETA`, `SPS_RANGE`, `MIN_SYMBOLS`, `MODULATIONS`). It recomputes the gate arithmetic the production loop performs. **No production file was modified.** The replication is trusted only because it reproduces the engine's published `n_front_ends` and `front_ends_rejected_serial_dependence` exactly in **14 of 14** conditions; had it not, the criteria required reporting the analysis as UNVERIFIED.

Evidence: `results/frontend_mechanism_rows.jsonl` (14 conditions), `results/frontend_mechanism_fronts.jsonl` (3,876 candidate front ends). Reproduce with `python eval/frontend_mechanism.py run` then `report`.

**END OF FRONTEND MECHANISM RESULTS**
