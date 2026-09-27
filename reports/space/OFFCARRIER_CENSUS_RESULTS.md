# OFFCARRIER_CENSUS_RESULTS

**ICHNOVA · SIH26147 — `SPACE-OFFCARRIER-CENSUS-01`: how often does the SHIPPED engine admit an off-carrier, noise-like front end with NO carrier correction at all?**

**Status: EXECUTED (2026-09-27). Read-only census of 1,810 sealed captures with the unmodified engine. No correction, no ablation, no oracle, no production change.**

> **Headline — MEASURED FACT.** Off-carrier front ends are **not rare and not exotic**: the shipped engine admits at least one on **373 of 1,300** signal-bearing captures (**28.7 %**), and **9,186 of 115,057** admitted front ends (8.0 %) are off-carrier, 59 % of them noise-like. **None of them has ever produced a claim.** All **256** published claims came from an on-carrier (255) or near-carrier (1) front end; **zero** off-carrier. All **34** F4 acceptances came from an on-carrier front end, all correct, none with zero convergence. **T4 = T5 = 0 of 1,300** (Wilson 95 % upper bound **0.0029**).
>
> **Verdict, by the pre-registered rule: LATENT — NOT REALIZED.** The mechanism occurs routinely in the shipped engine and is **not** consummated.

**Labels:** **MEASURED FACT** · **ENGINEERING INTERPRETATION** · **UNRESOLVED QUESTION**

---

## 0. A pre-registration error, declared before the results

`eval/offcarrier_census_criteria.json` operationalised "reaches F4" as *"its cfo appears in `diagnostics.all_hypotheses.cfo`"*. **That is wrong, and the criteria file has been left unedited so the error stays on the record.** `diagnostics.all_hypotheses` is family **F1**'s hypothesis table: `src/pipeline.py:428` passes the same `M` as `F1_burst_code.tested_hypotheses`. It was caught because all 34 F4 acceptances came back with an empty band — their F1 table is empty.

Consequences, all applied:

- **T3 is reported as "reaches F1"**, which is what was actually measured. It remains a meaningful rung — F1 carries the largest family weight (0.50) — but it is not F4.
- **F4 publishes no hypothesis → front-end mapping.** `accepted_hypothesis` keeps only a `stream` index, and the stream → front map is internal to `_block_code_family`. Per-candidate F4 *reach* is therefore **not measurable read-only**, and this report does not claim it. Per the standing rule, the missing field is reported rather than added to `src/`.
- **T4 is measured from the published claim instead.** `result['cfo']` is set from the front end that produced the published claim (`pipeline.py:385–407`). On all 34 F4-accepting captures `final_code == f4_code`, so F4 supplied the claim and that cfo **is** F4's own front end. This is published, exact, and sufficient for the question actually asked.

## 1. Method

- **Population:** all **1,810** sealed captures, imported from `f4_margin.jobs()` — bench-v2 sealed (430), bench-v1 sealed (30), independent null set (1,350). Class distinctions preserved: **1,300 signal-bearing** (a real carrier exists) and **510 no-signal** (`class == 'noise'`, where on/off-carrier is **undefined** and is never pooled into any rate).
- **Engine:** `analyze_iq(iq, _all_hypotheses=True)`, unmodified. The flag is existing evaluation-only logging read *after* every acceptance decision. **Verdict-neutrality was verified, not assumed:** status, final code, F4 acceptance, F4 best-p and outcome are identical to SPACE-F4-MARGIN-01's 1,810 rows, recorded with the flag off.
- **Per-front-end data:** `frontend_mechanism._front_candidates`, imported unchanged. **It reproduced the engine's published `n_front_ends` and `front_ends_rejected_serial_dependence` on 1,810 of 1,810 captures** — a large strengthening of MECH-01's 14/14.
- **Correctness:** `f4_margin._correct`, imported verbatim (each dataset's own pre-existing rule; the null set's mixed 900-true-null / 450-catalogue taxonomy is preserved).
- **Bands, committed before measurement:** `rot = |candidate_cfo − true_carrier| × true_sps` in cycles/symbol. on ≤ 0.01 < near ≤ 0.10 < off. Drifting carriers are referenced to their mean over the capture.
- **Determinism:** the census was run twice (the second time after the F1 relabel) and reproduced **115,057 admitted front ends** and an identical noise-like reference both times.
- **Evidence:** `results/offcarrier_census_rows.jsonl` (1,810), `results/offcarrier_census_admitted.jsonl` (115,057). Criteria sha256 `9c5f7eb2d4f1d15d…`.

## 2. The ladder — MEASURED FACT

Each rung is a **separate** distinction. *Existence is not admission; admission is not a claim.*

| Rung | | n / 1,300 signal-bearing | |
|---|---|---:|---|
| **T1** | an off-carrier CFO candidate **exists** | **391** | 30.08 % |
| **T2** | an off-carrier front end is **admitted** (passes the serial gate) | **373** | 28.69 % |
| **T3** | an off-carrier cfo **reaches F1**'s hypothesis table | **363** | 27.92 % |
| **T4** | an off-carrier front end **produces an F4-accepted claim** | **0** | 0.00 % |
| **T5** | an off-carrier front end produces a **wrong claim** | **0** | 0.00 % |

Zero counts: Wilson 95 % upper bound **0.0029** (≈ 1 in 345).

**Band-edge sensitivity** — the headline does not depend on where the band was drawn:

| threshold | captures where one exists | captures where one is admitted |
|---|---:|---:|
| rot > 0.05 | 950 | 907 |
| rot > 0.10 (committed) | 391 | 373 |
| rot > 0.20 | 33 | 33 |

## 3. What the admitted front ends look like — MEASURED FACT

115,057 admitted front ends. **All are serially independent by construction** (that is what admission means).

| band | n | agreement min/med/max | symbol SNR median | noise-like (SNR ≤ 0 dB) |
|---|---:|---|---:|---|
| on-carrier | 25,085 | 0.158 / 0.508 / 0.742 | **+0.88 dB** | 10,882 (43.4 %) |
| near-carrier | 48,329 | 0.083 / 0.526 / 0.773 | −0.44 dB | 26,711 (55.3 %) |
| **off-carrier** | **9,186** | 0.235 / **0.552** / 0.727 | **−0.81 dB** | **5,451 (59.3 %)** |
| undefined (no-signal captures) | 32,457 | 0.000 / 0.495 / 0.739 | **−4.35 dB** | 31,143 (96.0 %) |

**The two properties are distinct, as pre-registered and now measured.** Serial independence does **not** imply noise-like: 64.5 % of admitted front ends are noise-like, so **35.5 % are serially independent and carry signal energy**. And noise-like does not imply off-carrier: 43.4 % of *on-carrier* admitted front ends are noise-like too.

Off-carrier admitted front ends: rot median **0.126**, p90 0.189, **max 0.268** cyc/symbol; **2,282 (24.8 %) sit at the band edge** (|cfo| > 0.9·CFO_MAX) — the MECH-01 signature. Of the 9,186: 8,842 reach F1, 5,451 are noise-like, 5,268 are both.

Across all captures the engine offers 6 CFO candidates on 1,142 captures, 5 on 601, 4 on 63, 3 on 4 — **10,121 candidates in total, of which 650 are off-carrier and 1,028 are band-edge.**

## 4. Does it threaten F4? — MEASURED FACT

**No, on this evidence base.**

- **34 F4 acceptances. All 34 published from an on-carrier front end** (claim rot 0.0000). 32 TP + 2 TP_PARTIAL, **0 FALSE_ACCEPT, 0 zero-convergence.** Codes: RS(255,239) ×13, RS(255,223) ×11, TC-LDPC(128,64) ×10.
- **256 DECODED captures overall: 255 on-carrier claims, 1 near-carrier, 0 off-carrier.**
- **3 FALSE_ACCEPTs exist in the census**, all the same F2 continuous conv-K7 claim (`burst_8PSK_k3_diag_0165`, `ccsds_concat_0260`, `stream_k7_0251`). Their claim-producing front ends are **near-carrier (rot 0.0101) and on-carrier (0.0099, 0.0035)**. **None is off-carrier: the off-carrier mechanism does not explain any known false accept.**
- **510 no-signal captures: 32,457 admitted front ends, 0 F4 accepts, 0 FALSE_ACCEPT.** The engine admits tens of thousands of pure-noise front ends and still refuses.

**ENGINEERING INTERPRETATION.** The protection is **not** the serial-independence gate — MECH-01 showed it admits these front ends, and this census shows it does so 9,186 times. The protection is **downstream**: the family bar with its multiplicity correction. Admitting a noise-like front end *raises M*, which *lowers the bar*, and noise then fails to clear the lowered bar. This is the designed behaviour of the family-wise error control, and it is now measured at scale rather than argued.

## 5. The one configuration that came close — MEASURED FACT

The pre-registered analysis did not ask this; it emerged from the class breakdown and is reported because it is the closest thing to a threat in the data.

**`bench2_sealed/ccsds_concat_0268` is the only capture in 1,300 where *every* admitted front end is off-carrier** (36 of 36) — the sole-survivor configuration that produced MECH-01's false accept under correction. **It is also the closest non-accepting approach to the F4 bar in the entire census: margin +0.2304.**

It did **not** accept. Status `UNKNOWN`, outcome `FN` (a missed detection, not a false claim).

For scale: the tightest *accepting* margin is **−7.25** and the median accept is **−87.4** (negative = accepted). The gap between the closest non-accept (+0.230) and the weakest accept (−7.25) is **7.5 log units**. **ENGINEERING INTERPRETATION: proximity here is not near-miss proximity.**

Next closest approaches: `uncoded_bpsk_240_012` (+0.3986, best F1 hypothesis off-carrier at rot 0.136, REFUSED_OK), `noise_384_011` (+0.4015). **108 captures** have an off-carrier best-F1 hypothesis; the closest any of them came to the F4 bar is +0.3986.

**Confirming MECH-01's configuration:** all **10** bench-v2 `idle_carrier` captures admit **zero** front ends uncorrected (all `SIGNAL_NO_CODE`) — exactly the uncorrected behaviour MECH-01 measured on `idle_carrier_0411`, now shown to be the whole class, not one capture.

## 6. Where it concentrates — MEASURED FACT

Broad, not concentrated in one pathology. Highest rates: `nullset/uncoded_qpsk` 70/150 (46.7 %), `nullset/k3` 53/150, `k5` 50/150, `k7` 49/150, `uncoded_bpsk` 44/150, `8psk_k7` 36/100, bench-v1 sealed 7/30. Every bench-v2 burst class contributes 1–3 of 5. **`tc_ldpc_cltu` (10 captures) has none** — and it is one of the two classes carrying F4 acceptances.

**ENGINEERING INTERPRETATION.** The rate looks driven by how *strong and clean* the carrier is: where the true carrier dominates the x²/x⁴ spectrum, all candidates land on it (idle_carrier, tc_ldpc_cltu: 0 off-carrier admitted); where the signal is weaker or the spectrum flatter, the weakest candidates are drawn from the noise floor. **This was not tested by manipulating peak structure and remains an interpretation, not a measured cause.**

## 7. Answers to the six questions

1. **Does the shipped engine already admit off-carrier / noise-like front ends without correction?** **Yes, routinely.** 373 of 1,300 signal-bearing captures (28.7 %); 9,186 admitted front ends; 59.3 % of those also noise-like.
2. **How frequently?** See above. Robust across band definitions (rot > 0.05: 907 captures; > 0.2: 33).
3. **Does it threaten F4 structural acceptance?** **Not on this evidence base.** 0 of 1,300 (Wilson upper 0.0029). All 34 F4 accepts are on-carrier and correct; the closest off-carrier approach fell 0.2304 log units short, 7.5 log units from the weakest real accept.
4. **Does it explain anything from SPACE-F4-MARGIN-01?** **Yes — it removes the open worry.** F4-MARGIN-01 left PARTIALLY RESOLVED because a zero-convergence accept on record (`linear_0084`, in MECH-01's **tracking-ablated** arm) suggested the shipped engine might run close to an F4 accept on a structureless stream. This census identifies the configuration that would cause it (all-off-carrier survivors), finds it **once in 1,300**, and finds that it **still refused**. The shipped engine's F4 margin is not being quietly held up by the absence of off-carrier front ends — they are present in bulk and F4 rejects them.
5. **Does it change "carrier-estimator integration NOT SUPPORTED"?** **No — and it sharpens why.** The census shows off-carrier admission alone is **harmless**: it happens 9,186 times with no claim. What was harmful in `SPACE-CARRIER-EST-01` was not that a correction *creates* an off-carrier front end but that it **removed the on-carrier competition** — the correction turned a capture with 0 survivors into one with 18 survivors *all* on a single off-carrier candidate, taking F4's M from 0 to 2048. That sole-survivor configuration arises **once in 1,300** uncorrected and **reliably** under correction on idle carriers. **The decision stands: INTEGRATION NOT SUPPORTED.**
6. **What uncertainty remains?** §8.

## 8. UNRESOLVED QUESTIONS

- **Per-candidate F4 reach is not measurable read-only.** F4 publishes no hypothesis → front-end map. This report therefore cannot say how much of any capture's M4 an off-carrier front end contributed — only that admitted front ends (8.0 % off-carrier) all feed the stream set F4 scans. Closing this would require adding a published field to `src/`, which was **not** done.
- **Why a candidate lands off-carrier** is unproven (§6): consistent with the noise-floor account, never tested by manipulating peak structure.
- **One occurrence is one occurrence.** The sole-survivor configuration was seen once in 1,300. Its frequency is not usefully bounded by a single event; whether it is rarer or commoner on real spacecraft captures is unknown.
- **This evidence base is synthetic and static-carrier by construction.** It says nothing about Doppler-varying carriers, which is where `SPACE-DOPPLER` already measured a failure.
- **The 3 known FALSE_ACCEPTs remain unexplained by this work.** They are on/near-carrier F2 conv-K7 claims and are out of scope here.

## 9. What should be frozen

1. Off-carrier, noise-like front-end **admission is a normal, high-frequency operating state** of the shipped engine (28.7 % of signal-bearing captures), **not** a pathology introduced by carrier correction.
2. Admission has **never** produced a claim on 1,810 sealed captures: 0/1,300 F4 passes, 0 wrong claims, 0 on 510 no-signal captures.
3. Serial independence and noise-likeness are **distinct** properties; 35.5 % of admitted front ends are serially independent *and* carry signal energy.
4. The safeguard is the **multiplicity-corrected family bar**, not the serial gate.
5. `SPACE-F4-MARGIN-01` moves from PARTIALLY RESOLVED to **RESOLVED for the off-carrier question**: the configuration exists, was measured, and does not reach the bar.
6. **`SPACE-CARRIER-EST-01` remains INTEGRATION NOT SUPPORTED.** No remediation is recommended by this experiment.
7. Nothing here licenses any space capability claim; `SPACE_CLAIM_FIREWALL.md` §2a is unchanged.

## Method note

`eval/offcarrier_census.py`, criteria `eval/offcarrier_census_criteria.json` (left unedited despite the §0 error). Reproduce with `python eval/offcarrier_census.py run` then `report`. Tests: `tests/test_offcarrier_census.py`. No production file was modified; no threshold, bar, family weight, serial criterion, sps ranking or CFO generator was touched; no previous experiment's data, manifest, rows or report was altered; no bench-v2 access-log entry was written.

**END OF OFFCARRIER CENSUS RESULTS**
