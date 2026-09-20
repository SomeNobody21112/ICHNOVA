# ICHNOVA — launch narrative, composition brief and share copy

Source material for a launch video or a submission reel. **Every claim here traces to
`FINAL_RELEASE_FREEZE.md` §16 (safe claims); nothing from §17 (prohibited) appears.**

If this is fed to a generator such as `brag`, use it as the script rather than letting the tool infer
claims from the source tree — an inferred pitch reaches for *AI-powered*, *production-ready* and an
accuracy percentage, all three banned by Constitution §3 and each one contradicted by the reports
sitting beside it.

**Tone:** technical, understated, evidence-first. The project's whole argument is restraint, so a
hype reel would undercut the product it is advertising.

---

## The one sentence

> ICHNOVA reads a radio recording it was told nothing about, works out how it was built — and says so
> only when it can prove it.

## The 75-second script

Twelve shots. Every asset is committed to the repository; nothing needs a network.

| # | Time | On screen | Voice / caption |
|---|---|---|---|
| 1 | 0:00–0:06 | Waterfall of an unidentified capture | "This is a recording. We don't know what's in it." |
| 2 | 0:06–0:14 | Upload → analysis running | "No station, no code, no sample rate given. The engine is told nothing." |
| 3 | 0:14–0:22 | `BENCH-QPSK-K7` → DECODED | "It recovers the modulation, the error-correcting code and the interleaver." |
| 4 | 0:22–0:30 | Evidence chain, statistical validation panel | "Fifty thousand hypotheses were tested. The bar moves to account for every one of them." |
| 5 | 0:30–0:36 | Accepted p-value beside the corrected threshold | "It cleared the moved bar. That is why it is allowed to answer." |
| 6 | 0:36–0:44 | `BENCH-SHORT-K7` → UNKNOWN | "Same kind of transmission. Shorter capture. Now watch." |
| 7 | 0:44–0:52 | "What would prove it?" → IMPOSSIBLE_IN_DOMAIN | "It refuses — and tells you more signal would not help. Thirty-two coded bits can never clear the bar." |
| 8 | 0:52–1:00 | JJY replay, GPS comparison | "A Japanese time station, decoded blind, agreeing with the receiver's GPS clock to two milliseconds." |
| 9 | 1:00–1:06 | WWVB replay → SIGNAL_NO_CODE | "Same engine, same night, different station. It found structure and refused to state a time." |
| 10 | 1:06–1:14 | Verify receipt → chain intact | "Every decision is hash-chained. Your browser recomputes it. You do not have to trust the server." |
| 11 | 1:14–1:20 | Tampered ledger → verification fails, entry named | "Alter one record and it names the record." |
| 12 | 1:20–1:25 | Limitations card | "No field deployment. No accuracy percentage. It tells you what it has not proven." |

**Closing line:** *"Most systems answer. This one also knows when not to."*

## Composition brief

- **Palette:** the console's own dark theme. No stock footage, no synthetic "cyber" imagery, no
  rotating globes. Screen recordings only.
- **Pace:** slow enough to read the numbers. The numbers *are* the product — if a viewer cannot read
  the p-value beside the threshold, shot 5 is wasted.
- **Text on screen:** one figure per shot, large. `0 / 120 false accepts` · `+1.9 ms` ·
  `50,916 hypotheses`.
- **No music bed under the refusal shots** (6, 7, 9). Those carry the argument; let them sit.
- **Never show:** the simulated monitoring-network pages, the Salesforce panel, or anything labelled
  SIMULATED without its label visible in frame.

## Share copy

**Short (X / status):**

> We built a receiver that refuses to guess. Given a radio recording and nothing else, ICHNOVA
> identifies the modulation, error-correcting code and interleaver — and returns UNKNOWN when the
> evidence does not reach the bar. 0 false accepts across 120 sealed non-catalogue signals. SIH26147.

**Medium (LinkedIn):**

> Most signal tools always return an answer. We spent this project making ours capable of refusing.
>
> ICHNOVA analyses `.IQ` and `.wav` recordings blind — no station, no code, no sample rate supplied —
> and reports DECODED, SIGNAL_NO_CODE or UNKNOWN. An answer is emitted only when an exact statistical
> test clears a bar corrected for every hypothesis tried, sometimes 68,000 of them on one capture.
>
> On a sealed benchmark with criteria committed before the first run: 9 of 9 pre-registered criteria
> passed, with 0 false accepts across 120 non-catalogue signals. On real radio: government time
> signals from NICT, PTB, NPL and NIST decoded blind and checked against the receiver's own GPS
> clock, agreeing to between 2 and 23 milliseconds. On one of them — WWVB — it refused to state a
> time, and the refusal was correct.
>
> Every decision is hash-chained into a receipt the browser re-verifies without trusting our server.
> Degrade a capture and the engine moves toward refusal rather than toward a wrong answer: 180
> controlled runs, zero wrong decodes.
>
> An independent Smart India Hackathon prototype for problem statement SIH26147. Not an official
> Government of India system. No field deployment, and no general accuracy figure is claimed — both
> stated in the repository.

**The line to lead with, in any format:**

> "0 false accepts on 120 sealed non-catalogue signals — and it tells you when it cannot tell."

## Claim check

Swept against `FINAL_RELEASE_FREEZE.md` §17. This document contains no instance of *AI-powered*,
*real-time*, *universal*, *accurate*, *guaranteed*, *first*, *novel*, *patented*, *production-ready*,
*field-deployed*, *official government system*, any competitor comparison, or any general accuracy
percentage. Every number carries the dataset it came from.

## If you render this with `brag`

Requirements absent on the development machine at freeze: **FFmpeg** (and no `winget` with which to
install it), a **Hyperframes** account for rendering, and memory headroom — 1.5 GB free of 7.7 GB,
where video encoding is the workload most likely to exhaust it. The render was therefore not
attempted. Use this script as the input, and review any generated copy against §17 before it enters
the repository.
