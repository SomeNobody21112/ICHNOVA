# SPACE_GROUND_SEGMENT_POSITIONING
**ICHNOVA · SIH26147 — what ICHNOVA is and is not, in the space-ground-segment context**
**Status: RESEARCH/POSITIONING (2026-09-25). Implementations nothing.**
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

**Space-specific narrowing (INFERENCE):** for spacecraft links, the honest claim is *strictly conditional*:

> ICHNOVA **could serve** as an evidence-first analysis layer for **partially unknown spacecraft RF recordings** — uncooperative, mislabelled, degraded or new emitters where known-parameter decoders have nothing to start from — **provided its space-relevant impairments (Doppler, fading, pass geometry) are first validated by the sealed SPACE-BENCH defined in this study.** Until that validation exists, the space positioning is a RESEARCH CLAIM, not a capability statement.

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

1. SPACE-BENCH families C–E (static CFO, time-varying Doppler, Doppler+noise) fail acceptance ⇒ space claim narrows to "clean/low-SNR telemetry analysis layer" and DOPPLER_EXPERIMENT_DESIGN.md reopens as engineering.
2. Adversarial family I produces any false DECODED ⇒ STOP (Constitution rule), document, gate, re-run; positioning claim about trustworthiness is suspended until fixed.
3. No plausible path to a real capture of spacecraft-resembling telemetry within SIH scope ⇒ positioning stays a simulation-only demonstrator, explicitly labelled SIMULATED everywhere.

**END OF POSITIONING**
