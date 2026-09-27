# SPACE_CLAIM_FIREWALL
**ICHNOVA · SIH26147 — the claim firewall for all space-related work**
**Status: STANDING POLICY (2026-09-25). Binding on every space document, UI screen, demo, and commit message.**

---

## 1. The rule

> **No claim without measured evidence. Every unproven thing is labelled. Labels are not decoration; they are the product.**

## 2. Mandatory labels

| Label | When it must appear |
|---|---|
| **SIMULATED** | Every synthetic capture, every replay timeline, every simulated pass parameter (duration/elevation/Doppler/noise), and inside every exported package's provenance section |
| **BENCHMARK** | Every SPACE-BENCH-derived screen, number, or figure |
| **EXPERIMENTAL** | 8PSK/16-QAM anywhere they are mentioned; any feature behind a flag; the fingerprint/similarity features |
| **NOT ESTABLISHED** | Anything implemented but unvalidated at space conditions (block-LDPC TM; real-capture space validation; field deployment; TLS; pen test; and, within row 6, trajectory measurement / classification / receipt — D1, D2, D8) |
| **MEASURED LIMITATION** | Time-varying carrier (Doppler). The experiment has run: wrong payload beneath a true structural claim in **54 of 96** treated captures, **0 of 96** on static controls (2026-09-25, `reports/space/DOPPLER_EXPERIMENT_RESULTS.md`). This label is **stronger than NOT ESTABLISHED** and replaces it for Doppler: the answer is known and it is negative. Any statement about decoding must carry the **static-carrier** qualifier, and the three-outcome guarantee must never be presented in a way that implies a *payload* guarantee. **Update 2026-09-27: the label STANDS.** `PAYLOAD_CONSISTENCY_MIN` is now integrated, so such a payload is **withheld** instead of published (`PAYLOAD_GATE_RESULTS.md`; 52 of those 54 captures become `SIGNAL_NO_CODE` with the reason given). The payload is still **not recovered** — the limitation is unchanged, it is merely no longer asserted, and 2 of the 54 still clear the floor. |
| **PARTIALLY SUPPORTED** | CCSDS layers where only part of the semantics exist (transfer frames, CLTU, modulation assumptions) |
| **NOT SUPPORTED** | CCSDS layers not implemented (block-LDPC TM, turbo, packet semantics, GMSK, PCM/PSK/PM carriers) |

## 2a. The Doppler sentence: permitted and forbidden forms (2026-09-25, post-experiment)

**PERMITTED — this exact statement is evidence-backed and may be used as written:**

> "ICHNOVA's blind-inference core and refusal discipline are validated within its documented benchmark scope; controlled time-varying-carrier testing has identified a measured limitation in payload reliability."

Permitted variants must keep **both halves** — the validated scope *and* the measured limitation. Dropping the second half is a false claim by omission.

**PERMITTED as of 2026-09-27, because the behaviour now ships** (`PAYLOAD_GATE_RESULTS.md`, `PAYLOAD_CONSISTENCY_MIN` in `src/pipeline.py`):

> "Where the decoded payload does not reproduce the observed stream, ICHNOVA withholds it and reports SIGNAL_NO_CODE with the statistic and floor that refused it, keeping the structural claim the evidence supports."

Measured before integration and re-measured after: 0 of 1,278 previously-correct decodes lost; bench-v1 30/30; bench-v2 sealed 9/9 criteria with false accepts **3 → 0**; null set 0/900 false accepts. **This may NOT be stated as "ICHNOVA handles Doppler" or as a payload capability** — it is a refusal, not a recovery, and the measured limitation above is unchanged.

**FORBIDDEN — each of these is prohibited unless and until future evidence establishes it:**

| Forbidden statement | Why |
|---|---|
| "ICHNOVA handles satellite Doppler." | Measured: 54 wrong payloads in 96 time-varying-carrier captures |
| "ICHNOVA is Doppler robust." | The opposite is what was measured |
| "ICHNOVA is validated on satellite links." | No spacecraft capture exists in this project |
| "ICHNOVA can decode telemetry during a satellite pass." | No pass has ever been analysed; the trajectory tested is CONTROLLED SYNTHETIC |
| "ICHNOVA is space-ready." | Never supported, and now contradicted by measurement |
| Any presentation of the three-outcome guarantee that implies a **payload** guarantee without the static-carrier qualifier | What held is the guarantee about *structure*: 0 wrong structures in 192. Payload reliability is the measured gap |

**The one-sentence test applied to this result** — *"would this still be true if the reader re-ran every measurement it rests on?"*: the permitted statement survives it because both halves are measured; every forbidden statement fails it.

## 3. Forbidden claims (absolute)

1. "ICHNOVA is satellite technology" / an ISRO system / Government-of-India system — **never**. Independent prototype; government RF-monitoring workflows are design inspiration only (existing footer wording — FACT — is the correct register).
2. Operational deployment on any spacecraft, mission, or agency ground segment.
3. Validated on operational spacecraft telemetry (no such capture exists — FACT).
4. "First-of-kind", "novel algorithm", "patented", "superior to commercial/defence systems" (those systems are not inspectable — the comparison cannot be evidenced).
5. "AI-powered" anything — the engine is deliberately NumPy/SciPy exact statistics; claiming ML would be false *and* indefensible.
6. Universal decoder / universal protocol support — catalogue-bounded refusal is the design, not a limitation to hide.
7. Encryption breaking / cryptanalysis of any kind.
8. Fake live data, fake tracking, fake ground-station networks, fake mission control, fake "live ISRO feed".
9. Arbitrary confidence percentages ("97% confident") — only exact statistics: p-values, thresholds, M, coverage, structural booleans, measured SNR/quality numbers.
10. Silent benchmark tuning — criteria are pre-registered; any discovered failure is STOP → document → decide (Constitution rule). A documented failure + corrective gate is a **valid published outcome**; a hidden one is misconduct.

## 4. Allowed claims (as they stand today, each FACT-backed)

- "Evidence-first blind RF analysis: infers signal structure by hypothesis testing under family-wise error control and issues DECODED / SIGNAL_NO_CODE / UNKNOWN."
- "Refuses to claim a decode the evidence has not earned" — backed by **two separate artefacts, each cited as its own**: bench-v2 sealed **0/120** false accepts on non-catalogue classes (430-file sealed run, 95% Wilson upper bound 3.10% — FACT), and the independent **1,350-file null set** at **0/900** false accepts on non-catalogue files with **0/450** wrong decodes on coded files (`eval/nullset.py`, seed 500000, parameter ranges deliberately different from bench-v1 — FACT). Neither number may be attributed to the other benchmark.
- "CCSDS-aligned within the searched domain" (ASMs, randomizers, conv/RS/concatenated/TC-LDPC validated at bench conditions — FACT), **with** the CCSDS profile's out-of-domain ledger shown.
- "Space positioning: a candidate evidence-first analysis layer for partially unknown spacecraft RF recordings, **conditional on SPACE-BENCH validation**" (SPACE_GROUND_SEGMENT_POSITIONING.md §2).
- Real-signal validation *as actually measured*: JJY/DCF77/MSF/WWV time codes with GPS agreement, DDH47 FSK, AIR carriers, one live SDR capture ending in SIGNAL_NO_CODE (§22 — FACT).

## 5. Enforcement mechanics

- **Documents:** every new space document carries the label taxonomy in its header; the reviewer checklist is this file.
- **UI:** every space screen renders its labels from data (provenance/flags), not from copy that can drift.
- **Exports:** the space evidence package embeds SIMULATED/REAL provenance in the signed content (SPACE_EVIDENCE_RECEIPT_DESIGN.md §3).
- **Demos:** the demo script (SPACE_DEMO_SCRIPT.md) requires the SIMULATED banner on screen during replay and a spoken BENCHMARK label when showing sealed numbers.
- **Commits:** space-related commits reference the document they implement; no engine-constant change is ever bundled with a space feature.

## 6. The one-sentence test

Before any sentence about ICHNOVA and space leaves this repository, it must survive:

> *"Would this sentence still be true if the reader re-ran every measurement it rests on?"*

If the sentence rests on measurements that do not exist yet, it gets a label or it gets deleted.

**END OF CLAIM FIREWALL**
