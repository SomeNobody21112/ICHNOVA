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
| **NOT ESTABLISHED** | Anything implemented but unvalidated at space conditions (Doppler behaviour until the experiment runs; block-LDPC TM; real-capture space validation; field deployment; TLS; pen test) |
| **PARTIALLY SUPPORTED** | CCSDS layers where only part of the semantics exist (transfer frames, CLTU, modulation assumptions) |
| **NOT SUPPORTED** | CCSDS layers not implemented (block-LDPC TM, turbo, packet semantics, GMSK, PCM/PSK/PM carriers) |

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
- "Refuses to claim a decode the evidence has not earned" — backed by sealed 0/120 false accepts and 0/900 null accepts (bench-v2 — FACT).
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
