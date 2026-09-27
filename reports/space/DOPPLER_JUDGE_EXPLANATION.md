# DOPPLER_JUDGE_EXPLANATION
**ICHNOVA · SIH26147 — the Doppler result, explained for a technical judge**
**Status: PRESENTATION (2026-09-25). Every number here is measured and traceable to `DOPPLER_EXPERIMENT_RESULTS.md`.**

**This document does not claim the failure is solved. It is not solved.**

---

## PROBLEM

What happens when a blind RF inference system — one that has been validated on a sealed benchmark and never lies about signal structure — is exposed to a carrier whose **frequency changes during the capture**?

That is the defining condition of a spacecraft link. Every previous ICHNOVA measurement was taken with a carrier that holds still within the capture. Whether those results transfer to a moving carrier had never been measured in this project, at any point. So we measured it.

## EXPERIMENT

**192 controlled, deterministic vectors.** One transmitter throughout: a continuous rate-½ K=7 convolutional stream, BPSK — chosen because it is the *best*-evidenced case in our sealed benchmark (16/16 recall at Es/N0 ≥ 6 dB), so any degradation is attributable to the carrier rather than to a weak baseline.

Four carrier trajectories: `zero` and `static` (controls), `linear` ramp (control 2 — the drift class the engine was already hardened against), and `pass`, a bounded S-curve — **controlled synthetic, never a real satellite pass**. Crossed with four severities scaled to the engine's own declared search bound, three noise levels, two capture lengths straddling the engine's tracking threshold, and two repetitions.

**The acceptance criteria were written and committed before the first vector existed** (`eval/space_doppler_criteria.json`). The dataset regenerates byte-identically from its seeds. One run, published whatever it said.

## RESULT

| | captures | correct payload | refused | **wrong payload** |
|---|---:|---:|---:|---:|
| **Static / zero carrier (control)** | 96 | 80 | 16 | **0** |
| **Time-varying carrier (treatment)** | 96 | 11 | 31 | **54 (56.3%)** |

In **54 of 96** time-varying captures the engine said `DECODED`, named the code correctly — and handed over a payload that was **not** the transmitted one. Median bit error rate of those payloads: **0.320**. The verdict carried no indication that anything was wrong.

Noise was not the cause: the wrong payloads are flat across the SNR range (18 at 12 dB, 17 at 9 dB, 19 at 6 dB). They cluster *inside* the offset range the engine claims to handle; beyond that range it refuses cleanly (35 of 48 out-of-bound captures refused).

## CONTROL

**0 wrong payloads in 96 static-carrier captures.** The `zero` trajectory decoded 48/48 correctly across every severity and noise level. Every control refusal was an out-of-bound cell where refusal was the pre-registered expectation.

This is what makes the result interpretable rather than anecdotal: the same generator, seeds, code path and scoring function produce perfect results whenever the carrier holds still. The failure is caused by the one factor we varied.

## IMPORTANT — what did *not* fail

**0 wrong structures across all 192 captures.**

Every one of the 145 `DECODED` verdicts named the true code family. Every one reported the true modulation. The machinery that exists to prevent false claims — exact syndrome sign tests under family-wise error control at α = 0.01 — **held completely**, at carrier drift rates up to **375×** anything the engine had previously been tested against.

So the accurate statement is not "the engine made 54 false structural claims". It is: **the engine made 0 false structural claims and 54 unreliable payloads.** We insist on the distinction because it localises the failure to one layer — and because overstating our own failure would be as dishonest as hiding it.

Also unchanged: 185 tests pass (178 pre-existing, none altered, plus 7 new), the original sealed benchmark still scores 30/30 with 0 false accepts, and no production file was modified.

## INTERPRETATION

The **structural test remains strong**; **payload reliability breaks** under the tested time-varying-carrier conditions.

We can say where the failure appears and where it does not. Detection, modulation inference, symbol-rate inference and code identification all held. The failure surfaces at the **Viterbi/payload stage of an already-accepted, correct hypothesis** — and nothing in the verdict path tests whether that payload is trustworthy. A parity-based structural test answers "is this code present?"; it was never designed to answer "are these bits right?". For a code whose generators have odd weight, the complement of a codeword is itself a codeword — so a stream can be overwhelming statistical evidence of the right code and still decode to the wrong bits.

**We are not claiming to know the exact mechanism. ROOT CAUSE NOT ESTABLISHED.** Six candidates are documented, each with the observation that would confirm or kill it (`DOPPLER_FAILURE_ANALYSIS.md` §7). Naming a cause we had not proven would be the same class of error as tuning a threshold: a story that makes the project look finished.

## RESPONSE

What we did **not** do:

- We did not tune a threshold — not the acceptance bar, the family weights, the carrier search bound, the tracking threshold, or the agreement floor.
- We did not re-run the experiment with easier criteria.
- We did not soften the documentation or quietly drop Doppler from the story — we replaced the claim with the measured limitation.
- We did not start building space features on top of an unvalidated capability.

What we did:

1. **Froze the result.** The 192-vector dataset, its manifest, its pre-registered criteria and its outcome are sealed historical evidence. Future work uses a new namespace, new criteria and a new experiment ID.
2. **Documented the boundary precisely.** A `DECODED` verdict may be relied on for *what the signal is*; for *what the signal says*, only when the carrier is static within the capture. That sentence is now in the evidence matrix, the claim firewall and the positioning document, and the forbidden-claims list grew.
3. **Designed the next experiment** (`SPACE-DOPPLER-MECH-01`) to identify the mechanism — not to pass. Its decisive comparison is ideal ground-truth carrier correction versus estimated correction versus none, with the meaning of every outcome written down in advance, including the outcome "still not established".
4. **Left the production engine untouched**, and filed the two changes we think may be needed as explicit, unapproved requests with their risks stated — including the risk that the safer one costs decode recall we currently have.

## WHY THIS IS THE RIGHT ANSWER TO A FAILED EXPERIMENT

An evidence-first system is only worth something if its evidence can come back negative. Ours did, on the capability that would have been most impressive to claim — and the response is a narrower claim, a mapped boundary, and a sharper next question.

The progression we follow, without skipping steps:

```
hypothesis → controlled experiment → failure → reproduction → boundary identification
   → mechanism experiment → only then remediation → new sealed validation
```

We are at **boundary identification**, moving to **mechanism experiment**. We are not at remediation, and we will not present as though we were.

**One honest sentence about ICHNOVA and space, today:** ICHNOVA's blind-inference core and refusal discipline are validated within its documented benchmark scope, and controlled time-varying-carrier testing has identified a measured limitation in payload reliability. Anything stronger is not supported by our evidence — and we would rather be the team that found the limit than the team that presented past it.

**END OF JUDGE EXPLANATION**
