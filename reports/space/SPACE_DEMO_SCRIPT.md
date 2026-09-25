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
| 4:45–5:30 | **The Doppler experiment (if results exist)** | Show trajectory extraction: measured carrier drift vs injected truth; static-vs-S-curve classification; "0 wrong payloads across the sweep" — read from SPACE_BENCH_RESULTS.md **whatever it actually says** | Label every number BENCHMARK; if results are pending, show the pre-registered spec instead and say exactly that |
| 5:30–6:15 | **CCSDS profile + assumption ledger** | Open the ledger on the decoded run: what was searched, what was gated out, what is NOT SUPPORTED (block-LDPC TM, turbo, packet semantics). "This screen cannot claim more than was tested — that is the point" | The trust centerpiece |
| 6:15–6:45 | **Receipt verification** | Export the space evidence package; verify the SHA-256 chain with the CLI; optionally flip one byte and show it fail | "Verifiable without trusting us" |
| 6:45–7:00 | **Close** | The narrowed positioning sentence (POSITIONING §2): "an evidence-first ground-segment analysis layer for partially unknown spacecraft RF links — validated at bench conditions, honestly labelled everywhere else" | Never claim operational anything |

## Judge-question armour (30-second answers)

- **"Is this real satellite data?"** → "No. Synthetic, labelled SIMULATED. The engine output on it is real, and the real-capture story to date is terrestrial — time codes, FSK, broadcast carriers, one live SDR capture. A real spacecraft-resembling capture is on the roadmap, not claimed."
- **"Why not just use gr-satellites?"** → "Different problem. It needs the satellite's YAML — known parameters. Ours is for when you don't have them, and it refuses when evidence is short. We'd feed each other."
- **"What if a wrong hypothesis looks better?"** → "That's the adversarial family. There is a measured precedent on our own 8PSK alias experiment — we published it and gated the feature off. The structural checks exist because of failures like that, documented, not hidden."
- **"Is the ML in the room?"** → "There is no ML. Exact binomial tests and spectral nulls. That is why every number is defensible."
- **"What's validated vs not?"** → "Bench conditions: sealed. Space conditions: the pre-registered SPACE-BENCH — results are what they are. Doppler tracking exists; its space-condition limits are exactly what the experiment measures. Everything unproven is labelled."

## Hard requirements for whoever runs the demo

1. SIMULATED banner visible during any replay; never dismissed or cropped.
2. Any sealed number is introduced with the word "benchmark".
3. If asked about ISRO/agency involvement: "None. Independent prototype. Their published ground-segment structure is public design inspiration."
4. Never show a screen that doesn't exist yet; if a P1 feature isn't built by demo day, that beat is dropped, not faked.

**END OF DEMO SCRIPT**
