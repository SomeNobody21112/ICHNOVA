# SATELLITE_PASS_REPLAY_DESIGN
**ICHNOVA · SIH26147 — Mission Replay: a SIMULATED progressive-evidence demonstrator (design only)**
**Status: DESIGN PROPOSAL (2026-09-25). Implements nothing.**

---

## 1. What Mission Replay is — and refuses to be

Mission Replay is a **demonstration view over a real engine analysis**: one genuine ICHNOVA run on a space-shaped capture, presented as if the evidence had accumulated over an 8–12 minute pass — by *revealing the already-computed evidence progressively*, timestamped into the pass timeline.

**Every screen carries the label:**

```
MISSION REPLAY — SIMULATED
-----------------------------
Pass duration: 08:42   (simulated)
Elevation: simulated
Doppler: simulated
Noise: simulated
Signal: synthetic telemetry
-----------------------------
```

This is not fake telemetry, not fake live data, not mission control (prohibited — SPACE_CLAIM_FIREWALL.md). The engine output, statistics, p-values and verdict are real; only the *presentation timeline* is simulated, and it says so.

## 2. Architecture

```
┌───────────────────────────────────────────────────────────┐
│ SPACE-BENCH generator (synthetic pass capture)            │
│  pass-shaped Doppler trajectory + noise + coded TM frames │
└──────────────┬────────────────────────────────────────────┘
               ↓ one real analysis
┌───────────────────────────────────────────────────────────┐
│ ICHNOVA engine (unchanged): full evidence pack + receipt  │
└──────────────┬────────────────────────────────────────────┘
               ↓ evidence → timeline projection (pure function)
┌───────────────────────────────────────────────────────────┐
│ REPLAY TIMELINE: engine diagnostics re-ordered onto a     │
│ simulated pass clock; degradation branch from severity    │
└──────────────┬────────────────────────────────────────────┘
               ↓
┌───────────────────────────────────────────────────────────┐
│ REPLAY VIEW (frontend): SIMULATED banner + timeline +     │
│ live evidence cards + final verdict + receipt link        │
└───────────────────────────────────────────────────────────┘
```

- **Projection is a pure function** over the existing evidence pack (which already orders detection → sps → modulation → CFO → FEC → frame → verdict — FACT, pipeline result keys) mapping each diagnostic to a simulated wall-clock offset. It can be unit-tested with no engine and no UI.
- **Degradation branch**: a second capture class where severity rises through the pass; the projection emits the mid-pass transition (DECODED → SIGNAL_NO_CODE/UNKNOWN) from a real run of that class — never a scripted verdict.

## 3. The two demonstrated timelines (expected shapes, from real capability)

**Success path (a real DECODED run, revealed progressively):**
```
00:00  SIGNAL ACQUIRED            (capture gate GOOD — real quality module)
00:04  CARRIER DETECTED           (detection_log10_p vs α — real number)
00:07  SYMBOL-RATE CANDIDATE      (sps table — real)
00:11  MODULATION CANDIDATE       (modulation consistency — real)
00:15  CODING CANDIDATE           (syndrome sign test p-value — real)
00:21  FRAME STRUCTURE VERIFIED   (ASM/frame map — real)
00:26  PAYLOAD VERIFIED           (structural checks — real)
00:27  DECODED                    (multi-hypothesis correction reported — real)
```

**Degradation path (a real refusal run, revealed progressively):**
```
00:00  SIGNAL ACQUIRED
00:04  CARRIER DETECTED
00:09  SYMBOL-RATE CANDIDATE
00:16  CODING: evidence insufficient   (real bar not met — real numbers shown)
00:22  DEGRADATION: drift increased    (simulated pass geometry, real measured trajectory)
00:26  SIGNAL_NO_CODE / UNKNOWN        (real refusal + sufficiency reason)
       + "what would settle it"        (real ACHIEVABLE/IMPOSSIBLE_IN_DOMAIN)
```

Both shapes come from actual engine behaviour (the progressive order mirrors the engine's own pipeline order — FACT); nothing is invented to look good.

## 4. Components

| Component | Status | Notes |
|---|---|---|
| Pass-shaped synthetic capture generator | `NEW` (shares SPACE-BENCH family D/E generator) | SIMULATED-labelled |
| Evidence-pack → timeline projection | `NEW` (pure function + tests) | No engine change |
| Replay view (frontend page/panel) | `NEW` | Renders existing components (verdict, evidence chain, receipt) on a clock |
| SIMULATED banner + provenance tag | `NEW` (UI only) | Mandatory, non-dismissable; recorded in receipt provenance as SIMULATED |
| Engine / pipeline changes | **NONE** | Replay is read-only over evidence packs |

## 5. Honesty rules specific to replay

1. The clock is simulated and labelled; the evidence timestamps are presentation, never stored as capture history.
2. A replay of a refusal must show the refusal as prominently as a decode would show its verdict — the degradation path is a first-class demo, not an error case.
3. The receipt of the underlying run remains verifiable independently of the replay view (the replay adds no evidence of its own).
4. "Elevation/Doppler: simulated" is not decoration — it repeats on exports and in the demo script (SPACE_DEMO_SCRIPT.md).

**END OF MISSION REPLAY DESIGN**
