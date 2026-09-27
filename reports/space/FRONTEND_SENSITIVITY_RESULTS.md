# FRONTEND_SENSITIVITY_RESULTS
**ICHNOVA · SIH26147 — `SPACE-FRONTEND-SENSITIVITY-01`: which published front-end gate moves when the carrier correction changes?**
**Status: EXECUTED AND PUBLISHED AS-IS (2026-09-26). Read-only, published diagnostics only. No production file changed, no estimator change, no threshold touched, no new dataset, no new correction grid.**

> **Headline. MEASURED FACT.** The published diagnostics **are sufficient** — no `src/` change was needed — and they localise **two different gates for two different phenomena.**
> **On the idle carrier:** CFO detection is strongly significant with or without correction (log₁₀p −141.5 at 0 front ends), the candidate front-end pool is **invariant at 396**, and the only field that moves is **how many candidates the serial-independence check rejects**: 396 rejected / 0 surviving → 378 / **18**. F4's hypothesis count follows exactly (0 → 2048), and the false accept appears.
> **On the modulated captures:** the field that moves is the **`sps_candidates` list**. The decisive case is `k3_120_008`, where the front-end count is **identical (24)** under both conditions, the sps list changes from `[13, 19, 6, 3, 2]` to `[13, 7, 4, 2]`, and the verdict flips from a correct decode to a refusal.

**Labels:** **MEASURED FACT** (read off this run) · **ENGINEERING HYPOTHESIS** (inference beyond it).

---

## Objective

Which existing front-end construction gate(s) change when the same IQ capture is subjected to different carrier corrections, and which change is associated with the appearance or disappearance of the downstream F4 hypothesis? **Localise the mechanism — not fix it, not optimise it, not choose a threshold.**

## Pre-registration and reuse

`eval/frontend_sensitivity_criteria.json`, committed before any gate value was extracted. The correction grid, the primary capture and the secondary selection are **imported** from `eval/carrier_est_diag.py` — the same five shapes, the same seven multipliers, the same zero control, the same deterministic secondary rule. **No new magnitude, shape or capture was introduced.** The estimator is imported from `eval/space_doppler_mech.py`. 88 analyses: 38 primary + 50 secondary. Determinism: two independent runs gave **88/88 rows identical** on every field except runtime.

Only fields the engine already publishes were recorded: `cfo_candidates`, `detection_log10_p`, `sps_table`, `sps_candidates`, `raw_sps_estimate`, `modulation_gates`, `modulation_stats`, `n_front_ends`, `phase_tracked_front_ends`, `front_ends_rejected_serial_dependence`, and the F4 fields. **No new metric was invented, and no unexposed internal was needed.**

## The descriptive chain — primary capture (`idle_carrier_0411`)

Presentation order, not a causal claim: only the correction was manipulated.

```
corrected IQ → CFO candidates / detection → sps candidates → modulation gates
             → front-end count → F4 hypothesis count M → F4 acceptance
```

| Condition | CFO cands | detection log₁₀p | sps rows | sps candidates | **rejected / surviving** | M(F4) | F4 margin |
|---|---:|---:|---:|---|---:|---:|---:|
| A original | 6 | **−141.50** | 19 | `[20,10,5,4,2,…]` | **396 / 0** | 0 | +2.699 |
| B zero correction | 6 | −141.50 | 19 | `[20,10,5,4,2,…]` | 396 / 0 | 0 | +2.699 |
| C estimator exact | 6 | −140.14 | 19 | `[20,10,5,4,2,…]` | **378 / 18** | 2048 | **−0.112 ACCEPT** |
| `constant` m=0.5 | 6 | −147.36 | 19 | `[20,10,5,4,2,…]` | 396 / 0 | 0 | +2.699 |
| `constant` m=1.0 | 6 | −150.47 | 19 | `[20,10,5,4,2,…]` | **378 / 18** | 2048 | +2.299 |
| `pass_mean` m=0.01 | 6 | −47.99 | 19 | `[20,10,5,4,2,…]` | **378 / 18** | 2048 | **−1.050 ACCEPT** |
| `varying_only` m=0.5 | 6 | −143.04 | 19 | `[20,10,5,4,2,…]` | 396 / 0 | 0 | +2.699 |
| `varying_only` m=1.0 | 6 | −139.75 | 19 | `[20,10,5,4,2,…]` | **378 / 18** | 2048 | **−0.112 ACCEPT** |
| `linear_mean` m=0.3 | 6 | −1.76 | 19 | `[20,10,5,4,2,…]` | **366 / 30** | 3072 | +2.634 |
| `linear_mean` m=1.0 | 6 | −0.48 | 19 | `[18,9,6,3,2,…]` | 396 / 0 | 0 | +2.699 |

Full 38-cell table: `python eval/frontend_sensitivity.py report`; raw rows in `results/frontend_sensitivity_rows.jsonl`.

### Which gates do NOT move

**MEASURED FACT.** Across all 38 primary cells: **CFO candidate count is 6 in every single condition**; `sps_table` has **19 rows in every condition**; `raw_sps_estimate` is constant; both modulation gates (`8PSK`, `16QAM`) report `searched: false` everywhere; and the modulation decision is `BPSK` for every candidate in every condition. **Detection is not the gate either** — the untouched capture is significant at log₁₀p **−141.50** and still builds **0 front ends**, while `linear_mean` m=1.0 has essentially no detection (−0.48) and also builds 0.

A caution on method: `detection_log10_p`, `best_cfo_log10p`, `best_q4` and `best_q2` are continuous values that differ in every cell, so a naive set-disjointness test calls them "separating" when it is only telling us they are noisy. They are reported, and they are **not** treated as the gate.

### The gate that does move

**MEASURED FACT.** `front_ends_rejected_serial_dependence + n_front_ends` is **396 in 34 of the 38 cells** (288 and 324 in the four largest-magnitude cells, where the sps list itself changed). The candidate pool is therefore essentially fixed, and the whole variation is in **how many candidates survive the serial-independence check**: 396/0, 386/10, 378/18, 366/30, 304/20, 270/18.

**MEASURED FACT — F4's appearance tracks it exactly.** In **38 of 38** cells, `M(F4) > 0` if and only if `n_front_ends > 0`. Every acceptance (`pass_mean` 0.01, `estimator_scaled` 1.0, `varying_only` 1.0) occurred in a cell with 18 survivors and M(F4) = 2048, and each published `ccsds_tc_ldpc_128_64` / QPSK with **0 of 18 codewords converged**.

**MEASURED FACT — two independent routes to the same gate.** (i) `constant` m=1.0 moves the strongest CFO line from +0.005840 to +0.000001 — removing the real offset — and 18 candidates survive. (ii) `varying_only` m=1.0 leaves the line where it was (+0.005841, unchanged to five digits) and **still** frees exactly 18. So neither "the carrier was moved" nor "a trajectory was invented" is individually necessary: both routes reduce serial-dependence rejections by the same 18.

## Secondary captures — a different gate

| Group / capture | A original | C estimator exact | What moved |
|---|---|---|---|
| **G1** `test_008` | 76 fronts, sps `[6,3,2,20,10,…]`, **TP** | 77 fronts, same sps, **FN** | front count +1, sps unchanged |
| **G1** `test_009` | 77 fronts, sps `[6,3,2,16,8,…]`, **TP** | 61 fronts, sps `[6,3,2,18,9,…]`, **FN** | **sps candidates changed** |
| **G2** `burst_BPSK_k3_block_0041` | 85 fronts, sps `[8,4,2,20,10,…]`, **TP** | 108 fronts, sps `[11,8,4,2,18,…]`, **FN** | **a new head candidate (11) entered** |
| **G2** `burst_BPSK_k3_diag_0046` | 59 fronts, sps `[14,7,2,13,6,…]`, **TP** | 48 fronts, sps `[14,7,2,13,1,…]`, **FN** | **sps tail changed** |
| **G3** `k3_120_005` | 51 fronts, sps `[12,6,4,3,2,…]`, **TP** | 69 fronts, sps `[19,12,6,4,3,…]`, **FN** | **a new head candidate (19) entered** |
| **G3** `k3_120_008` | **24** fronts, sps `[13,19,6,3,2]`, **TP** | **24** fronts, sps `[13,7,4,2]`, **FN** | **sps list only — front count identical** |
| **G4** `static_0000` | 60 fronts, sps `[8,4,2,12,6,…]`, correct | **60 fronts, identical sps**, correct | **nothing** |
| **G4** `static_0001` | 38 fronts, sps `[8,4,2,15,5,…]`, correct | **38 fronts, identical sps**, correct | **nothing** |
| **G5** `linear_0096` | 36 fronts, sps `[8,4,2,7,3]`, **wrong payload** | 61 fronts, sps `[8,4,2,7,18,…]`, **correct payload** | **sps candidates changed** |
| **G5** `linear_0100` | 55 fronts, sps `[15,5,3,8,4,…]`, **wrong payload** | 43 fronts, sps `[15,5,3,8,4,…]`, **correct payload** | front count −12 |

**MEASURED FACTS:**

1. **`k3_120_008` is decisive.** The front-end **count is identical (24)** under both conditions, the **sps candidate list changes**, and the verdict flips from a correct decode to a refusal. So on modulated captures the operative published field is the **symbol-rate candidate set**, not merely how many front ends survive.
2. **G4 is a perfect negative control.** On the two static captures that SPACE-CARRIER-EST-01 handled correctly under both arms, the sps list and the front-end count are **identical in all five conditions**, and so is the outcome. Where nothing upstream moves, nothing downstream moves.
3. **The same gate moves in both directions.** In G5 the sps list changes and a wrong payload becomes a **correct** one; in G1/G2/G3 it changes and a correct decode becomes a **refusal**. One mechanism, opposite consequences — consistent with the previous diagnostic's finding that benefit and harm arrive together at full correction magnitude.
4. **The zero control is identical to the original in all ten secondary captures** (and on the primary), on every recorded field. The correction machinery remains transparent.

## Answer to the question

**MEASURED FACT — the gate(s) localised, per phenomenon:**

| Phenomenon | Published gate that moves | Association with the F4 hypothesis |
|---|---|---|
| Idle-carrier false accept | **`front_ends_rejected_serial_dependence`** — the candidate pool stays at 396 while survivors go 0 → 18 | **Exact**: M(F4) 0 ↔ 2048 in 38/38 cells, and every accept sits in a surviving-front-end cell |
| Static recall loss, and the drift-recovery gain | **`sps_candidates`** (the symbol-rate candidate set), with the front-end count usually following — but not always: `k3_120_008` flips with the count unchanged | Indirect: these captures are decided by F1/F2, not F4; F4 never accepted on any secondary capture |
| Unaffected captures | **nothing moves** (G4: identical sps list, identical front count) | none |

**Gates ruled out as the discriminator (MEASURED FACT):** CFO candidate count (6 everywhere), detection significance (−141.5 with zero front ends), `sps_table` row count (19 everywhere), `raw_sps_estimate`, and both modulation gates (never searched, BPSK decided everywhere).

**ENGINEERING HYPOTHESIS (labelled, not established).** The serial-independence check and the symbol-rate candidate ranking both consume statistics of the *corrected* sample stream, so a correction that changes those statistics changes which front ends are admitted and which symbol rates are ranked — and the structural search then runs on a different hypothesis set. This experiment shows the *association* in published values; it does not show the internal computation, and the previous diagnostic's leading explanation ("pre-correction preempts the engine's own carrier inference") remains a hypothesis.

## Limitations

1. **Eleven captures.** One primary plus ten pre-declared secondary. Association, not incidence.
2. **Association, not causation-within-the-chain.** Only the correction was manipulated; the intermediate gates were observed, not set. Nothing here proves the serial-dependence check *causes* the F4 appearance rather than sharing a common upstream cause.
3. **Non-monotonic throughout**, as in the previous diagnostic: survivors flip 0 ↔ 30 with no ordering in correction magnitude. No threshold is derivable and none is proposed.
4. **The 396/288/324 pool difference** in four cells means the pool is not perfectly invariant; those cells also changed their sps list, so two gates move at once there and cannot be separated.
5. **F4 never accepted on any secondary capture**, so the F4-specific localisation rests on the single idle-carrier capture.
6. **No engine internals were read**, by design. The published fields happened to be sufficient to localise the gates; they are not sufficient to explain them.

## Conclusion

**The published diagnostics were sufficient: no production change was required, and none was made.** The mechanism is localised to **two existing gates** — the **serial-independence rejection of candidate front ends** (which alone explains the idle-carrier false accept, with M(F4) tracking it in 38/38 cells) and the **symbol-rate candidate set** (which explains the modulated-capture flips, decisively in `k3_120_008` where the front count did not change at all). Detection, CFO candidate count, sps-table size and the modulation gates are ruled out as discriminators.

**What is not established:** why these two gates are so sensitive to a correction, and whether either *causes* the other. That remains an **ENGINEERING HYPOTHESIS**.

**What is unchanged:** `SPACE-CARRIER-EST-01` remains **INTEGRATION NOT SUPPORTED**; no threshold, bar or estimator parameter was altered; no remediation was designed or proposed; `SPACE_CLAIM_FIREWALL.md` §2a stands, and time-varying-carrier payload reliability remains a **measured limitation** of the shipped engine.

## Reproduction

```bash
cd C:/Users/WVF-D/Downloads/SIH26147/repo
python eval/frontend_sensitivity.py demo
python -m pytest tests/test_frontend_sensitivity.py -q
python eval/frontend_sensitivity.py primary      # 38 conditions, imported grid
python eval/frontend_sensitivity.py secondary    # the same 5 groups x 2 captures x 5 conditions
python eval/frontend_sensitivity.py report
```

**END OF FRONTEND SENSITIVITY RESULTS**
