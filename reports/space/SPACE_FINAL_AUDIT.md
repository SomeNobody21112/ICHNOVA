# SPACE_FINAL_AUDIT

**ICHNOVA · SIH26147 — final engineering audit of the Space-Ground Extension**
**Status: AUDIT ARTEFACT (2026-09-27). Verified against the working tree: `python -m pytest -q` → 247 passed; sealed datasets 192/192, 144/144, 288/288 byte-identical; production diff `src/pipeline.py` +61/−3 (write-only diagnostics only).**

**No experiment was run for this audit. No sealed dataset, results file, manifest, criteria file or historical experiment report was altered. No production code, threshold or gate was changed. No document was edited to make this audit pass — every inconsistency below is reported as a recommendation, not applied.**

---

## 1. Executive verdict

**The Space branch is internally coherent, evidence-backed and Constitution-compliant, and it should be frozen — after four documentation fixes, one of which is a demo-safety blocker.**

The engineering result that survives is narrow and real: **ICHNOVA's blind inference and refusal discipline are validated at benchmark conditions for a carrier that is static within the capture; under a moving carrier it keeps signal structure correct and publishes an unreliable payload, which is a measured limitation with a supported mechanism and a rejected remediation.** Nothing in the branch claims more than that.

**No measured result needs revision. No report contradicts another on a matter of fact.** The problems are all in *living* documents that were written before later experiments landed, plus one pre-experiment demo script that still scripts a headline the experiment refuted.

**One blocker before any demo:** `SPACE_DEMO_SCRIPT.md` line 15 scripts the spoken line **"0 wrong payloads across the sweep"**. The measured result is **54 of 96 wrong payloads**. It also promises "trajectory extraction" and "static-vs-S-curve classification" — both **NOT ESTABLISHED** — and cites `SPACE_BENCH_RESULTS.md`, **which does not exist in the repository**.

## 2. Established capabilities — MEASURED FACT

| # | Capability | Evidence |
|---|---|---|
| E1 | **Static-carrier blind inference** (modulation, symbol rate, code, framing, payload) within the documented benchmark scope | bench-v2 sealed 430 files, **9/9** pre-registered criteria; bench-v1 sealed **30/30**; independent 1,350-file null set **0/900** false accepts on true nulls |
| E2 | **Refusal discipline** — `SIGNAL_NO_CODE` / `UNKNOWN` with sufficiency reasons | bench-v2 **0/120** false accepts on non-catalogue classes (Wilson 95% upper 3.10%); null set 0/900; the WWVB real-signal refusal, where a significant structure was found and the time withheld |
| E3 | **Out-of-bound carrier offset is refused** | 35 of 48 out-of-bound captures refused |
| E4 | **Structural claim integrity survives a moving carrier** | **0 wrong structures in 192** sealed Doppler captures at up to 375× bench-v2's drift rate, and **0 in 144** mechanism captures under the shipped engine and both corrections. The one wrong structure on record occurred with the phase tracker **ablated** — a configuration that does not ship |
| E5 | **F4 block-code structural safety, characterised at scale** | 1,810 sealed captures, shipped engine: **34 accepts, all correct** (32 TP + 2 TP_PARTIAL), **0 zero-convergence**, **0 on the 900 true nulls**, only 3 of 1,776 rejections within 0.5 log units of the bar |
| E6 | **The multiplicity-corrected bar — not the serial gate — is what keeps noise out** | Off-carrier, noise-like front ends are admitted **routinely**: 373 of 1,300 signal-bearing captures, 9,186 of 115,057 admitted front ends. **None ever produced a claim**: all 256 published claims came from an on-carrier (255) or near-carrier (1) front end; **T4 = T5 = 0 of 1,300** (Wilson 95% upper 0.0029) |
| E7 | **The phase tracker's validity boundary is observable as evidence** | `diagnostics.phase_tracking_validity` and `unwrap_margin_by_front_end`; π is the exact discriminant of `np.unwrap`, not a chosen threshold; deterministic; proven inert; separates non-overlapping at claim level (statics 1.623–2.712 rad, non-slipping 0.0900–2.712, slipping 0.0001–0.0422) |
| E8 | **Evaluation replication fidelity** | The eval-side front-end replication reproduces the engine's published `n_front_ends` and `front_ends_rejected_serial_dependence` on **1,810 of 1,810** captures |

**E1–E3 are terrestrial/bench capabilities.** Per `SPACE_EVIDENCE_MATRIX.md`'s governing distinction, they are **NOT ESTABLISHED as space-link capabilities**, and this audit does not upgrade them.

## 3. Measured limitations — MEASURED FACT

| # | Limitation | Evidence |
|---|---|---|
| L1 | **Payload reliability under a time-varying carrier.** Wrong payload published beneath a **true** structural claim, with no refusal available from today's gates | **54 of 96** treated captures (0 of 96 static controls), `DOPPLER_EXPERIMENT_RESULTS.md` |
| L2 | **The drift boundary starts lower than first sampled** | 3 wrong payloads in 16 captures at drift 1.0×10⁻⁷–1.5×10⁻⁶ cyc/sample², rising to 0.938 by 1.5×10⁻⁵ |
| L3 | **The shipped phase tracker fails catastrophically past its own unwrap bound** | Median max phase error **273 rad** (linear) / **470 rad** (pass) vs a known trajectory; slips in 37 of 48 time-varying captures; matches the truth-side prediction in **47 of 48**. Static controls: worst error **0.643 rad**, **0 slips** |
| L4 | **The tracker's block-length adaptation is saturated** | It chose the minimum block (8) in **96 of 96** captures; coherence falls monotonically with block length. No headroom remains against faster carriers |
| L5 | **The verdict does not report payload unreliability** | Structure is trustworthy, payload is not, and `DECODED` does not distinguish them. This is the gap that request **B** (payload-reliability gate) exists for, and it remains **BLOCKED / unapproved** |

## 4. Supported mechanisms — and their limits

| Hypothesis | Status | Basis |
|---|---|---|
| **H1 — residual carrier-frequency error the front end does not model** | **SUPPORTED, dominant** | Ideal ground-truth correction removed the failure entirely: **0 of 96** treated captures wrong, against 57 of 96 for the shipped engine on the same bytes (paired) |
| **H3 — unwrap slip at the M-power ambiguity** | **SUPPORTED as a mechanism; REFUTED as the explanation** | Among claims from a tracked front end the separation is perfect (**24/24** slipped → wrong payload; **11/11** clean → correct), but **30 of 54** failures came from *untracked* front ends. Ceiling: ≤ 24 of 54 (44%) |
| **Correction reshapes the hypothesis search space** | **SUPPORTED** | Earliest divergence is the **CFO candidate set** (`_cfo_candidates`); a second dissociable route is q4 **re-ranking** of the sps candidate list. Replication verified 14/14, then 1,810/1,810 |
| H2 | **KILLED** | `DOPPLER_MECHANISM_RESULTS.md` |
| H4 | **LARGELY EXCLUDED** | ibid. |
| H6 | **WEAKENED** | ibid. |
| *Why* a CFO candidate relocates off-carrier | **NOT ESTABLISHED** | Consistent with the noise-floor account; never tested by manipulating peak structure |
| The mechanism of the 30 untracked-claim failures | **NOT ESTABLISHED** | Consistent with H1; not separately tested |

**ENGINEERING INTERPRETATION, stated as such.** The tracker is **not** the cause of the Doppler limitation — it is the only thing producing correct time-varying decodes at all (all 11 correct time-varying decodes came from it), and severity-for-severity tracked claims fail *less* than untracked ones (severity 0.25: 2/12 vs 12/12). It fails only past a bound explicit in its own code.

## 5. Rejected approaches — tested, then rejected on pre-registered rules

| # | Attempt | Outcome |
|---|---|---|
| R1 | **Integrating the blind per-block carrier estimator** | **INTEGRATION NOT SUPPORTED.** It fixes the Doppler symptom (108 → 2 wrong payloads on its own matrix) and **damages the existing evidence base**: bench-v1 30/30 → **22/30**; bench-v2 9/9 → **8/9**; null-set catalogue decodes 128 → **87**; and decisively it **manufactured a `ccsds_tc_ldpc_128_64` claim out of an idle carrier the production engine refuses**, F4 margin +2.699 → −0.112 with 0/18 codewords converged. Two independent pre-registered rules fired (C1, C3) plus the immediate-stop condition |
| R2 | **"Estimator output is spurious" (H-A)** as the explanation of that false accept | **REFUTED.** Zero-correction ≡ original through the same machinery; synthetic corrections reproduce the false accept ⇒ H-B supported |
| R3 | **`unwrap_corrections` as the tracker validity indicator** | **TESTED AND REJECTED** — fires on **10 of 48 static controls** (up to 146), because a benign ±π crossing also triggers a branch. No proxy was substituted |
| R4 | **The whole-search aggregate (`min`/`max_unwrap_margin_rad`) as a warning signal** | **REJECTED as an indicator** — static controls reach 0.0106 (`max`) and 0.0000 (`min`), because the search deliberately includes wrong-cfo/wrong-sps front ends whose trackers *should* be beyond the bound. Both are still published as facts, explicitly not as warnings |
| R5 | **§11.1.9's "any accept with zero converged codewords is a failure"** | **NOT APPLIED**, with the reason recorded *before* measurement: `src/blockcode.py:175-177` documents convergence as a per-block provenance marker, not an acceptance requirement, and bench-v2's own scorer treats partial convergence as partial credit |

**This is the branch's strongest evidence of discipline: the one change that would have "fixed Doppler" was measured, found to damage the system, and rejected — and the rejection is documented in more detail than the improvement.**

## 6. Remaining NOT ESTABLISHED

- **Carrier-trajectory measurement, static-vs-time-varying classification, trajectory in the receipt (D1, D2, D8).** Still NOT ESTABLISHED — and now for a *stronger* reason than absence of evidence: `TRACK_READOUT_RESULTS.md` measured that the shipped tracker estimates a **piecewise-constant phase with no trajectory model**, diverging by 273–470 rad from the known trajectory. **The new `phase_tracking_validity` field is a scalar phase margin, not a trajectory**, so it does not breach the gate's rule that no document may imply ICHNOVA measures or reports a carrier trajectory.
- **Static-vs-time-varying classification specifically.** The validity margin *separates* the two populations on the sealed set, which is tempting. It is **not** a classifier: coverage is 39 of 192, no threshold exists in `src/`, and the field is at the bound on 24 wrong claims **and** 28 correct refusals. Calling it classification would be an unearned upgrade.
- **Real spacecraft RF** — no spacecraft capture exists anywhere in this project.
- **Orbital Doppler** (TLE, geometry, pass model) — no orbit model exists.
- **CCSDS out-of-domain layers** — TM block-LDPC, turbo, packet semantics, GMSK, PCM/PSK/PM carriers, 132.0/133.0 semantics.
- **Space UI / mission replay / telemetry forensics / space receipt section** — design only, not built.
- **QPSK and higher-order behaviour of the unwrap bound** — the step is 2π/4, so it should engage at half the drift rate. HYPOTHESIS, untested; the sealed Doppler set is BPSK.
- **Fading as a physical channel model; time-varying symbol timing.**
- **Whether an unwrap slip is detectable or repairable from the engine's own statistics** — deliberately not examined, because that is remediation.

## 7. Claim-firewall audit

**Result: the firewall is sound. No forbidden language was found anywhere in `reports/space/` outside the forbidden-list rows that exist to name it.** A targeted sweep for *space-ready, Doppler robust, satellite validated, telemetry decoder, real spacecraft capability, orbital validation, guaranteed decoding, universal blind decoding, handles Doppler* returned only (a) the firewall's own prohibition table, (b) `DOPPLER_EXPERIMENT_RESULTS.md`'s list of forbidden sentences, and (c) `CARRIER_ESTIMATOR_RESULTS.md`'s explicit disclaimer. All three are correct usages.

**§2a remains exactly right.** The permitted sentence is still fully evidence-backed, and both halves are still required.

**Newly *permitted* claims that the evidence now supports but the firewall does not yet list.** These are optional additive strengthenings; none is required for the freeze, and none may be stated without its number:

1. *"Signal-structure identification remained correct in every time-varying-carrier capture tested (0 wrong structures in 192 sealed + 144 mechanism captures, shipped engine)."* — E4.
2. *"Across 1,810 sealed captures the shipped engine's block-code family accepted 34 times, every acceptance correct, none on the 900 true nulls."* — E5.
3. *"The engine routinely admits off-carrier, noise-like front ends and has never published a claim from one (0 of 1,300; 95% upper bound 0.29%); the safeguard is the multiplicity-corrected acceptance bar."* — E6.
4. *"The engine reports whether its own phase-tracking unwrap assumption was stressed, as evidence, and no decision consults it."* — E7. **Must never be phrased as Doppler handling, Doppler detection or a confidence score.**

**One firewall label whose justification (not label) is now stronger:** the NOT ESTABLISHED row covering D1/D2/D8 is currently justified by a missing read-out. The read-out now exists and *confirms* the label. Recommended wording change is in §10 (F2).

## 8. Evidence-integrity audit

| Check | Result |
|---|---|
| Sealed SPACE-DOPPLER (192, manifest `f9823ef5…`) | **byte-identical** |
| Sealed DOPPLER-MECH (144, manifest `a152d682…`) | **byte-identical** |
| Sealed CARRIER-EST (288, manifest `8af0c83d…`) | **byte-identical** |
| Prior results rows, manifests, criteria, protocol files modified | **none** |
| Historical experiment reports rewritten | **none** |
| bench-v2 access log | exactly **one** added entry, the authorised `SPACE-CARRIER-EST-01` read-only re-analysis (2026-09-26) |
| Production diff, whole branch | `src/pipeline.py` **+61/−3**, confined to `analyze_iq`'s diagnostics assembly and `_track_phase` |
| Did production instrumentation change any decision? | **No.** Verdicts re-verified unchanged on all 192 sealed Doppler captures; `_all_hypotheses` verified verdict-neutral against 1,810 F4-margin rows; corrupting `_tracking_validity` leaves status, code, payload, `accept.n_hypotheses` and `n_front_ends` identical; no file in `src/` or `server/` reads either new field |
| Full suite | **247 passed** |

**One collateral fix is on the record and was not hidden:** `eval/space_doppler_mech.py` stubbed the tracker as `lambda y, mod: None` for its arm-A ablation; the new optional parameter broke that stub, the **existing** test caught it, and the stub now mirrors the real signature with identical ablation semantics. MECH-01's data and rows were re-verified byte-identical afterwards.

## 9. Internal-consistency findings

**Narrative coherence: SUPPORTED.** Each link maps to a published report — unknown RF → evidence-first blind inference (bench-v1/v2, null set) → refusal when evidence is insufficient (0/120, 0/900, WWVB) → controlled Space-ground experiments (`SPACE-DOPPLER`, pre-registered) → measured Doppler limitation (54/96, published as-is) → mechanism investigation (MECH-01, H1 supported) → remediation attempt (`CARRIER_ESTIMATOR_EXPERIMENT`) → **remediation rejected when it damaged existing evidence** (C1+C3, INTEGRATION NOT SUPPORTED) → further diagnostics (EST-DIAG, FRONTEND-SENSITIVITY, FRONTEND-MECH, OFFCARRIER-CENSUS, F4-MARGIN) → explicit tracker validity evidence (TRACK-READOUT, TRACK-VALIDITY) → bounded Space capability.

**No report contradicts another on a matter of fact.**

**No numbers are conflated in the experiment reports.** The three wrong-payload counts belong to three disjoint populations and each report names its own: **54 of 96** = SPACE-DOPPLER sealed (seeds 500000–500191); **57 of 96** = MECH-01 arm B (seeds 600000–600143); **108 of 192 treated** = CARRIER-EST-01 arm A (seeds 700000–700287). **However** the status board places "54/96" and "57 of 96" in adjacent rows without naming the populations, which invites exactly the misreading the audit asks about. That is a presentation hazard, not a factual error — fix F5.

**Positioning (audit Q9): ACCURATE.** `SPACE_GROUND_SEGMENT_POSITIONING.md` §2 states ICHNOVA is *"an evidence-first **ground-segment RF analysis layer**"*, carries both halves of the Doppler sentence, labels the spacecraft-recording application a **RESEARCH CLAIM**, and records that the pre-registered narrowing consequence *"was honoured, not renegotiated."* Nothing frames ICHNOVA as a satellite system.

**The five-way distinction (audit Q10): CLEAN.** static-carrier capability (E1–E3, ESTABLISHED at bench scope) · time-varying-carrier limitation (L1–L5, MEASURED) · real spacecraft RF (NOT ESTABLISHED, no capture) · orbital modelling (NOT ESTABLISHED, no model) · telemetry capability (PARTIALLY SUPPORTED inside the searched domain, NOT SUPPORTED outside it). No document collapses any pair.

## 10. Required fixes

**All are documentation-only, in *living* documents. None changes a measured result. I have applied none of them.**

**Living vs frozen — the rule I applied:** `SPACE_ENGINEERING_STATUS.md`, `SPACE_IMPLEMENTATION_GATE.md`, `SPACE_ENGINEERING_ROADMAP.md`, `SPACE_EVIDENCE_MATRIX.md`, `SPACE_DEMO_SCRIPT.md` and `SPACE_CLAIM_FIREWALL.md` are living governance and may be corrected. `DOPPLER_FAILURE_ANALYSIS.md`, `DOPPLER_MECHANISM_RESULTS.md`, `DOPPLER_REMEDIATION_EXPERIMENT.md` and `DOPPLER_JUDGE_EXPLANATION.md` also contain now-stale "awaiting approval" language, but they are **frozen historical records and must not be edited** — the living documents carry the forward pointer.

| # | Severity | Location | Problem | Smallest correction |
|---|---|---|---|---|
| **F1** | **BLOCKER before any demo** | `SPACE_DEMO_SCRIPT.md` line 15 | Scripts the spoken line **"0 wrong payloads across the sweep"** — the measured result is **54 of 96 wrong**. Also promises "Show trajectory extraction: measured carrier drift vs injected truth; static-vs-S-curve classification", both **NOT ESTABLISHED**. Cites `SPACE_BENCH_RESULTS.md`, which **does not exist** | Replace the segment with the measured outcome and the refusal story: cite `DOPPLER_EXPERIMENT_RESULTS.md`, state 54/96 wrong payloads beneath 0 wrong structures, and present the rejected remediation as the discipline result. Delete the trajectory-extraction and classification promises. Fix the file reference |
| **F2** | Medium | `SPACE_ENGINEERING_STATUS.md` line 56; `SPACE_IMPLEMENTATION_GATE.md` §9.3 status line (118); `SPACE_ENGINEERING_ROADMAP.md` line 32; `SPACE_EVIDENCE_MATRIX.md` line 284 | All four say the trajectory read-out is **awaiting approval** / D1-D2-D8 are "blocked on an unapproved read-out". The read-out was **approved, implemented and published** (TRACK-READOUT-01, TRACK-VALIDITY-01) | Keep the **NOT ESTABLISHED** label — it is still correct — and change the *reason*: no longer "blocked on an unapproved read-out" but "measured: the shipped tracker estimates a piecewise-constant phase with no trajectory model (`TRACK_READOUT_RESULTS.md`)". Mark gate §9.3 **APPROVED AND DELIVERED**, retaining its rule that no document may imply ICHNOVA reports a carrier trajectory |
| **F3** | Medium | `SPACE_ENGINEERING_STATUS.md` line 57 | Says the estimator's **"recall cost is unmeasured"**. `SPACE-CARRIER-EST-01` measured it in full | Replace with the measured cost (bench-v1 30/30→22/30; bench-v2 9/9→8/9; null-set catalogue 128→87; idle-carrier false accept) and the decision **INTEGRATION NOT SUPPORTED** |
| **F4** | Low | `SPACE_ENGINEERING_STATUS.md` line 16 and header (line 3) | Says **"H3 still untested"**, and the header reads "as of 2026-09-26 (updated after `SPACE-FRONTEND-MECH-01`)" while the board now contains three later experiments | H3 → "SUPPORTED as a mechanism for ≤24 of 54 failures; REFUTED as the explanation (`TRACK_READOUT_RESULTS.md`)". Bump the header to 2026-09-27 / `SPACE-TRACK-VALIDITY-01` |
| **F5** | Low | `SPACE_ENGINEERING_STATUS.md` lines 16, 57 vs the 54/96 row | 54/96, 57/96 and 108/192 appear without their populations, inviting the reading that they are the same measurement | Add the population in-line, e.g. "57 of 96 (MECH-01 population, seeds 600000–600143)" |
| **F6** | Optional | `SPACE_CLAIM_FIREWALL.md` §4 | Four newly permitted, fully measured claims are not yet listed (§7 above) | Add them verbatim with their numbers, or leave §4 as-is. **Not required for the freeze** |

## 11. Freeze recommendation

**FREEZE the Space branch, contingent only on F1.**

F1 is a demo-safety blocker: a script that pre-writes *"0 wrong payloads across the sweep"* in front of judges would state the opposite of the project's own headline measurement, and the hedge "read whatever it actually says" is not sufficient protection for a live demo. **F2–F5 are stale-status corrections that should be made for coherence but block nothing and change no result. F6 is optional.**

**No new research branch is warranted.** Every remaining uncertainty in §6 is either already characterised (the 30 untracked-claim failures are an H1 question), inherently out of reach without new data (real spacecraft RF), or explicitly out of scope (orbital modelling). The interesting-but-unnecessary items — QPSK behaviour of the unwrap bound; why a CFO candidate relocates off-carrier; whether a slip is detectable from the engine's own statistics — are recorded here as **future work**, not started.

## 12. Final Space capability statement (for SIH material)

> **ICHNOVA is an evidence-first ground-segment RF analysis layer.** It takes an IQ capture of an unknown or partially known signal, infers signal structure by hypothesis testing under family-wise error control, and issues **DECODED / SIGNAL_NO_CODE / UNKNOWN** with a cryptographic evidence receipt.
>
> **What is validated, at documented benchmark conditions, for a carrier that is static within the capture:** blind identification of modulation, symbol rate, coding and framing (bench-v2 sealed, 430 files, 9/9 pre-registered criteria; bench-v1 sealed 30/30), and refusal when the evidence is insufficient (0 of 120 false accepts on non-catalogue classes; 0 of 900 on an independent null set; one real-signal capture where a significant structure was found and the time value withheld).
>
> **What was measured and is a limitation:** under a carrier whose frequency moves during the capture, signal-structure identification remained correct in all 192 controlled synthetic captures, while the published **payload** was wrong in **54 of 96** treated captures, with no refusal available from the current gates. The decode verdict is therefore **scoped to a carrier that is static within the capture**.
>
> **What was tried and rejected:** a blind carrier pre-correction removed most of that payload failure and simultaneously cost 8 of 30 bench-v1 decodes, one of bench-v2's nine criteria, 41 of 128 null-set catalogue decodes, and manufactured a CCSDS LDPC claim from an idle carrier. It was **not integrated**.
>
> **What the engine now reports as evidence:** whether its own phase-tracking unwrap assumption was stressed during a capture — a measured phase margin, published alongside the result, consulted by no decision.
>
> **Not established:** real spacecraft RF (no spacecraft capture exists in this project), orbital Doppler modelling, carrier-trajectory measurement or classification, and CCSDS layers outside the searched domain. All synthetic data is labelled **SIMULATED**; all benchmark numbers are labelled **BENCHMARK**.

**END OF SPACE FINAL AUDIT**
