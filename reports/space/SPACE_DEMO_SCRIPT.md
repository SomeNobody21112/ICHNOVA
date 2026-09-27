# SPACE_DEMO_SCRIPT
**ICHNOVA · SIH26147 — 5–7 minute judge demonstration (script; demo assets built per SPACE_ENGINEERING_ROADMAP.md P0/P1)**

---

## Timing plan (6:30 target)

| Clock | Beat | What happens | Honesty beat |
|---|---|---|---|
| 0:00–0:45 | **The problem** | "When a ground station records an unknown RF signal, the hard question is not *can we decode it* — it is *should anyone believe a decode*." Show the three-outcome model: DECODED / SIGNAL_NO_CODE / UNKNOWN | Establishes the thesis in one line |
| 0:45–1:30 | **The evidence principle** | Open any engine record: point at the p-value, the hypotheses-tested count M, the Bonferroni-corrected threshold, the structural checks. "Every number on this screen is a measurement, and the receipt is hash-chained" | Say "bench" when citing sealed numbers |
| 1:30–2:15 | **Why space** | LEO Doppler numbers (±5 kHz at S-band, ~32 Hz/s — sourced). "A pass makes the carrier *move*. Most decoders need the satellite's parameters up front. What happens when nobody can give them to you?" | Facts from SPACE_RESEARCH_LANDSCAPE.md sources |
| 2:15–3:30 | **Mission Replay — success path** | Launch the SIMULATED replay: banner visible. Watch evidence accumulate: acquired → carrier → symbol rate → modulation → coding → frames → DECODED at 00:27. Pause at 00:15: "everything shown is already statistically verified — the timeline is simulated, the evidence is not" | **SIMULATED banner on screen the whole time** |
| 3:30–4:45 | **Mission Replay — degradation path** | Second replay: severity rises mid-pass; the system migrates to SIGNAL_NO_CODE/UNKNOWN *with the measured reason*: which statistic refused, and what capture would settle it (ACHIEVABLE / IMPOSSIBLE_IN_DOMAIN) | The refusal is the hero moment, not a failure |
| 4:45–5:45 | **The Doppler experiment — and what it cost us** | Read the measured result from `DOPPLER_EXPERIMENT_RESULTS.md`: on 192 controlled synthetic vectors, **structure stayed correct in all 192 — 0 wrong structures** — while the published **payload was wrong in 54 of 96** treated time-varying-carrier captures, against **0 of 96** static controls. Then the honest sequel, in four sentences: the mechanism is residual carrier error the front end does not model (`DOPPLER_MECHANISM_RESULTS.md`); we built the obvious fix, a blind carrier pre-correction; it removed most of the payload failure **and** cost 8 of 30 bench-v1 decodes, one of bench-v2's nine criteria, 41 of 128 null-set catalogue decodes, and manufactured a CCSDS LDPC claim out of an idle carrier; so we **did not integrate it** (`CARRIER_ESTIMATOR_RESULTS.md`). Close on what the engine now *reports*: whether its own phase-tracking unwrap assumption was stressed during the capture — evidence, consulted by no decision (`TRACK_VALIDITY_RESULTS.md`) | Label every number BENCHMARK. Say the failure number out loud **before** the fix. **Do not claim trajectory extraction, static-vs-time-varying classification, or carrier-trajectory measurement — all three are NOT ESTABLISHED.** The decode verdict is scoped to a carrier that is static within the capture |
| 5:45–6:15 | **CCSDS profile + assumption ledger** | Open the ledger on the decoded run: what was searched, what was gated out, what is NOT SUPPORTED (block-LDPC TM, turbo, packet semantics). "This screen cannot claim more than was tested — that is the point" | The trust centerpiece |
| 6:15–6:45 | **Receipt verification** | Export the space evidence package; verify the SHA-256 chain with the CLI; optionally flip one byte and show it fail | "Verifiable without trusting us" |
| 6:45–7:00 | **Close** | The narrowed positioning sentence (POSITIONING §2), **with both halves — dropping the second is a false claim by omission** (CLAIM_FIREWALL §2a): "an evidence-first ground-segment RF analysis layer: its blind inference and refusal are validated at documented benchmark conditions for a carrier that is static within the capture, and controlled time-varying-carrier testing identified a measured limitation in payload reliability" | Never claim operational anything. Never state the first half alone |

## Judge-question armour (30-second answers)

- **"Is this real satellite data?"** → "No. Synthetic, labelled SIMULATED. The engine output on it is real, and the real-capture story to date is terrestrial — time codes, FSK, broadcast carriers, one live SDR capture. A real spacecraft-resembling capture is on the roadmap, not claimed."
- **"Why not just use gr-satellites?"** → "Different problem. It needs the satellite's YAML — known parameters. Ours is for when you don't have them, and it refuses when evidence is short. We'd feed each other."
- **"What if a wrong hypothesis looks better?"** → "That's the adversarial family. There is a measured precedent on our own 8PSK alias experiment — we published it and gated the feature off. The structural checks exist because of failures like that, documented, not hidden."
- **"Is the ML in the room?"** → "There is no ML. Exact binomial tests and spectral nulls. That is why every number is defensible."
- **"What's validated vs not?"** → "Bench conditions: sealed, for a carrier that is static within the capture. Time-varying carrier: measured, and it is a limitation — 54 of 96 treated captures published a wrong payload beneath a correct structure. A phase tracker exists and it is what produces the correct time-varying decodes we do get, but it fails past a bound written into its own code, and the engine now reports when that bound was approached. Real spacecraft RF, orbital modelling and carrier-trajectory measurement: not established, no capture, no model. Everything unproven is labelled."
- **"So did you fix the Doppler problem?"** → "No, and we can show you why. The obvious fix worked on Doppler and broke things that already worked — 8 of 30 bench-v1 decodes lost, and it invented a CCSDS LDPC claim from an idle carrier. We measured it, wrote it up, and rejected it. That decision is the result."

## Hard requirements for whoever runs the demo

1. SIMULATED banner visible during any replay; never dismissed or cropped.
2. Any sealed number is introduced with the word "benchmark".
3. If asked about ISRO/agency involvement: "None. Independent prototype. Their published ground-segment structure is public design inspiration."
4. Never show a screen that doesn't exist yet; if a P1 feature isn't built by demo day, that beat is dropped, not faked. **As of 2026-09-27 the Space UI and Mission Replay are NOT BUILT** (`SPACE_ENGINEERING_STATUS.md`), so the 2:15–4:45 replay beats are conditional on that work landing; if it has not, drop them and give the time to the 4:45 evidence beat, which needs no UI.
5. The Doppler beat states the measured failure (54 of 96) before it states anything that was attempted about it. No beat may claim trajectory extraction, static-vs-time-varying classification, or carrier-trajectory measurement.

**END OF DEMO SCRIPT**
