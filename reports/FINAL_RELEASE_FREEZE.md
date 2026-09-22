# ICHNOVA — Final release freeze

**Major engineering is frozen unless a Class A correctness failure is discovered.**

---

## 1. Project identity

**ICHNOVA** — blind signal analysis and decoding for Smart India Hackathon problem statement
**SIH26147**. An **independent SIH prototype**. **Not an official Government of India system.**
Government RF monitoring workflows are design inspiration only.

## 2. Governing document

Constitution **v2.5.4** (2026-09-20). Where any file disagrees with it, the Constitution governs.

## 3. Commit

Frozen at the commit carrying this document, on `sih-readiness`, with `origin/main` at the same
commit. Working tree clean and no untracked files at the time of the freeze checks.

## 4. Tests

**175 passed**, 0 failed, 0 skipped, 2 warnings (SciPy `nperseg` notices on short real captures),
62.8 s. Frontend `tsc --noEmit` exit 0; `vite build` succeeded; `npm audit --omit=dev` reports
0 vulnerabilities.

## 5. Benchmark evidence

**bench-v2 sealed** — 430 files, criteria committed before the first run, one logged run:
**9 of 9 pre-registered criteria pass.**

| Measure | Result |
|---|---|
| False accepts, non-catalogue classes | **0 / 120** (95% upper 3.10%) |
| Wrong structure or payload, catalogue classes | 3 / 310 = **0.97%** |
| Continuous K7 stream recall (≥ 6 dB) | 16 / 16 |
| CCSDS concatenated chain (≥ 9 dB) | 10 / 12 |
| TC LDPC CLTU (≥ 6 dB) | 8 / 8 |
| Framed RS (≥ 9 dB) | 5 / 6 |
| Blind framed stream, true period reported | 5 / 10 |

**Null set** — 0 / 900 false accepts on non-catalogue files; 0 / 450 wrong decodes on coded files.
**bench-v1** regression tripwire — 30/30 sealed, 63/100 train, 0 false accepts.

## 6. Real-signal evidence

| Signal | Result | Independent check |
|---|---|---|
| JJY 40 kHz (NICT) | DECODED blind | GPS agreement **+1.9 ms** |
| DCF77 (PTB) | DECODED blind | **+4.7 ms** |
| MSF (NPL) | DECODED blind | **+3.6 ms** |
| WWV 10 MHz (NIST) | DECODED blind | **+23.4 ms** |
| **WWVB (NIST)** | **SIGNAL_NO_CODE — time refused** | The ML frame was wrong; the digit test caught it |
| DDH47 (DWD) | DECODED ITA2 text | The text names its own callsign and frequency |
| AIR medium wave | 5 / 5 carriers | Matched to Prasar Bharati's published list |
| Live capture 2026-09-20, 720 kHz | Quality GOOD → carrier 61.3 dB above noise → **SIGNAL_NO_CODE** → receipt verified | Station identity **NOT ESTABLISHED** (nearest receiver 2,135 km) |

## 7. Security evidence

Authentication (scrypt, signed expiring tokens, revocation), RBAC across four roles enforced per
endpoint, fixed-window rate limiting, upload validation, raw-socket path-traversal probes, SSRF
protection on the live receiver, forwarded-header trust, token redaction in logs, no CORS header,
CSP / nosniff / no-referrer / frame-deny headers, and no internal detail in error replies.

**0 of 2,709 single-character forged session signatures accepted** (exhaustive).

**Not claimed:** no external penetration test. TLS is **CONFIGURED, never exercised**. Container
base-image CVEs **NOT ESTABLISHED** — no scanner available on this machine.

## 8. Evidence integrity

SHA-256 hash chain over decisions. CLI verifier: clean ledger exit 0 (6 checked); tampered copy exit
1 naming the altered index. Browser verifier: recomputes the chain in-page and names the altered
entry. Both tamper tests assert the file bytes moved **before** verifying, so neither can pass
vacuously. **One writer per results directory** is enforced by an OS lock (§9.12); a second process
refuses to start.

## 9. Known limitations

No field deployment · no external penetration test · TLS never exercised · container CVEs unscanned ·
two hosts on one shared filesystem unsafe by design · no general accuracy figure · blind absolute
sample rate physically unrecoverable · signal-presence test anti-conservative (~4.2% against a
nominal 1%, documented and deliberately not retuned) · monitoring-network data in the console is
simulated and labelled · Google sign-in is a prototype path not verified server-side.

## 10. Experimental / off by default

**8PSK and 16-QAM** — implemented and tested, **off by default on measured evidence**: 0 of 100 8PSK
captures decoded, search ×21.8, and one BPSK capture decoded as 8PSK with a *stronger* p-value and a
40%-wrong payload through a structural alias. Guarded by negative regression tests.

Also experimental: general header search beyond catalogue markers; signal-genome similarity; the
adaptive refinement module (not enabled).

## 11. E2 — degradation → refusal · **PASS**

**Hypothesis:** as a valid capture is degraded, the system moves toward refusal rather than toward a
wrong decode.

Dataset: 15 `data/train` captures that decode **correctly** at baseline (BER 0). Four impairments ×
three severities = 12 conditions each, **180 runs**, 26 s. Sealed split untouched, no threshold
changed, engine at default configuration.

| Baseline → after degradation | Count |
|---|---|
| DECODED → DECODED | 65 |
| DECODED → SIGNAL_NO_CODE | 61 |
| DECODED → UNKNOWN | 54 |

| Impairment | Decoded | SIGNAL_NO_CODE | UNKNOWN |
|---|---|---|---|
| Truncation (75 / 50 / 25%) | 0 | 30 | 15 |
| Clipping (50 / 30 / 15% of peak) | 34 | 11 | 0 |
| Dropouts (1 / 5 / 15% lost) | 31 | 9 | 5 |
| Added noise (+3 / +6 / +9 dB) | 0 | 11 | 34 |

**WRONG DECODES: 0.** Every capture that still decoded carried the correct interleaver and a payload
BER ≤ 1%. **115 of 180 degraded conditions produced a refusal.**

**Allowed conclusion:** on this development split, degradation drove the engine toward refusal and
never toward a wrong answer. Not a general guarantee.

## 12. E1 — Es/N0 characterisation · complete

Computed from committed null-set results. No retuning, no new data.

| Es/N0 (dB) | n | Decoded | Recall | 95% CI | Wrong decodes |
|---|---|---|---|---|---|
| 3 | 121 | 7 | 0.06 | [0.03, 0.11] | **0** |
| 6 | 115 | 24 | 0.21 | [0.14, 0.29] | **0** |
| 9 | 108 | 41 | 0.38 | [0.29, 0.47] | **0** |
| 12 | 106 | 57 | 0.54 | [0.44, 0.63] | **0** |

Non-catalogue classes, false accepts by bin: **0 at every Es/N0** (n = 185 / 189 / 205 / 221;
95% upper bound ≤ 2.0%).

**Allowed conclusion:** on this development split, recall rises monotonically with Es/N0 while wrong
decodes and false accepts stay at zero. **Dataset-bounded. Not an accuracy claim.**

## 13. E4 — benchmark coverage inventory

Read from `eval/bench2_gen.py`, not assumed.

**Tested in the sealed set.** Codes K=7/5/3 rate ½ plus out-of-catalogue K=9 · modulations BPSK,
QPSK, 8PSK, 16-QAM · interleavers block 12×16, diagonal 12×16, Forney convolutional (B=3, D=2), QPP
(K=192) · CCSDS RS(255,223)/(255,239) with dual basis, depth I and virtual fill · TC LDPC (128,64) ·
the full concatenated chain with randomiser and ASM · wrong-code decoys (DVB RS, linear LDPC, random
permutation) · framed-no-code and idle-carrier nulls · **channels: AWGN, Wiener phase noise
(0.5–2°/sample), linear CFO drift (±2×10⁻⁷ cycles/sample²), Rician block-flat fading (K 6–14 dB,
blocks of 64/128/256), slow amplitude variation, fractional timing offset (±0.5 sample)** · Es/N0
3, 6, 9, 12, 15 dB · random CFO ±0.008 cycles/sample and random phase.

**NOT tested in the sealed set** — the honest answer to "what happens under X?":

| Not covered | Status |
|---|---|
| Frequency-selective multipath (delay spread) | Fading is **block-flat** Rician only |
| Co-channel and adjacent-channel interference | Not generated |
| Impulsive or non-Gaussian noise | AWGN only |
| Clipping / ADC saturation | Not in the sealed set — **measured separately in E2** |
| Sample dropouts | Not in the sealed set — **measured separately in E2** |
| I/Q imbalance, DC offset | Caught by the quality gate; not a benchmark class |
| Two overlapping signals in one capture | Not generated |
| Doppler beyond linear CFO drift | Not generated |
| Receiver filter effects, single-sideband IQ | Seen on real AIR captures, not in the benchmark |

**Correction to the earlier audit.** `DOMINATION_READINESS_AUDIT.md` speculated that fading was
absent from bench-v2. Reading the generator shows Rician block-flat fading **is** covered; what is
genuinely absent is *frequency-selective* multipath. This document is correct; that guess was not.

## 14. Operator study — READY, not conducted

The 21-task protocol in `DOMINATION_READINESS_AUDIT.md` §3 was checked against the current build.
Every task is executable: all required routes exist (`/`, `/signin`, `/app/{command, analysis,
monitor, signals, signals/:id, review, incidents, spectrum, genome, intelligence, reports, system,
lab}`), and every S1 task has a real surface — UNKNOWN and SIGNAL_NO_CODE carry their meaning text,
DECODED shows what was established, provenance and `fs_source` are visible, receipts have a Verify
action, and limitations appear both in the console and in the reports.

**No blocker found. No UI change was required.** Status: **NOT ESTABLISHED** until two independent
operators actually run it.

## 15. Demo path — frozen and deterministic

| # | Step | Asset | Verified |
|---|---|---|---|
| 1 | Landing | `/` | ✓ |
| 2–4 | DECODED, evidence chain, statistical acceptance | `BENCH-QPSK-K7` (50,916 hypotheses) | ✓ committed pack |
| 5–6 | Refusal with a reason | `BENCH-SHORT-K7` → UNKNOWN, IMPOSSIBLE_IN_DOMAIN | ✓ committed pack |
| 7 | Real-world decode | `jjy40-japan-2026-09-17` → DECODED | ✓ committed replay |
| 8 | Real-world refusal | `wwvb-montana-2026-09-17` → SIGNAL_NO_CODE | ✓ committed replay |
| 9–10 | Receipt verification, then tamper detection | `evidence/ledger.jsonl` | ✓ both exercised |
| 11 | Source provenance and freshness | `/app/system` | ✓ |
| 12 | Limitations | §9 of this document | ✓ |

**The demo depends on none of:** live internet, live KiwiSDR, propagation, Salesforce, Docker,
external services, external authentication, or anything nondeterministic. Every asset is committed.

## 16. Claims that are safe

Blind analysis of `.IQ` and `.wav`; DECODED / SIGNAL_NO_CODE / UNKNOWN with genuine refusal;
0/120 sealed and 0/900 null-set false accepts; 9/9 pre-registered sealed criteria in one logged run;
real time signals decoded blind and checked against receiver GPS time to 2–23 ms; AIR carriers 5/5
against the official list; hash-chained receipts re-verifiable in a browser or by CLI; authenticated
API with four roles and 0 of 2,709 forgeries accepted; 175 tests; clean Python and Node dependency
scans; **degradation drives refusal, not error (E2: 180 runs, 0 wrong decodes)**; recall rises with
Es/N0 with 0 wrong decodes per bin (E1). An independent SIH prototype, not an official Government of
India system.

## 17. Claims that remain prohibited

AI-powered · real-time · universal · accurate / high-accuracy · guaranteed · first · novel ·
patented · better than commercial tools · production-ready · field deployed · live monitoring
network · official Government system · externally security-tested · Salesforce connected ·
"reads the message" · "identifies the sender" · any general accuracy percentage · any claim about a
named competitor.

**Final sweep result:** `frontend/src`, `README.md` and the current-facing reports contain **zero**
occurrences of these terms other than inside the lists that forbid them. Historical reports are
preserved unchanged.

## 18. Remaining risks

1. **Propagation and availability** if anyone attempts a live capture on stage — mitigated by a demo
   built entirely on committed replays.
2. **Frequency-selective multipath, interference and overlapping signals** are untested; the
   behaviour there is unknown, and is stated as unknown.
3. **Operator comprehension** is unmeasured until the two-person study runs. An S1 finding there
   would be a genuine defect.
4. **The signal-presence test is anti-conservative**, documented, and deliberately not retuned,
   because retuning after a sealed run would invalidate the single-run guarantee.

## 19. Deliberately not built

CNN or any learned classifier · Cyclic-CAF · SAGE-Lite · additional modulation, FEC or interleaver
families · a modulation classifier ahead of the code search · geolocation / TDOA · SDR hardware
integration · cloud scaling · live Salesforce · mobile application · additional UI pages ·
additional simulated monitoring · a generic AI assistant.

Verified absent at freeze: no learned-model dependency, no new modulation or FEC family, no cloud
dependency, and the air-gap design intact.

## 20. Final release decision

| Gate condition | Result |
|---|---|
| E2 passes — no wrong decode under degradation | **PASS** — 0 of 180 |
| Automated tests pass | **PASS** — 175 / 175 |
| Frontend typecheck and build | **PASS** |
| Demo path works with no external dependency | **PASS** |
| No S1 blocker in the operator-readiness check | **PASS** — no UI change required |
| No unsupported claim in current-facing material | **PASS** — zero found |

# RELEASE FREEZE — GO

**ICHNOVA is frozen for SIH. Further feature engineering is out of scope unless new evidence reveals
a Class A correctness failure.**

---

### Addendum — 22 September 2026: console presentation pass

A UI-only pass changed how the console presents existing results (themes, status shapes, verdict-first
layout, receipt layout, keyboard and reduced-motion handling). **No engine, acceptance criterion,
benchmark or evidence semantics changed**: no file under `src/`, `server/`, `eval/` or `tests/` was
touched. Re-checked: 175 / 175 tests, frontend typecheck and build pass. The 120-page viewport sweep
was not repeated for this pass. Details: `PROGRESS.md`.

### Addendum — 22 September 2026: speed and roadmap Phase 2

Still **no change to any decision, acceptance criterion, benchmark or evidence semantic.** What was
added or changed outside the console:

- `src/fingerprint.py` (new, EXPERIMENTAL): fingerprints from a finished engine result. It is not
  imported by `pipeline.py`, `blind_id.py` or the server, so it cannot influence a verdict; a test
  asserts it leaves the result unchanged.
- `eval/similarity.py` (new): Phase 2 evaluation on the synthetic null set; results in
  `reports/PHASE2_SIMILARITY_REPORT.md`.
- `server/app.py`: static files are served gzip-compressed with ETags (API behaviour unchanged).
- `server/export_frontend_data.py`: the evidence index also carries per-pack summaries, copied from
  the packs.

Re-checked: 178 / 178 tests (175 existing + 3 new).
