# ICHNOVA — Final feature audit

Independent Smart India Hackathon prototype for problem statement **SIH26147**.
**Not an official Government of India system.** Government RF monitoring workflows are used only as
design inspiration.

Audited at commit `4435908`, engine `v0.3.0`. Every number below was measured during this audit;
nothing is carried over from an earlier report without being re-run. Where something was not
measured, the row says so rather than estimating.

---

## 1. What the labels mean

The matrix uses six states, and they are not interchangeable:

| Label | Meaning |
| --- | --- |
| **LIVE** | Works against a real external service or real radio, and was exercised against it during this audit. |
| **VALIDATED** | Implemented *and* measured against data with known ground truth, or proven by a test that fails when the behaviour breaks. |
| **IMPLEMENTED** | The code path exists and runs end to end, but its correctness rests on the implementation rather than on a measurement. |
| **SIMULATED** | Runs on generated data with known ground truth. Useful for measurement, never evidence of field performance. |
| **PLANNED** | Designed, not built. No code claims it works. |
| **BLOCKED** | Cannot be done here, with the reason stated. |

A **BENCHMARK** result is a measurement on a specific dataset. It is never general performance, and
no number in this document should be quoted as "accuracy" without the dataset beside it.

---

## 2. Requirement matrix — SIH26147

| # | Requirement | State | Evidence |
| --- | --- | --- | --- |
| 1 | Blind detection of a signal in a capture | **VALIDATED** | Spectral-line test with an explicit p-value; measured on the sealed and null sets (`reports/BENCH2_SEALED_REPORT.md`). |
| 2 | Modulation identification (BPSK/QPSK) | **VALIDATED** | M2/M4 cumulant decision with a recorded margin; confusion matrix over the null set. |
| 3 | Symbol-rate estimation | **VALIDATED** | Candidate table per sps with quality figures; correct sps recovered across 4–12 sps in `tests/test_core.py`. |
| 4 | Carrier-offset estimation | **IMPLEMENTED** | CFO candidates ranked by peak-to-floor; the accepted hypothesis carries its CFO. |
| 5 | FEC identification (convolutional K=3/5/7) | **VALIDATED** | Exact sign test on parity checks with weighted Bonferroni correction across four families. |
| 6 | Interleaver identification | **VALIDATED** | Block/diagonal/convolutional/QPP search over a declared domain; recovered on benchmark captures. |
| 7 | Refusal when evidence is insufficient | **VALIDATED** | `UNKNOWN` / `SIGNAL_NO_CODE` outcomes; the null set produces no false accept at the declared α. |
| 8 | Payload extraction after identification | **IMPLEMENTED** | Viterbi decode of the accepted hypothesis; bit-exact on benchmark captures with known payloads. |
| 9 | Operator console showing the evidence | **IMPLEMENTED** | React console: evidence chain, hypothesis explorer, analyst views, audit trail. |
| 10 | Works on operator-supplied recordings | **LIVE** | `POST /api/analyze` accepts `.iq` and `.wav`; exercised during this audit. |
| 11 | Works on live radio | **LIVE** | KiwiSDR receiver network; 865 receivers listed during this audit, in range of all eight catalogued transmissions. |
| 12 | Standard-time transmissions as ground truth | **VALIDATED** | Time codes decoded blind and checked against receiver GPS time (`reports/REAL_SIGNAL_VALIDATION.md`). The CHU decoder is **SIMULATED** only: implemented and tested on synthetic packets, never received off air. |
| 13 | Indian signal source | **LIVE** | All India Radio Chennai, 720 kHz medium wave (Prasar Bharati, 200 kW). Two public receivers in range at audit time; five AIR carriers previously matched against the official transmitter list. |
| 14 | Higher-order modulation (8PSK, 16-QAM) | **EXPERIMENTAL** | Implemented, tested and switchable per analysis, but off by default on measured evidence: 0 of 100 8PSK captures decoded, search 21.8× larger, and one BPSK capture returned a confident 8PSK answer 40 % wrong (`reports/HIGHER_MODULATION_EXPERIMENT.md`). |
| 15 | LDPC / Reed–Solomon / frame-level codes | **VALIDATED** | CCSDS RS(255,223)/(255,239) with dual basis, depth I and virtual fill; TC LDPC (128,64); the full concatenated chain decoded end to end by `test_f4_decodes_the_full_ccsds_chain` and `test_f4_decodes_a_tc_ldpc_cltu_and_reports_unresolved_polarity`. |

---

## 3. Platform and operations

| Area | State | Evidence measured in this audit |
| --- | --- | --- |
| Authentication | **VALIDATED** | scrypt password hashing (n=2^14, r=8, p=1); HMAC-SHA256 session tokens with absolute expiry and a revocation set. 2,709 single-character signature forgeries tested, **0 accepted**. |
| Authorisation (RBAC) | **VALIDATED** | ADMIN / ANALYST / REVIEWER / VIEWER against a permission map; endpoint permissions enforced server-side and covered by tests. |
| Rate limiting | **VALIDATED** | Fixed-window limiter per client and bucket; 429 with `Retry-After`, asserted by test. |
| Security headers | **VALIDATED** | Measured on a live reply: CSP `default-src 'self'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, `Cache-Control: no-store`. |
| CORS | **VALIDATED** | No `Access-Control-Allow-Origin` is emitted, verified with a hostile `Origin` header: the API is same-origin only. |
| Path traversal | **VALIDATED** | Eight raw-socket probes (curl rewrites `../` client-side and cannot test this). No source file served; the two 200s are the SPA fallback returning `index.html`. |
| Error leakage | **VALIDATED** | Six malformed requests: no traceback, file path or library name in any reply. |
| Upload validation | **VALIDATED** | Size cap refused on the declared length before the body is read; malformed `.iq` and `.wav` return 400 with a specific reason. |
| Secrets | **VALIDATED** | No credential in any tracked file; `results/` (ledger, outbox) is ignored; the only tracked `.env` is `frontend/.env.example`, which holds an empty key. |
| Evidence receipts | **VALIDATED** | SHA-256 hash chain over decisions. Tamper, gap, reorder and capture-mismatch detection each covered by a test; a tampered ledger was verified **in the browser** and correctly reported "entry 3: content does not match its hash". |
| Capture quality gate | **VALIDATED** | GOOD / DEGRADED / FAILED on clipping, DC offset, dropouts, I/Q balance, non-finite samples and declared rate. Kept strictly separate from the verdict, and tested to be so. |
| Evidence sufficiency | **VALIDATED** | Required parity checks derived from the sign test that refused the capture. Four honest outcomes, including `IMPOSSIBLE_IN_DOMAIN` and `STRUCTURALLY_REJECTED`, so no refusal asks for capture that cannot help. |
| Signal source registry | **LIVE** | Five sources with provenance, licence and measured health; "last received" read from what this machine actually received. |
| Salesforce hand-off | **IMPLEMENTED** | Offline outbox, idempotency on the receipt hash, exponential backoff, dead letter, env-only credentials. **Not LIVE: no Salesforce org was available to this audit, and the code reports exactly that rather than claiming a sync.** |
| Deployment | **IMPLEMENTED** | Dockerfile (node build stage, python-slim runtime, non-root). Hugging Face Docker Spaces require a paid plan, so only the Static SDK is free — the API-backed console cannot run there. |

---

## 4. Defects found and fixed during this audit

Each was found by running the system, not by reading it.

1. **Sufficiency told a noise capture to collect 44 more parity checks.** Two causes: a hypothesis
   that passed the bar and failed a *structural* check was treated as short of evidence, and the best
   of tens of thousands of hypotheses was extrapolated from without correcting for the search. Now
   `STRUCTURALLY_REJECTED` and `NO_TREND` respectively. No refused benchmark capture now asks for
   signal that cannot help.
2. **Every benchmark capture read DEGRADED.** One sample at the peak counted as clipping; the sample
   mean of a short capture counted as DC offset; an arbitrary 4,096-sample floor duplicated a
   question only sufficiency can answer. All three corrected; all six flagship captures now GOOD.
3. **Token signatures were compared as decoded bytes.** The last base64 character carries four bits
   that decoding discards, so three of every 63 single-character changes verified. Now compared as
   the text they were issued as, with an exhaustive test.
4. **Refusing a POST without draining its body** made Windows clients see a connection reset instead
   of the 401/403/429 explaining the refusal. This was an intermittent test failure; 12 consecutive
   runs are clean since.
5. **A tampered ledger verified green from cache.** `.jsonl` was missing from the no-store list, and
   the verifier did not force a fresh fetch. Both fixed, then re-tested by tampering with a shipped
   ledger and confirming the browser refuses it.
6. **A malformed `.wav` returned 500.** A bad upload is the client's error and now returns 400.
7. **The source health check silently found no receivers**, because a site dict was passed where a
   `(lat, lon)` tuple was expected and every receiver was skipped by an exception handler.

---

## 5. What this system does not claim

- **No field deployment.** It has never run at a monitoring station. There are no field interviews,
  no written operator feedback and no certificates. `reports/REAL_SIGNAL_VALIDATION.md` covers
  publicly receivable transmissions, which is a different thing.
- **No general accuracy figure.** Every measurement belongs to a named dataset.
- **No novelty claim from combination.** The components — cumulant modulation tests, syndrome search,
  exact sign tests, Bonferroni correction — are established. What is deliberate here is the refusal
  behaviour and the evidence trail, not the mathematics.
- **No Salesforce synchronisation has occurred.** The integration is built and tested against a
  stand-in; no org was connected.
- **No restricted data.** Every source is publicly offered and openly documented. Nothing reaches
  government telemetry, command links, encrypted services or private RF infrastructure.

---

8. **Four coverage claims in the console were stale**, all understating the engine: convolutional,
   diagonal and QPP de-interleaving and the CCSDS RS/LDPC/concatenated chain were listed as
   "Planned" long after they were built and tested. Corrected against the code and the tests that
   exercise it. Blind sampling frequency stays NOT ESTABLISHED, and now says why: baseband carries
   the symbol rate only as a fraction of the sampling rate, so an absolute rate cannot come from the
   samples at all.

---

## 6. Test position

`125 tests collected`, all passing at audit time, across: DSP and decoder correctness, null and
wrong-structure captures, sample-rate provenance, authentication and authorisation, capture quality,
evidence sufficiency, receipts, and the CRM outbox.

Twenty of those tests exist because of this audit, and each was written to fail if the behaviour it
protects regresses — including the three that assert the system refuses to claim something it has not
established.

---

## 7. Honest verdict

The engine does what the problem statement asks, refuses when it cannot, and now carries a verifiable
record of every decision it makes. The console presents that evidence rather than a conclusion. The
operational layer is built and tested but has never spoken to a real Salesforce org, and the system
as a whole has never been used in the field.

Those two gaps are the honest distance between this prototype and a deployment, and neither is hidden
anywhere in the interface.
