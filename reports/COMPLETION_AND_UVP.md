# ICHNOVA — What was assigned, what was delivered, and why it wins

Independent Smart India Hackathon prototype for problem statement **SIH26147**. **Not an official
Government of India system.**

State after the hardening, ordering and deployment pass, engine `v0.3.0`, updated 2026-09-22 for the
console speed pass and roadmap Phase 2. **178 tests pass.** Every
figure below comes from a committed result file or a test; where something is not established, this
document says so. What that pass changed, and what it deliberately did not,
is in `reports/HARDENING_AND_DEPLOYMENT_PASS.md`; the verification that followed it — a real
browser sweep, a dependency scan, and the ledger's measured scaling limit — is in
`reports/FINAL_VERIFICATION_PASS.md`.

Labels used throughout: **LIVE** (exercised against real radio or a real service), **VALIDATED**
(measured against known ground truth, or protected by a test that fails if it breaks),
**IMPLEMENTED** (works end to end, not separately measured), **EXPERIMENTAL** (built, off by
default), **NOT ESTABLISHED** (not claimed).

---

## 1. Assigned by the problem statement — SIH26147

The audit on 2026-09-17 found most of the explicit SIH26147 checklist missing. All of it is now either
delivered or honestly bounded.

| Requirement in the brief | At the audit | Now | Evidence |
|---|---|---|---|
| Input raw `.IQ` and `.wav` | Delivered | **LIVE** | `POST /api/analyze`, exercised in the browser |
| Waterfall, spectrum, constellation | Delivered | **VALIDATED** | Rendered for every evidence pack |
| Blind symbol rate and carrier offset | Delivered | **VALIDATED** | 2–20 samples/symbol search, `tests/test_core.py` |
| PSK demodulation (BPSK, QPSK) | Delivered | **VALIDATED** | Null-set confusion matrix |
| FSK demodulation | Delivered | **LIVE** | Real DWD teleprinter decoded; the text names its own callsign |
| Convolutional FEC + Viterbi | Delivered | **VALIDATED** | K = 3/5/7, exact parity-check sign test |
| **QAM demodulation** | Missing | **EXPERIMENTAL** | 8PSK and 16-QAM implemented and tested; off by default on measured evidence (§3.1) |
| **Reed–Solomon** | Missing | **VALIDATED** | CCSDS (255,223) and (255,239), dual basis, depth I, virtual fill |
| **Concatenated coding** | Missing | **VALIDATED** | RS + randomiser + ASM + inner K7 decoded end to end: 10/12 sealed captures |
| **LDPC** | Missing | **VALIDATED** | CCSDS TC LDPC (128,64): 8/8 sealed CLTUs |
| **Convolutional, diagonal, pseudo-random de-interleaving** | Missing | **VALIDATED** | Forney, wrapped diagonal, 3GPP QPP — all in the default search |
| **Bit-stream correlation, header / payload** | Missing | **VALIDATED** | Frame sync on the CCSDS ASM with a header/payload map; 5/10 non-catalogue framed streams given their true period |
| **Raw `.IQ` sample rate** | Silently assumed 1 MHz | **VALIDATED — and bounded** | Provenance on every result (`declared` / `wav_header` / `unavailable`). An absolute rate in Hz is not recoverable from baseband samples, and the engine says so instead of inventing one |

**The sealed benchmark (bench-v2)** — criteria committed before the first run, one run only, access
logged. **All nine pre-registered criteria pass.**

| Criterion | Required | Measured |
|---|---|---|
| No false accepts on non-catalogue signals | ≤ 1 % | **0 / 120** (95 % upper bound 3.1 %) |
| Wrong structure or payload is rare | ≤ 2 % | **3 / 310 = 0.97 %** |
| Continuous K7 stream recall, Es/N0 ≥ 6 dB | ≥ 80 % | **16 / 16** |
| CCSDS concatenated chain recall, ≥ 9 dB | ≥ 60 % | **10 / 12** |
| TC LDPC CLTU recall, ≥ 6 dB | ≥ 80 % | **8 / 8** |
| Framed RS recall, ≥ 9 dB | ≥ 50 % | **5 / 6** |
| Blind framed stream reported with its true period | ≥ 50 % | **5 / 10** |
| CCSDS concatenated answered without a wrong claim | ≥ 85 % | **11 / 12** |

These are benchmark measurements on a named synthetic dataset, not a general accuracy figure.

---

## 2. Assigned by the team, pass by pass

| Assignment | Delivered | Status |
|---|---|---|
| Full engineering and SIH-readiness audit | 17-section audit, requirement matrix, document conflicts C1–C9 resolved | Done |
| Remove the silent 1 MHz default | `fs_source` on every result; decisions independent of fs | **VALIDATED** |
| A sealed benchmark done properly | bench-v2: committed manifest, pre-registered criteria, one logged run | **VALIDATED** — 9 / 9 |
| A working model, not a demo | Dockerfile (non-root, `HOST`/`PORT`), LAN setup; the deployed process runs the real engine | **IMPLEMENTED** |
| Frontend that doesn't look AI-made | Impeccable and unslop passes; every route measured; 89 measured defects → 0 | Done |
| Real authentication | scrypt passwords, signed expiring tokens, revocation, rate limiting | **VALIDATED** — 0 of 2,709 forged signatures accepted |
| RBAC: Admin / Analyst / Reviewer / Viewer | Enforced per endpoint on the server **and** reflected in the console | **VALIDATED** — Viewer gets 403 on writes; a test keeps the console's table identical to the server's |
| Security audit | Headers, CORS, raw-socket path traversal, error leakage, upload validation, secrets scan | **VALIDATED** — see `FINAL_FEATURE_AUDIT.md` |
| Data-quality gate, separate from the verdict | GOOD / DEGRADED / FAILED, tested never to change a verdict | **VALIDATED** |
| "What would prove it?" without invented numbers | Required parity checks derived from the test that refused the capture | **VALIDATED** |
| Evidence receipts with a visible VERIFY | SHA-256 hash chain; the browser recomputes it | **VALIDATED** — tampering caught in the browser |
| Live and near-live Indian signal data, legally sourced | `SignalSource` registry: five sources with provenance, licence and a freshness rule | **LIVE** — 865 public receivers, 2 in range of AIR Chennai 720 kHz. One source is live-capable, one is reference only, one metadata only; a reachable service with no recent observation reads STALE, never green |
| Salesforce as the workforce layer, never faking a sync | Offline outbox, idempotent, retries, dead letter, env-only secrets | **IMPLEMENTED** — never connected to a real org, and says so |
| `reports/FINAL_FEATURE_AUDIT.md` | Written, then corrected twice as later measurements superseded it | Done |
| Fix every screenshot bug | Ten bugs: oversized badges, overflow, empty CSV, blank print, grey button cards, and more | Done, each verified in the browser |
| Complete the "planned" items | Three were already built and mislabelled; QAM measured; blind fs bounded | Done |
| Git hygiene and push to main | No blanket `git add`, no secrets committed, fast-forward only | Done — `origin/main` verified with `git ls-remote` after each push |

---

## 3. Added beyond the assignment

None of these were asked for. Each exists because running the system exposed a problem.

1. **An experiment instead of an argument.** QAM was "off because it might add false accepts".
   Measured over all 1,350 null-set captures with the gate forced on: false accepts were **0 either
   way** — the stated worry was wrong. The real cost was worse. It decoded 0 of 100 8PSK captures while
   growing the search a median 21.8×, and turned one bit-perfect BPSK decode into a confident, 40 %-
   wrong 8PSK answer — a structural alias no statistical test can catch.
   `reports/HIGHER_MODULATION_EXPERIMENT.md`.
2. **Sufficiency that cannot mislead.** The first version told a *noise* capture to "record 44 more
   parity checks". Two honest outcomes were added — `STRUCTURALLY_REJECTED` and a selection-aware
   `NO_TREND` — so no refusal asks for capture that cannot help.
3. **Seven defects found by testing, not by reading**: signatures compared as decoded bytes (3 in 63
   near-miss forgeries passed); refused uploads reset the connection on Windows; a tampered ledger
   verified green from browser cache; a malformed `.wav` returned 500; stale evidence served from
   cache; one pack without an interleaver emptied the whole signal library; the receiver health check
   silently matched nothing.
4. **Constitution v2.5.3.** The governing document said a CRM "needs its own amendment — none is
   approved" while the CRM was already committed. Amended through its own process.
5. **Four stale public claims corrected**, all understating the system — including "the API is
   unauthenticated", repeated in four documents long after it stopped being true.
6. **A drift test between console and server permissions**, so the UI can never quietly offer an
   action the server refuses, or hide one it allows.
7. **Receipt verification that cannot be cached into lying**, plus a CLI
   (`server/verify_receipt.py`) so a third party can check a ledger without running ICHNOVA.
8. **Roadmap Phase 2, measured instead of promised** (EXPERIMENTAL). A fingerprint built only from
   what the engine measured, and nearest-neighbour search over it. On 675 held-out synthetic
   captures, with the protocol fixed before the run, the nearest fingerprint is the same kind of
   signal **54.2 %** of the time (95 % CI 50.5–57.9 %) against 20.4 % for a random pick and 31.5 % for
   the verdict alone; 70.4 % at 384 coded bits. Never part of a decision.
   `reports/PHASE2_SIMILARITY_REPORT.md`.
9. **A console that opens fast without dropping anything.** Start-up no longer downloads every
   evidence pack (~14 MB) to list the library; each screen is its own chunk (first visit ~146 kB
   gzip); the server compresses and revalidates (a 4.3 MB pack travels as 228 kB).

---

## 4. Unique value propositions

Each is something a judge can check in the room.

### UVP 1 — It refuses to guess, and proves it
Every answer is **DECODED**, **SIGNAL_NO_CODE** or **UNKNOWN**. A result is accepted only when an
exact statistical test clears a bar corrected for *every hypothesis tried* — up to about 68,000 on a
single capture. **0 false accepts on 120 sealed non-catalogue signals, and 0 on 800 null-set
captures.** We have not surveyed other tools, so this makes no claim about them: what is stated is
what this one does, which is to return an answer only when it can defend it, and to publish the rate
at which it refuses.

### UVP 2 — Every decision is independently verifiable
Each decision is chained into a SHA-256 receipt: this capture, this engine, this verdict, linked to
the one before. The browser recomputes the chain itself — the server is never asked whether it is
honest. Alter any record and the page names which one.

### UVP 3 — A refusal comes with its remedy
"UNKNOWN" is not a dead end. The engine states *why* — too few parity checks, a structural
contradiction, or no trend at all — and, when more signal would help, exactly how much, derived from
the test that refused it. When more signal would not help, it says that instead.

### UVP 4 — Checked against the real world, not only synthetic data
Government time signals decoded blind and checked against receiver GPS time to **2–23 ms**: NICT
(JJY), PTB (DCF77), NPL (MSF), NIST (WWV). A German weather teleprinter decoded to text that names its
own callsign. All India Radio medium-wave carriers matched **5 / 5** against Prasar Bharati's official
transmitter list. Where it could not establish a time (WWVB), it refused — and the refusal was right.

### UVP 5 — It knows where its data came from, and what it may do with it
Every source declares its operator, its terms, and whether it may produce a verdict (`ENGINE`), only
check one (`REFERENCE ONLY`), or carries no samples at all (`METADATA ONLY`). Nothing touches
restricted, encrypted or private RF infrastructure.

### UVP 6 — Measured before it is claimed
A sealed benchmark with pre-registered criteria and one logged run; a governing constitution that the
code and UI may not contradict; an honesty label on every claim. When a feature does not earn its
place, the measurement is published rather than hidden.

### UVP 7 — It can recognise a signal it could not decode (EXPERIMENTAL, measured)
A refusal still leaves a fingerprint of what was measured. Searching those fingerprints finds
captures of the same kind **54 %** of the time on held-out synthetic data (random: 20 %; the verdict
alone: 32 %), so an unknown signal that comes back can be recognised as a recurrence rather than a new
mystery. Measured on synthetic captures only; not yet on real recordings.

### UVP 8 — Built to be deployed, not demoed
An air-gap-capable engine with no cloud dependency for analysis, an authenticated API with role
permissions, a container image, and a CRM hand-off designed for a network that is usually down.

---

## 5. Questions a jury can ask any SIH26147 solution

We have not audited any other team's implementation, so nothing here is a comparison with a named
entry. The left column is what a jury can ask *any* submission to show; the right column is what
ICHNOVA shows in response. The middle column describes a failure mode, not a competitor.

| What a jury can ask | A submission with no evidence trail | ICHNOVA |
|---|---|---|
| "Show me it on something you didn't generate." | Synthetic data only | Real government transmissions, checked against GPS time |
| "What happens when there's no signal?" | Returns a best guess | Returns UNKNOWN — 0 false accepts on 920 no-code captures |
| "How do I know your accuracy wasn't tuned?" | One accuracy number | Criteria committed before a single, logged sealed run |
| "You tried thousands of hypotheses — isn't one bound to fit?" | Not addressed | Corrected exact tests; the correction is shown on every decision |
| "Can I trust this record next month?" | A log file | A hash-chained receipt the browser re-verifies |
| "Why did it fail on this capture?" | "Low confidence" | The exact test, the shortfall, and whether more signal would help |
| "What is this raw .IQ's sample rate?" | A hard-coded default | Stated provenance, and an honest refusal when it cannot be known |
| "Which parts are real and which are mock-ups?" | Unlabelled | LIVE / BENCHMARK / SIMULATED / EXPERIMENTAL on every panel |
| "Who is allowed to do what?" | One login | Four roles, enforced on the server, reflected in the UI |
| "RS, LDPC, QAM, interleavers?" | Listed on a slide | Decoded end to end with sealed recall per family — and QAM kept off, with the reason measured |

The short version for a jury: **other entries claim capabilities; ICHNOVA publishes its failure rate.**
A system that says when it is wrong, and refuses when it cannot know, is the one an operator can put
in front of a real decision.

---

## 6. What is still not claimed

Stated plainly, because a judge will ask:

- **No field deployment.** Never run at a monitoring station; no operator feedback, no certificates.
- **No general accuracy figure.** Every number above belongs to a named dataset.
- **No Salesforce synchronisation has ever occurred.** Built and tested against a stand-in only.
- **8PSK / 16-QAM remain EXPERIMENTAL.** With the default configuration their sealed recall is 0, and
  enabling them was measured to cause a wrong decode. The path forward is a modulation classifier that
  chooses the constellation *before* the code search.
- **TLS is CONFIGURED, not live.** The API does not terminate TLS and is not meant to. `deploy/`
  carries a complete HTTPS reverse-proxy deployment — certificates, redirect, forwarded headers,
  limits, timeouts — and the application now believes `X-Forwarded-For` only from a trusted proxy.
  No certificate has been issued for a real host and no traffic has been served through it.
- **No novelty claimed from combination.** Cumulant tests, syndrome search, exact sign tests and
  multiple-testing correction are established methods. What is deliberate here is the refusal
  behaviour and the evidence trail — not the mathematics.

Related reports: `HARDENING_AND_DEPLOYMENT_PASS.md`, `FINAL_FEATURE_AUDIT.md`,
`BENCH2_SEALED_REPORT.md`, `REAL_SIGNAL_VALIDATION.md`, `HIGHER_MODULATION_EXPERIMENT.md`, the
deployment path in `deploy/README.md`, and the Constitution in `sih26147-constitution/`.
