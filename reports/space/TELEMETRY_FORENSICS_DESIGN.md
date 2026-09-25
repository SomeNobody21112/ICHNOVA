# TELEMETRY_FORENSICS_DESIGN
**ICHNOVA · SIH26147 — TELEMETRY FORENSICS screen (design only)**
**Status: DESIGN PROPOSAL (2026-09-25). No UI code written.**
Principle: this screen exposes **evidence, not decoration**. Every value is a measurement from the evidence pack; no arbitrary confidence percentages exist anywhere on it (firewall rule 9). It reuses the existing evidence components and honesty conventions already in the operator console (verdict-first, quality-beside-verdict, provenance tags — FACT) and extends them with the space-specific LINK section.

---

## 1. Screen structure

```
┌────────────────────────────────────────────────────────────────────────┐
│ TELEMETRY FORENSICS — <capture id>          [provenance tag]           │
│                                (SIMULATED banner when applicable)      │
├──────────────────────────┬─────────────────────────────────────────────┤
│ CAPTURE                  │ LINK                                        │
│  duration, sample rate   │  modulation (from accepted hypothesis)      │
│  fs + fs_source          │  symbol rate (+ sps, fs-normalised)         │
│  capture gate: GOOD/FAIR │  CFO (cyc/sample + Hz-equivalent)           │
│  clipping/DC/dropouts/   │  Doppler trajectory (when measured):        │
│  I/Q balance             │   static | linear | pass-shaped (declared   │
│                          │   rule), per-block measured points,         │
│                          │   residuals; NOT MEASURED when absent       │
├──────────────────────────┼─────────────────────────────────────────────┤
│ CODING                   │ FRAME                                       │
│  FEC family + params     │  sync status: ASM 32 / ASM 64 / blind window│
│  (K, rate, generator)    │  frame period, offset, polarity             │
│  interleaver type+params │  header: proven constant/alternating cols;  │
│  acceptance result:      │  undetermined cols + frames needed          │
│  corrected p, α, M,      │  randomizer applied (if any)                │
│  structural checks ✓/✗   │  payload boundary                           │
├──────────────────────────┴─────────────────────────────────────────────┤
│ DECISION                                                               │
│  DECODED | SIGNAL_NO_CODE | UNKNOWN        (+ capture-gate axis beside)│
├────────────────────────────────────────────────────────────────────────┤
│ WHY?                                                                   │
│  The exact evidence that caused the decision:                          │
│   · detection line p vs α · modulation consistency pair                │
│   · syndrome sign test p, corrected (p·M vs threshold)                 │
│   · structural checks (modulation / block length / soft path floor)    │
│   · runner-up margin · frames agreeing                                 │
│  and for refusals: the failing statistic + sufficiency verdict         │
│  (ACHIEVABLE: n more seconds | IMPOSSIBLE_IN_DOMAIN: reason)           │
│  + assumption ledger: what was searched, gated out, NOT SUPPORTED      │
└────────────────────────────────────────────────────────────────────────┘
```

## 2. Component mapping (everything is an existing component or a thin extension)

| Section | Source |
|---|---|
| CAPTURE | Existing CaptureGate + DataQuality components — FACT |
| LINK | Existing Characteristics component; **Doppler trajectory = new read-only sub-component** fed by the LINK EVIDENCE receipt section (DOPPLER #3) — when absent, the field says **NOT MEASURED**, never blank or "0" |
| CODING | Existing FEC/interleaver evidence renderers (hypothesis explorer data) — FACT |
| FRAME | Existing frame-map rendering (header columns, undetermined with frames-needed — FACT) |
| DECISION | Existing Verdict component — FACT |
| WHY? | Existing WhyPanel + WhatWouldProveIt + assumption ledger (CCSDS profile §3) |
| Receipt link | Existing ReceiptPanel — FACT |

The screen is thus **an arrangement over existing, tested components** plus one new read-only trajectory chart — deliberately no new inference, no new numbers, nothing that could disagree with the evidence pack.

## 3. Hard display rules

1. **Measured or labelled.** Every field shows either a measurement from the pack or an explicit NOT MEASURED / NOT ESTABLISHED / NOT SUPPORTED label. No dashes hiding missing capability, no zeroes faking measurements.
2. **No percentages that are not statistics.** Coverage, agreement rates and p-values are exact; "confidence" sliders do not exist.
3. **The refusal gets equal treatment.** A SIGNAL_NO_CODE/UNKNOWN screen is as complete as a DECODED one — the WHY? section is where refusals shine (what was tested, what failed, what would settle it).
4. **SIMULATED provenance repeats** in the header when the capture is synthetic, and exports carry it in the package.
5. **One source of truth.** The screen renders the same evidence pack the receipt hashes; it cannot show a number the receipt does not contain.

## 4. Interaction notes

- The trajectory chart's per-block points are the *measurements*; the fitted curve is clearly the model, and its declared classification rule is stated in a tooltip (the D2 rule), not silently applied.
- Clicking any WHY? line opens the corresponding evidence-chain entry (existing chain view) — no dead ends.
- The assumption ledger expands to show the full out-of-domain list (what was NOT tested), because that is what an operator must know before trusting a decode.

**END OF TELEMETRY FORENSICS DESIGN**
