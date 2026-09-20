# ICHNOVA — Domination readiness audit

Independent Smart India Hackathon prototype for problem statement **SIH26147**.
**Not an official Government of India system.**

Audited 2026-09-20 against Constitution **v2.5.4** and the repository as committed. Historical pass
reports were read as history, never as current-state evidence.

**The verdict, up front: stop major engineering. The binding constraint on this project is no longer
capability — it is operator evidence and rehearsal.**

---

# PHASE 1 — Current state audit

## 1.1 Genuinely complete

| Capability | Evidence | Action |
|---|---|---|
| Blind detection, symbol rate, CFO, PSK/FSK demodulation | `tests/test_core.py`, bench-v2 | None |
| Convolutional FEC K=3/5/7 + Viterbi, exact parity sign test | bench-v2, 175 tests | None |
| Four interleaver families — block, diagonal, Forney convolutional, 3GPP QPP | In default search; `test_catalogue.py` | None |
| CCSDS RS (255,223)/(255,239), TC LDPC (128,64), full concatenated chain | bench-v2 10/12, 8/8; `test_families.py` | None |
| Frame sync / bit-stream correlation on ASM with header-payload map | bench-v2 5/10 blind framed | None |
| Sample-rate provenance, no invented default | `fs_source` on every result | None |
| Capture quality gate, separate from verdict | `src/quality.py`, tested never to alter a verdict | None |
| Evidence sufficiency with four honest verdicts | `src/sufficiency.py` | None |
| Evidence receipts, SHA-256 chain, CLI + browser verifiers | Both driven against a real tamper | None |
| Authentication, RBAC, rate limiting, upload validation | 0 of 2,709 forged signatures accepted | None |
| Signal-source registry with provenance, licence, freshness | `server/sources.py`, §9.13 | None |
| One writer per results directory | `server/store_lock.py`, two-process test, §9.12 | None |
| Operator console, 15 routes, two themes | 120 pages measured, 4 viewports | None |

## 1.2 Genuinely validated (measured, or protected by a failing-if-broken test)

- **bench-v2 sealed**: 430 files, criteria committed before the run, one logged run, **9/9 pass**.
  0/120 false accepts on non-catalogue signals; 3/310 wrong structure or payload = 0.97%.
- **Null set**: 0/900 false accepts on non-catalogue files; 0/450 wrong decodes on coded files.
- **Real signals**: JJY, DCF77, MSF, WWV decoded blind, GPS agreement +1.9 to +23.4 ms; DDH47 ITA2
  text naming its own callsign; AIR medium wave 5/5 carriers matched to the official list; **WWVB
  time refused** — the refusal was correct.
- **Live chain, 2026-09-20**: 720 kHz, 144,384 samples, GPS-timed → quality GOOD → carrier 61.3 dB
  above noise → **SIGNAL_NO_CODE** → receipt verifies.
- **175 tests pass**; frontend typecheck and build clean; Python and Node dependency scans clean.

## 1.3 Implemented but NOT validated

| Item | Why not validated | Action |
|---|---|---|
| Salesforce case hand-off | Never connected to a real org. Outbox, idempotency, retry, dead-letter tested against a stand-in only | **None — leave it** |
| TLS reverse proxy | `deploy/nginx.conf` consistent with the app, never exercised: no Docker daemon, no native nginx | None before SIH |
| Container image | `Dockerfile` present; **never built or run on this machine** | Optional, low value |
| Container base-image CVEs | No scanner available (`trivy`, `grype`, `pip-audit` all absent) | Blocked |
| Google sign-in | Prototype path: token decoded in the browser, **not verified server-side**. Already labelled EXPERIMENTAL in the UI | None |

## 1.4 Experimental

| Item | Status |
|---|---|
| 8PSK / 16-QAM | **OFF by default, measured.** 0/100 8PSK decoded, search ×21.8, one BPSK capture decoded 40% wrong via a structural alias. Guarded by negative tests |
| General header/payload search beyond catalogue markers | EXPERIMENTAL in the coverage table |
| Signal-genome similarity | EXPERIMENTAL tag in the console |
| Adaptive/code-aided refinement | Research module, **not enabled** |

## 1.5 Explicitly NOT established

Field deployment · external penetration test · container base-image CVEs · TLS serving live traffic ·
two hosts on one shared filesystem · general accuracy figure · blind absolute sample rate (physically
unrecoverable) · station identity of the 2026-09-20 live capture (nearest receiver 2,135 km).

## 1.6 Contradictions found — all resolved today

| Source | Claim | Status |
|---|---|---|
| `SIH26147_CURRENT_STATE.md` | "Constitution v2.4 · branch `baseline-hardening` · 30 tests" | **FIXED** — rewritten to v2.5.4, `sih-readiness`, 175 tests |
| `SIH26147_PROJECT_CONSTITUTION.md` | No mention of `store_lock`, TLS deployment, forwarded-header trust or source freshness, though all were committed | **FIXED** — amendment v2.5.4 added §9.12, §9.13, limitations 8 and 8a |
| `COMPLETION_AND_UVP.md` | "`main` = `08ee9a7`" | **FIXED** — four commits stale |
| `FINAL_FEATURE_AUDIT.md` | Presented as wholly measured at `4435908`, but rows 14–15 amended later | **FIXED** — provenance note added |

## 1.7 Stale claims in current-facing UI, docs or code

**None found.** Swept `frontend/src` and the current-facing documents for *real-time*, *AI-powered*,
*production-ready*, *field-deployed*, *guaranteed*, *patented*, *100% accurate*, *industry-leading*.
Zero hits. The only match anywhere is the claim-audit section of `FINAL_VERIFICATION_PASS.md`, which
lists the terms in order to forbid them.

The console never states Salesforce is connected: every reference is conditional on
`CONFIGURED`, and the unconfigured path says *"nothing has been sent"*.

---

# PHASE 2 — Should we engineer more?

**Classification key:** A = must fix before SIH · B = high-value validation · C = nice to have ·
D = do not build now · E = blocked / wait for evidence.

| # | Item | Class | Reasoning |
|---|---|---|---|
| 1 | **Detection calibration (4.2% → 1%)** | **D** | Real limitation, honestly documented. But retuning the detection threshold *after* a sealed run changes decisions on the sealed set — §9.6 forbids tuning on it, and doing so would cost the one thing bench-v2 buys: a pre-registered, single-run result. **Document, do not touch.** |
| 2 | **Es/N0 waterfall** | **B** | Pure measurement on data that already exists (train + null set). Answers the jury's most likely quantitative question — *how does it degrade?* No new code paths, no new failure modes. **Do it.** |
| 3 | **Modulation classifier before code search** | **D** | This is the correct long-term fix for QAM, and it is weeks of work with a direct false-accept risk. The current position — off by default, with the measurement that justifies it — is *stronger* in front of a jury than a rushed classifier. |
| 4 | **Cyclic-CAF** | **D** | Research-frontier item. No current failure demands it. |
| 5 | **SAGE-Lite** | **D** | Same. |
| 6 | **More modulations** | **D** | §9.11 forbids feature-count competition. We cannot demo the ones we have gated. |
| 7 | **More FEC families** | **D** | Catalogue already spans convolutional, RS, LDPC and concatenated. Marginal jury value ≈ 0. |
| 8 | **More interleavers** | **D** | Four families already. Nothing is failing for want of a fifth. |
| 9 | **CNN / learned models** | **D — actively harmful** | The thesis is *exact tests with a stated false-accept bound*. A learned model cannot produce a p-value, would break §9.4 auditability, and hands the jury "how do you know it isn't hallucinating?" — the one question we currently answer perfectly. |
| 10 | **Geolocation / TDOA** | **D** | Needs synchronised multi-receiver capture we do not have. Would be an unvalidated claim on day one. |
| 11 | **SDR hardware integration** | **D** | Public KiwiSDR already supplies real RF and real GPS timing. Hardware adds procurement and demo risk for no new evidence class. |
| 12 | **Cloud scaling** | **D** | Directly contradicts §9.12 (one writer) and §9.2 (air-gap capable). Would require replacing the evidence store. |
| 13 | **Salesforce live integration** | **E** | Blocked without a real org. Connecting one days before submission risks the worst possible failure — a sync that appears to work and does not. Current state is defensible: implemented, honest, never claimed. |
| 14 | **Mobile application** | **D** | Console is an operations tool. A phone app is a second product. |
| 15 | **More UI pages** | **D** | 15 routes already exceed what a 7-minute demo can show. |
| 16 | **More monitoring features** | **D** | Monitoring-network data is simulated and labelled. Adding more simulation increases the surface a jury can attack. |
| 17 | **Field deployment** | **E** | Cannot be achieved honestly before the deadline. **The affordable proxy is Phase 3** — two independent operators on the real application. |

**Nothing is class A.** That is the finding: no engineering item is blocking submission.

**Two items are class B**, and both are *validation*, not features: the Es/N0 waterfall (Phase 4,
E1) and the operator study (Phase 3).

---

# PHASE 3 — Operator / field validation protocol

**Purpose:** convert "operator value" from NOT ESTABLISHED into measured evidence, without claiming
field deployment. Two independent auditors who have not seen the project. Budget 60–75 minutes each.

**Method rules.** Think-aloud. No help from the team; if the operator is stuck for 90 seconds, record
it as a failure and *then* assist. Record: screen, time-on-task, exact words at the moment of
confusion. **Never ask "do you like it?"** — every task has an objective pass condition.

**Severity:** S1 = wrong conclusion drawn (the system misled them) · S2 = task not completed ·
S3 = completed but confused or slow · S4 = cosmetic.

| # | Task | Expected behaviour | Pass condition | Evidence | Severity if failed |
|---|---|---|---|---|---|
| 1 | Open the console cold, no briefing | Landing explains what it does | Operator states the purpose in one sentence, unprompted, within 60 s | Their exact sentence | S2 |
| 2 | Sign in | Demo accounts visible, roles stated | Signs in without help in < 60 s | Time | S2 |
| 3 | Upload a `.wav` capture | Analysis runs, result appears | Reaches a verdict screen unaided | Screen recording | S2 |
| 4 | Run analysis on a provided `.iq` | Sample-rate provenance shown | Operator states the rate is **not** known from the file | Their words | **S1** |
| 5 | Read a DECODED result | Code, interleaver, modulation, payload | Names what was established, without over-reading | Their words | S3 |
| 6 | Open the evidence chain | Six stages, each inspectable | Navigates to the statistical stage unaided | Click path | S3 |
| 7 | Explain UNKNOWN in their own words | "Not enough evidence", not "no signal" | Distinguishes it from "nothing was there" | Their words | **S1** |
| 8 | Explain SIGNAL_NO_CODE | "Signal present, no catalogue code" | Distinguishes it from UNKNOWN | Their words | **S1** |
| 9 | Explain what DECODED does *not* mean | Not "message read", not "sender identified" | States at least one correct limit | Their words | **S1** |
| 10 | Find where the capture came from | Source kind and provenance visible | Locates it in < 90 s | Click path | S3 |
| 11 | Read a receipt and press Verify | Chain recomputed in-browser | Reports the chain verified | Screenshot | S2 |
| 12 | Told a record was altered — prove it | Verify fails, naming the entry | Concludes the record cannot be trusted | Their words | **S1** |
| 13 | Upload a corrupt / non-signal file | 400 with a specific reason | Understands it was rejected and why | Error text | S2 |
| 14 | Recover after the error | Can retry without reloading | Completes a second analysis | Time | S3 |
| 15 | Find an earlier analysis | Signal library, searchable | Locates a named record in < 90 s | Time | S3 |
| 16 | Produce a report for a supervisor | Report view, print/PDF, CSV | Produces a PDF **and** opens the CSV with rows in it | Both files | S2 |
| 17 | State two limitations of the system | Limitations are visible, not buried | Names two, correctly | Their words | **S1** |
| 18 | Repeat tasks 5 and 7 at 1366×768 | No clipping, all actions reachable | Completes both | Screenshots | S3 |
| 19 | Repeat task 5 on a phone (390 px) | Layout stacks, nothing cut off | Completes it | Screenshots | S3 |
| 20 | Switch to light theme, repeat task 6 | Contrast holds, nothing invisible | Completes it | Screenshots | S4 |
| 21 | Terminology sweep | — | Operator lists every word they could not define | Their list | S3 |

**Acceptance for the study as a whole:** zero S1 findings across both operators. Any S1 is a
statement that the interface caused a wrong conclusion, which is the only defect class this project
cannot tolerate given what it claims.

**What may be claimed afterwards:** *"Two independent operators, neither of whom had seen the system,
completed N of 21 tasks unaided; the confusions recorded were X and Y."* **Not** "usability
validated", and **never** "field tested".

---

# PHASE 4 — Highest-value remaining experiments

Four experiments, ordered by confidence gained per hour. None touches the sealed split.

### E1 — Es/N0 waterfall (do this one)

- **Hypothesis:** recall rises monotonically with Es/N0 while the false-accept rate stays at 0.
- **Dataset:** existing `data/train` (100) and `data/nullset` (1,350). No new data.
- **Controls:** default configuration; engine commit recorded; no tuning between runs.
- **Metric:** recall and wrong-decode rate per Es/N0 bin, with Wilson intervals.
- **Threshold:** false accepts remain 0 in every bin; recall increases with Es/N0.
- **If it passes:** *"On the development split, recall improves with Es/N0 and no bin produced a
  false accept."* **Not** a general accuracy claim.
- **If it fails** (false accepts appear in a bin): that bin is a genuine weakness — report it, and
  say so on the limitations slide. A discovered weakness reported first is a strength in Q&A.

### E2 — Refusal behaviour under degradation

- **Hypothesis:** as a capture is degraded (truncation, clipping, dropouts), the engine moves
  DECODED → refusal, and **never** DECODED → wrong decode.
- **Dataset:** train captures, degraded synthetically. Sealed set untouched.
- **Metric:** transition matrix of verdicts vs degradation level; count of wrong payloads.
- **Threshold:** zero transitions into a *wrong* decode.
- **If it passes:** *"Degradation drives the engine toward refusal, not toward error"* — the single
  most valuable sentence available to this project.
- **If it fails:** a wrong decode under degradation is an S1-class defect. Fix before submission.

### E3 — Detection-test calibration, measured not tuned

- **Hypothesis:** the signal-presence test is anti-conservative at the documented ~4.2% against a
  nominal 1%.
- **Dataset:** noise-only null files.
- **Metric:** empirical false-detection rate with a Wilson interval.
- **Threshold:** none — this is a measurement.
- **Allowed conclusion:** a number to put beside the limitation. **Do not retune** (§9.6).

### E4 — What bench-v2 does not cover

- **Method:** enumerate, from `eval/bench2_gen.py`, the impairments *absent* from the sealed set
  (e.g. fading, multipath, co-channel interference, frequency drift beyond the tested range).
- **Output:** a written list, not an experiment.
- **Value:** lets us answer "what would break it?" with specifics rather than a shrug. Cheapest
  confidence in this document.

**Explicitly not proposed:** anything requiring new hardware, a new dataset, or a model.

---

# PHASE 5 — Jury attack test

25 questions a sceptical evaluator would ask. For each: why it is asked, the strongest truthful
answer, what to show, and what must not be said.

### Novelty and positioning

**1. "What is actually new here?"**
Asked because most entries combine known parts. **Answer:** the components are established —
cumulant modulation tests, syndrome search, exact sign tests, multiple-testing correction. What is
deliberate is the *decision rule*: an answer is emitted only when an exact test clears a bar
corrected for every hypothesis tried, and the system is built to refuse otherwise. **Show:** the
acceptance panel with hypothesis count and corrected bar. **Do not say:** novel, first, patented.

**2. "Isn't this just a demodulator with a UI?"**
**Answer:** a demodulator tells you what it decoded. This tells you *how strongly it believes it*,
against what alternatives, and refuses when the evidence is short. **Show:** BENCH-SHORT-K7
returning IMPOSSIBLE_IN_DOMAIN. **Do not** disparage other tools.

**3. "Why not use AI?"**
**Answer:** a learned classifier cannot produce a p-value or name the alternatives it rejected.
§9.4 requires every decision to carry its statistic, threshold and rejected alternatives. **Show:**
the hypothesis explorer. **Do not say:** AI-powered.

### False positives and statistical validity

**4. "You tried 68,000 hypotheses. Isn't one bound to fit?"**
**Answer:** that is exactly what the correction is for — the bar is divided across weighted families
and is shown per decision. **Show:** hypothesis count beside the corrected threshold.

**5. "What is your false-positive rate?"**
**Answer:** 0/120 on sealed non-catalogue signals, 0/900 on the null set. Both are dataset-bounded,
with Wilson upper bounds recorded. **Do not** convert to a general rate.

**6. "Could the benchmark have leaked into development?"**
**Answer:** criteria were committed before the first run, the sealed split has a committed manifest
and an access log, and it was run once. **Show:** `eval/bench2_criteria.json` and the access log.

**7. "What is the wrong-decode rate?"**
**Answer:** 3/310 = 0.97% on sealed catalogue classes, under the 2% pre-registered bar.

**8. "Show me a case where it is wrong."**
**Answer:** yes — enabling 8PSK/16-QAM makes a BPSK capture decode as 8PSK with a *stronger*
p-value and a 40%-wrong payload. That is why the feature is off, and we publish it. **Show:**
`HIGHER_MODULATION_EXPERIMENT.md`. This question is an opportunity, not a threat.

**9. "Your detection test is anti-conservative — isn't that a hole?"**
**Answer:** yes, ~4.2% against a nominal 1%, documented. It affects *presence*, not acceptance: a
code is still only accepted through the corrected exact test. **Do not** claim it is fixed.

### Real-world validation

**10. "Has this ever seen a real signal?"**
**Answer:** yes — JJY, DCF77, MSF, WWV decoded blind and checked against receiver GPS time to
2–23 ms; DDH47 teleprinter text naming its own callsign; AIR carriers 5/5 against the official list.

**11. "How do you know the time decode was right?"**
**Answer:** it was checked against something the engine never saw — the receiver's GPS clock.

**12. "What about WWVB?"** **Answer:** it refused. The ML frame was wrong and the digit test caught
it. A refusal that prevented a false answer is the strongest evidence in the project.

**13. "Any Indian signal?"**
**Answer:** All India Radio medium wave, 5/5 carriers matched to Prasar Bharati's list. A live 720
kHz capture on 2026-09-20 gave quality GOOD, a carrier 61.3 dB above noise and SIGNAL_NO_CODE.
**Do not claim** the live capture was AIR Chennai — the nearest receiver was 2,135 km away and the
station identity is NOT ESTABLISHED.

**14. "Is it real-time?"** **Answer:** no. Analysis is ~0.15 s per capture; live reception streams
incrementally. **Do not say** real-time.

### Security, deployment, scale

**15. "Is it secure?"** **Answer:** it is authenticated with roles, rate-limited and input-validated,
and 0 of 2,709 forged session signatures were accepted. There has been **no external penetration
test**. **Do not say** secure without that sentence.

**16. "Is it production ready?"** **Answer:** no. TLS is configured but never exercised; container
base images are unscanned; there is no field deployment.

**17. "How does it scale?"** **Answer:** deliberately one writer per results directory — a second
process refuses to start, because two writers fork the evidence chain. Horizontal scale needs a
different store and is NOT ESTABLISHED.

**18. "What happens at 100,000 records?"** **Answer:** measured — ledger append is linear, 505 ms at
100k versus 11 ms at 100; the deployed ledger holds 153. The O(1) fix is understood and deliberately
not built.

**19. "Can I verify a result without trusting you?"** **Answer:** yes — the browser recomputes the
hash chain itself, and a CLI verifier runs with no ICHNOVA code. **Show:** the tamper demo.

### Reproducibility and operations

**20. "Can I reproduce your numbers?"** **Answer:** yes — data regenerates deterministically from
seeds; commands are in `SIH26147_CURRENT_STATE.md`.

**21. "Who would use this, and for what?"** **Answer:** a monitoring-station analyst deciding whether
an unidentified transmission warrants escalation. **Do not** claim any agency uses it.

**22. "Have real operators used it?"** **Answer:** honestly — not yet, or "two independent operators
completed N of 21 tasks" once Phase 3 is done. **Never** say field tested.

**23. "Is this an official government system?"** **Answer:** no, and the disclaimer is on every page.

**24. "What are the alternatives?"** **Answer:** describe the *class* — SDR toolchains, commercial
signal-analysis suites, academic blind-demodulation work — and what is different here (the refusal
rule and the evidence trail). **Do not** claim superiority over named tools we have not benchmarked.

**25. "What would break it?"** **Answer:** modulations outside the catalogue; structures outside the
declared interleaver domain; captures too short to prove anything (which it says); fading and
multipath, which bench-v2 does not cover. Answer this with the E4 list in hand.

---

# PHASE 6 — Demo architecture (5–7 minutes)

Two pairings carry the whole thesis, and both already exist. **Nothing below is invented.**

**The engineered pair — same code, different evidence:** `BENCH-QPSK-K7` (DECODED, 50,916
hypotheses) and `BENCH-SHORT-K7` (UNKNOWN, IMPOSSIBLE_IN_DOMAIN, 4,356 hypotheses). Both are genuine
K=7 transmissions. The only difference is how much signal there was.

**The real-world pair:** JJY (decoded blind, GPS +1.9 ms) and WWVB (time refused).

| # | Time | Screen | Action | Audience should notice | Say this | Highlight |
|---|---|---|---|---|---|---|
| 1 | 0:00 | Landing | — | It states what it does and what it refuses to do | "This reads a recording it was told nothing about, and it will tell you when it cannot answer." | The disclaimer |
| 2 | 0:30 | Analyse | Upload `BENCH-QPSK-K7` | A verdict with numbers, not a label | "Blind: no station, no code, no rate given." | — |
| 3 | 1:10 | Result | — | DECODED with modulation, code, interleaver | "It recovered a K=7 code and a 10×12 interleaver — and here is why it believes it." | 50,916 hypotheses tested |
| 4 | 1:40 | Evidence chain → statistical validation | Click | Corrected bar vs achieved p | "Fifty thousand hypotheses were tried, so the bar moves to account for that. It cleared the moved bar." | p vs threshold |
| 5 | 2:20 | Signal record | Open `BENCH-SHORT-K7` | Same code family, different outcome | "Same kind of transmission. Shorter capture." | UNKNOWN |
| 6 | 2:45 | "What would prove it?" | — | It refuses *and* explains | "It says more signal would not help — 32 coded bits can never clear the bar. That is a refusal with a reason." | IMPOSSIBLE_IN_DOMAIN |
| 7 | 3:20 | Monitor / real signal replay | Open JJY | Real radio, checked externally | "A Japanese time station, decoded blind, agreeing with the receiver's GPS clock to two milliseconds." | +1.9 ms |
| 8 | 4:00 | WWVB record | — | Refusal on a real signal | "Same engine, same night, different station: it found structure and refused to state a time. The most valuable thing here is the refusal." | SIGNAL_NO_CODE |
| 9 | 4:40 | Audit tab → Verify receipt | Click | Chain recomputed in the browser | "This is checked in your browser. We are not asking you to trust our server." | "Every hash recomputed here matches" |
| 10 | 5:20 | Verify again on a tampered ledger | Click | It names the altered entry | "One record altered on disk. It finds it and refuses to vouch for the decision." | "entry 2: content does not match its hash" |
| 11 | 6:00 | System → sources | — | Provenance and freshness | "Every source says who runs it, what we may do with it, and whether it is actually delivering — not just reachable." | STALE vs ONLINE |
| 12 | 6:30 | Close | — | The limitations slide | "No field deployment, no penetration test, Salesforce never connected. It is all written down." | — |

**Fallbacks:** the whole demo runs from committed evidence packs and replays with no internet.
Do not attempt a live KiwiSDR capture on stage — propagation is not a demo dependency you control.

---

# PHASE 7 — Claim firewall

### SAFE TO SAY
- "Analyses .IQ and .wav recordings blind: modulation, symbol rate, carrier offset, code, interleaver."
- "Returns DECODED, SIGNAL_NO_CODE or UNKNOWN, and refuses when the evidence is short."
- "0 false accepts on 120 sealed non-catalogue signals and 0 on 900 null-set captures."
- "9 of 9 pre-registered criteria passed on a sealed split, run once, access logged."
- "Real government time signals decoded blind and checked against receiver GPS time to 2–23 ms."
- "All India Radio carriers matched 5/5 against Prasar Bharati's published list."
- "Every decision carries a hash-chained receipt that a browser or a CLI can re-verify."
- "Authenticated API with four roles; 0 of 2,709 forged session signatures accepted."
- "175 tests; dependency scans clean for Python and Node."
- "An independent SIH prototype. Not an official Government of India system."

### SAY ONLY WITH A QUALIFIER
| Claim | Required qualifier |
|---|---|
| "No false accepts" | "on this sealed split / null set, with these Wilson bounds" |
| "Decodes RS, LDPC, concatenated chains" | "on the sealed benchmark, at the stated Es/N0" |
| "Works on live signals" | "through public receivers, subject to propagation" |
| "Live Indian source" | "a 720 kHz capture; station identity not established — nearest receiver 2,135 km" |
| "Secure" | "authenticated and hardened; no external penetration test" |
| "Deployable" | "container and TLS proxy configured; TLS never exercised" |
| "Fast" | "~0.15 s per capture as a development measurement, not a validated benchmark" |
| "Salesforce integration" | "implemented as an offline outbox; never connected to a real org" |
| "Supports 8PSK/16-QAM" | "implemented, off by default, with the measurement that justifies it" |
| "Verified by operators" | only after Phase 3, phrased as "N of 21 tasks completed unaided" |

### DO NOT SAY
AI-powered · real-time · universal · accurate / high-accuracy · guaranteed · first · novel ·
patented · better than commercial tools · production ready · field deployed · live monitoring
network · official Government system · "reads the message" · "identifies the sender" ·
any general accuracy percentage · any claim about a named competitor.

---

# PHASE 8 — Final action plan

### Next 24 hours — risk reduction only
1. **Run E1, the Es/N0 waterfall.** Existing data, no new code. Produces the chart that answers the
   most likely quantitative question.
2. **Run E2, degradation → refusal.** If it holds, it is the strongest sentence in the pitch. If it
   fails, we must know now.
3. **Write the E4 list** — what bench-v2 does not cover. One page, no code.
4. **Rehearse the Phase 6 demo, timed, five times**, including the tamper step.

### Next 48 hours — validation and presentation
5. **Run the Phase 3 operator study** with two independent auditors. Highest-value remaining evidence.
6. Fix only **S1 findings** from that study. Nothing else.
7. Build the limitations slide directly from §1.5 of this document.
8. Prepare answers to all 25 Phase 5 questions; rehearse questions 8, 13 and 22 aloud — those are
   where an honest answer beats a defensive one.

### After that — only if evidence justifies it
9. E3 detection-calibration measurement (measure, never tune).
10. Container image build and scan, **if** a Docker daemon becomes available.
11. Local TLS exercise, **if** nginx becomes available.

### DO NOT BUILD — freeze
Modulation classifier · Cyclic-CAF · SAGE-Lite · additional modulations, FEC or interleavers ·
any learned model · geolocation/TDOA · SDR hardware · cloud scaling · live Salesforce · mobile app ·
additional UI pages · additional simulated monitoring.

---

## The final question

> **"If this were your project and the deadline were close, would you stop major engineering now?"**

**Yes. Stop.**

The evidence, not encouragement:

1. **Every SIH26147 checklist item is delivered or honestly bounded.** The audit that started this
   work found QAM, RS, LDPC, concatenated coding, three interleaver types and bit-stream correlation
   missing. All are now implemented, and the one that is off by default is off *with a published
   measurement*.
2. **No engineering item is class A.** Seventeen candidates were assessed; none blocks submission.
3. **The remaining risk is not capability — it is evidence about people.** "Operator value" is the
   only term in the objective function that is still NOT ESTABLISHED, and it is closed by a
   two-person study, not by code.
4. **More engineering now actively lowers the score.** Every new feature adds an unvalidated claim,
   a new failure mode, and something that can break on stage — against a rubric that rewards depth
   and defensibility over breadth (§9.11).
5. **The project's strongest asset is already built and rehearsable:** it refuses, it explains the
   refusal, and anyone can verify the record without trusting us.

The one caveat: if **E2 fails** — if degradation can push the engine into a *wrong* decode rather
than a refusal — that is a class A defect and engineering resumes immediately, because it would
contradict the central claim. Run E2 first, tonight.
