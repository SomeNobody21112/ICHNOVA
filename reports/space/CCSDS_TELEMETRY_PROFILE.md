# CCSDS_TELEMETRY_PROFILE
**ICHNOVA · SIH26147 — CCSDS telemetry profile: layer-by-layer honesty (research + profile design)**
**Status: RESEARCH + PROFILE DESIGN (2026-09-25). No code modified.**
Governing reference: **CCSDS 131.0-B-5, TM Synchronization and Channel Coding (September 2023)** — FACT, current issue (the brief's "B-6" corrected; see SPACE_RESEARCH_LANDSCAPE.md §1.1).

---

## 1. Purpose and the central question

This profile exists to answer, for any decode: **"Which assumptions were required to reach this decode?"** It is an *interpretation view over existing evidence*, never a new inference path — and it uses exactly four labels per layer:

**SUPPORTED** (validated by sealed evidence) · **PARTIALLY SUPPORTED** (works under declared conditions) · **NOT SUPPORTED** (not implemented) · **NOT ESTABLISHED** (implemented but not validated at space-link conditions).

## 2. Layer table

| Layer (131.0-B-5 / related) | Status | Evidence / notes |
|---|---|---|
| **Attached Sync Marker, 32-bit** `0x1ACFFC1D` | **SUPPORTED** | Implemented (`framing.MARKERS`, from `references/ccsds_constants.json`); exercised in sealed F3 frame family — FACT |
| **Attached Sync Marker, 64-bit** `0x034776C7272895B0` (LDPC stream) | **SUPPORTED** | Same — FACT |
| **Blind sync for non-catalogue frame formats** (constant-field windows W ∈ {16,24,32,48,64}) | **SUPPORTED** (as an ICHNOVA capability, not a CCSDS one) | Exact binomial, Bonferroni over declared periods — FACT |
| **Transfer frame structure (132.0)** — version/Master/VC frames | **PARTIALLY SUPPORTED** | Frame period/marker/constant-and-alternating column map exists (header proven, payload boundary, undetermined columns reported with frames-needed); *semantic* 132.0 field interpretation is NOT implemented — FACT from code |
| **Space packet protocol (133.0-B)** | **NOT SUPPORTED** | No packet parsing anywhere — FACT |
| **Convolutional coding r=1/2, K=7 (G2-first)** | **SUPPORTED** | Sealed bench-v2: continuous K7 stream 16/16 at Es/N0 ≥ 6 dB — FACT |
| **Convolutional K=3, K=5** | **SUPPORTED** | Catalogue + sealed bench-v2 families — FACT |
| **Reed-Solomon (RS)** | **SUPPORTED** | Sealed bench-v2 CCSDS concatenated chain: 10/12 full decodes at Es/N0 ≥ 9 dB, honest partial RS decodes under CFO-drift/Rician — FACT |
| **CCSDS concatenated (RS + conv)** | **SUPPORTED** (with the 10/12 recall honestly stated) | bench-v2 criterion pair records the revision made before SEALED existed — FACT |
| **TC LDPC (arithmetic, e.g. (128,64)…)** | **SUPPORTED** (bench conditions) | Sealed: CLTU 8/8 at Es/N0 ≥ 6 dB — FACT |
| **Block LDPC (8161/8144, k=1024 family) for TM** | **NOT SUPPORTED** | Not in the code catalogue — FACT |
| **Turbo codes (legacy)** | **NOT SUPPORTED** | Not implemented — FACT |
| **TM randomizer 255 / 131071; TC BTG randomizer** | **SUPPORTED** (de-randomization; blind *detection* of randomizer choice within the searched hypotheses) | All three reproduce standards-printed first-40-bit vectors (tests/test_catalogue.py) — FACT |
| **CLTU / TC framing (231.0)** | **PARTIALLY SUPPORTED** | LDPC CLTU chain decoded in bench; full 231.0 start-sequence/tail semantics not claimed — FACT from bench description |
| **Modulation assumptions (401.0: BPSK/QPSK, PCM/PSK/PM, GMSK…)** | **PARTIALLY SUPPORTED** | BPSK/QPSK blind-searched; 8PSK/16-QAM EXPERIMENTAL and OFF (Constitution §24 — enabling measured harmful); PCM/PSK/PM phase-modulation carriers and GMSK NOT SUPPORTED — FACT |
| **Doppler/time-varying carrier conditions** | **NOT ESTABLISHED** | Tracking exists (measured on synthetic drift classes); pass-shaped trajectory validation = DOPPLER experiment, not yet run — FACT |
| **Real spacecraft capture validation** | **NOT ESTABLISHED** | No real spacecraft recording exists in the project; real-signal validation to date is terrestrial (time codes, DDH47, AIR — FACT) |

## 3. "Which assumptions were required?" — the mapping

The profile view is generated from the **accepted hypothesis + evidence pack** (all FACT structures today):

```
ASSUMPTION LEDGER (generated, per decode)
  modulations searched: BPSK, QPSK            [gated-out: 8PSK, 16-QAM — searched? NO]
  sps domain searched: 2–20 (divisors incl.)  [chosen: 6 sps = 166.67 ksym/s @ 1 MHz]
  CFO bound assumed: ±1.25% fs                [estimated: −0.00569 cyc/sample]
  roll-off assumed: β=0.3 matched filter      [estimated β not searched — declared]
  coding domain: catalogue v1 (K3/K5/K7, RS, concatenated, TC-LDPC)
  interleaver domain: block/diagonal/Forney/LTE-QPP
  frame domain: ASM 1ACFFC1D / 64-bit / blind windows, P ∈ [64, 16384] bits
  randomizers: tm_255 / tm_131071 / tc_btg
  carrier model: static CFO [tracked front end applied: YES/NO]
  NOT TESTED: 8PSK/16-QAM payloads, block-LDPC TM, turbo, packet semantics,
              phase-modulation carriers, GMSK
```

Every line is derived from code constants and the run's own diagnostics — the ledger cannot claim more than was searched. Out-of-domain items are printed, not hidden: the operator sees what the decode did **not** rule out.

## 4. Profile statement (for UI and documents)

> "CCSDS-aligned within the searched domain. The engine blindly identified structure compatible with [layers actually accepted]. CCSDS layers outside the searched domain (listed) were not tested and are not claimed. This is not a CCSDS-certified implementation." — DESIGN PROPOSAL, with the certification disclaimer mandatory.

**END OF CCSDS PROFILE**
