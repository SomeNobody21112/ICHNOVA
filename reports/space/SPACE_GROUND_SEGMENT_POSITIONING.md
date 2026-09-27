# SPACE_GROUND_SEGMENT_POSITIONING
**ICHNOVA · SIH26147 — what ICHNOVA is and is not, in the space-ground-segment context**
**Status: RESEARCH/POSITIONING (2026-09-25). Implements nothing.**
Labels: FACT / INTERPRETATION / INFERENCE / DESIGN PROPOSAL as in SPACE_RESEARCH_LANDSCAPE.md.

---

## 1. The chain we sit in

DESIGN PROPOSAL (the intended demonstrator chain), with status tags per node:

```
SPACECRAFT                       [context only — ICHNOVA is NOT the spacecraft]
   ↓ RF COMMUNICATION LINK       [context only]
GROUND ANTENNA / RF FRONT END / SDR   [context — existing capture infrastructure; NOT ESTABLISHED as ours]
   ↓ IQ CAPTURE                  [EXISTING — float32 .iq ingestion, src/modem.py load_iq]
ICHNOVA                          [EXISTING engine — the work of this project]
   ↓ EVIDENCE-BASED SIGNAL ANALYSIS   [EXISTING — pipeline.py OBSERVE→…→ACT]
DECODED / SIGNAL_NO_CODE / UNKNOWN    [EXISTING — three-outcome model]
   ↓ GROUND OPERATOR / MISSION ANALYSIS   [EXISTING console — operator actions, receipts; space-specific UX is DESIGN PROPOSAL]
```

## 2. What ICHNOVA is (the defensible statement)

**Positioning statement (narrowed as the evidence requires):**

> **FACT-grounded statement:** ICHNOVA is an evidence-first **ground-segment RF analysis layer**: it takes an IQ capture of an unknown or partially known communication signal, infers signal structure by hypothesis testing under family-wise error control, and issues **DECODED / SIGNAL_NO_CODE / UNKNOWN** with a cryptographic evidence receipt — refusing to claim a decode the evidence has not earned.

**Space-specific narrowing, REVISED 2026-09-25 after the Doppler experiment.** The first space-relevant impairment has now been measured, and it narrowed the claim rather than widening it. The defensible space sentence today:

> **ICHNOVA is an evidence-first ground-segment RF analysis layer whose blind-inference and refusal mechanisms are validated at controlled benchmark conditions, and whose controlled time-varying-carrier experiment has identified a payload-reliability boundary: under a carrier that moves during the capture it continued to identify signal structure correctly (0 wrong structures in 192 captures) while publishing an unreliable payload in 54 of 96 treated captures. Its decode verdict is therefore scoped to a carrier that is static within the capture.**

This is *more precise* than the earlier conditional formulation below, and deliberately no more ambitious. Three things changed:

1. **The condition is no longer open.** The earlier sentence said the space claim was pending a Doppler experiment. That experiment has run and **failed its headline criterion** — so the honest form is not "pending validation" but "validated within a stated boundary, with the boundary measured".
2. **The relevance survived; the deployment claim did not.** SPACE relevance rests on what held: structural identification under drift up to 375× the previously tested rate, out-of-bound refusal, and the refusal discipline generally. SPACE deployment is not claimed in any form.
3. **What remains conditional is narrower and named:** payload reliability under a moving carrier, carrier-trajectory measurement (D1/D2/D8), orbital Doppler, and real spacecraft RF — each NOT ESTABLISHED, each with its own experiment.

The earlier supporting facts still stand: the blind-inference core is validated (bench-v2 9/9 sealed — FACT), the CCSDS-relevant coding families are validated (CCSDS concatenated 10/12, TC-LDPC 8/8 sealed — FACT), and the ASM markers and randomizers are standards-verified (FACT from code). What has been added is not a capability but a **measured limit**, and stating it is part of the positioning, not a footnote to it (SPACE_CLAIM_FIREWALL.md §2a).

**The superseded formulation, kept for the record (written before the experiment ran):** for spacecraft links, the honest claim is *strictly conditional*:

> ICHNOVA **could serve** as an evidence-first analysis layer for **partially unknown spacecraft RF recordings** — uncooperative, mislabelled, degraded or new emitters where known-parameter decoders have nothing to start from — **provided its space-relevant impairments (Doppler, fading, pass geometry) are first validated by the sealed SPACE-BENCH defined in this study.** Until that validation exists, the space positioning is a RESEARCH CLAIM, not a capability statement.

*(The paragraph below belongs to the superseded pre-experiment text: its statement that "no Doppler experiment has been run" was true when written on 2026-09-25 and is no longer true — the experiment ran the same day. §2's revised statement is the current one.)*

That last clause is deliberate. The brief asked whether the positioning is defensible; the honest answer is **conditionally defensible**: the blind-inference core is validated (bench-v2 9/9 sealed — FACT), the CCSDS-relevant coding families are validated (CCSDS concatenated 10/12, TC-LDPC 8/8 sealed — FACT), the ASM markers and randomizers are standards-verified (FACT from code), but **no space-channel benchmark, no Doppler experiment, and no spacecraft-resembling capture has been run** — so any stronger sentence today would be a false claim (see SPACE_CLAIM_FIREWALL.md).

## 3. Hard boundaries — what ICHNOVA is NOT

Each item is a standing constraint, not a modesty statement (FACT about the repository):

| NOT | Why |
|---|---|
| a satellite or spacecraft system | No flight software, no on-board processing, no orbit control |
| an orbital control / tracking system | No ephemerides, no scheduling, no pointing — Satellite tracking is NOT ESTABLISHED and not attempted |
| an encryption-breaking system | No cryptanalysis anywhere in the codebase |
| operational ISRO / government infrastructure | Independent prototype; no ISRO involvement, branding, or claims of operational deployment |
| a real ground-station network | Live capture exists through one local SDR (§22 of the Constitution — FACT); a network is not claimed |
| a universal protocol decoder | Catalogue-bounded hypothesis domains; unsupported structures → SIGNAL_NO_CODE/UNKNOWN by design |
| AI/ML anything | Deliberately evidence-first, NumPy/SciPy, exact statistical tests — no learned components to defend |

## 4. Where the value actually is (the gap ICHNOVA occupies)

INFERENCE from the competitor landscape (SPACE_RESEARCH_LANDSCAPE.md §4): the space ground segment is rich in **known-parameter** decoding (gr-satellites SatYAML, SatNOGS mode DB) and **human-driven** reverse engineering (URH). The unserved niche is the **partially unknown** capture:

- a signal whose emitter is unidentified, mislabelled, or newly deployed;
- a known emitter whose link has degraded and no longer matches its catalogue entry;
- a capture where the operator must know **whether a decode can be trusted at all**.

In that niche the differentiator is not decoding power but **decision honesty**: hypothesis testing with Bonferroni-corrected exact tests (FACT — pipeline.py), three-outcome semantics with real refusals (FACT — bench-v2 0/120 false accepts on non-catalogue signals), sufficiency analysis that says what capture would settle a refusal (FACT — sufficiency.py ACHIEVABLE / IMPOSSIBLE_IN_DOMAIN), and tamper-evident receipts (FACT — receipt.py). FACT + INFERENCE, honestly labelled: **that combination is not a capability any surveyed competitor documents.**

## 5. What would falsify or force re-narrowing of this positioning

Pre-registered in this study, to be honoured:

1. **THIS HAS NOW PARTIALLY FIRED (2026-09-25).** The pre-registered consequence was: *SPACE-BENCH families C–E fail acceptance ⇒ the space claim narrows to a "clean/low-SNR telemetry analysis layer" and DOPPLER_EXPERIMENT_DESIGN.md reopens as engineering.* The controlled Doppler experiment — the family-D question, run standalone and pre-registered — failed its headline criterion. The claim was therefore narrowed in §2 (the decode verdict is scoped to a static-within-capture carrier) and the design reopened as `DOPPLER_REMEDIATION_EXPERIMENT.md`. The consequence was honoured, not renegotiated.
2. Adversarial family I produces any false DECODED ⇒ STOP (Constitution rule), document, gate, re-run; positioning claim about trustworthiness is suspended until fixed.
3. No plausible path to a real capture of spacecraft-resembling telemetry within SIH scope ⇒ positioning stays a simulation-only demonstrator, explicitly labelled SIMULATED everywhere.

**END OF POSITIONING**
