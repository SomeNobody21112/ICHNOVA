# SPACE_EVIDENCE_RECEIPT_DESIGN
**ICHNOVA · SIH26147 — portable evidence package for space-link analyses (design only)**
**Status: DESIGN PROPOSAL (2026-09-25). Extends the existing receipt architecture; changes nothing about chain semantics.**

---

## 1. Foundation (what exists — FACT)

ICHNOVA already produces **SHA-256 hash-chained evidence receipts** (`src/receipt.py`), verifiable by CLI (`server/verify_receipt.py`) and in-browser, both demonstrated against a real tamper (Constitution §22 — FACT). Receipts record the analysis parameters, hypothesis counts, statistical results and the decision, bound into the chain. The space extension is **additive fields + packaging**, not a new trust model.

## 2. The space-link package

```
MISSION / CAPTURE ID            (e.g. MISSION-REPLAY-0007 / real capture UUID)
  ↓ CAPTURE PROVENANCE          station identity (or "SIMULATED"), antenna/SDR metadata when real,
                                fs + fs_source (declared/wav/inferred/relative_only/unavailable — FACT enum),
                                capture-quality summary (gate result, never merged into verdict)
  ↓ ANALYSIS PARAMETERS         engine version/commit, profile flag (SPACE MODE on/off),
                                searched domains (modulations, sps range, CFO bound, β, catalogue revision)
  ↓ HYPOTHESIS LIST             the hypothesis domain actually enumerated per family (M values reported as-run)
  ↓ REJECTED HYPOTHESES         top-N rejected with their p-values and structural rejections
  ↓ ACCEPTED HYPOTHESES         the accepted hypothesis with its corrected p-value and structural checks
  ↓ STATISTICAL TESTS           detection line test, modulation consistency pair, syndrome sign test,
                                frame marker/window tests, correction arithmetic (p·M vs α) — as-run numbers
  ↓ FRAME EVIDENCE              sync source (ASM 32/64/blind), period, offset, polarity,
                                header columns proven constant/alternating, undetermined columns + frames-needed
  ↓ [SPACE EXTENSION] LINK EVIDENCE
                                measured carrier trajectory (per-block estimates or fitted params + residuals),
                                static-vs-time-varying classification + declared model-comparison rule,
                                capture-quality axis summary
  ↓ PAYLOAD VERIFICATION        structural checks (modulation, block length, soft-path floor),
                                coverage, runner-up margin, payload digest
  ↓ FINAL DECISION              DECODED | SIGNAL_NO_CODE | UNKNOWN (+ refusal reason + sufficiency verdict)
  ↓ CRYPTOGRAPHIC RECEIPT       SHA-256 chain entry (existing semantics, one new optional section)
```

## 3. Design rules

| Rule | Why |
|---|---|
| Chain semantics unchanged: new fields are a namespaced section hashed like any other | The verifier chain must stay byte-compatible in spirit and independently verifiable — existing receipts keep verifying |
| `SIMULATED` is a provenance value carried **inside** the package, not a UI decoration | An exported space package must not be mistakable for a real-station capture — firewall requirement |
| Trajectory evidence stores *measurements* (block phase/frequency estimates + residuals), not fitted beauties | Another operator must be able to re-derive D1/D2 conclusions without trusting our fit (DOPPLER D8) |
| The assumption ledger (CCSDS_TELEMETRY_PROFILE.md §3) is included verbatim | Answers "which assumptions were required" from the package alone |
| Rejected hypotheses included (top-N), not just the winner | Independent verification means seeing what lost, and by how much |
| No arbitrary confidence numbers | Percentages that are not exact statistics are prohibited (firewall); the package carries p-values, thresholds, M, and structural booleans |

## 4. Independent verification requirement

The package must let another operator answer, **without trusting ICHNOVA**:
1. What was observed (capture provenance, quality, fs provenance)?
2. What exactly was tested (domains, M, thresholds)?
3. What was rejected, with what evidence?
4. What was accepted, under which correction, passing which structural checks?
5. What was *not* tested (out-of-domain ledger)?
6. Is the package intact (chain verification)?

Items 1–4 and 6 are satisfied today by existing receipts + evidence packs (FACT); item 5 is the assumption ledger (new, presentation-level); the LINK EVIDENCE section is the only substantive new data, sourced from state the engine already computes internally during tracked analyses (FACT — `_track_phase` runs and its per-block phase exists; today it is discarded after equalisation).

## 5. Test strategy for the extension (when implemented, post-gate)

- Chain regression: old receipts still verify byte-for-byte (existing tests extended).
- Round-trip: package → CLI verifier → all sections present and consistent with the evidence pack.
- Tamper: flip one trajectory value → verification fails (mirrors the existing tamper demonstration).
- Provenance: a SIMULATED run's package is mechanically distinguishable from a LIVE one.

**END OF SPACE EVIDENCE RECEIPT DESIGN**
