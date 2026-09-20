# ICHNOVA — final verification pass

Independent Smart India Hackathon prototype for problem statement **SIH26147**.
**Not an official Government of India system.**

This pass added almost no features. Its job was to **check whether the previous pass's claims were
true**, and to close the verification gaps that pass had honestly recorded as open. Most are now
closed; one is closed differently than expected; one remains open with the reason stated.

Baseline: **169 tests**. After: **175 tests**. Every figure below came from a command run during
this pass.

---

## 1. What changed, and what merely got checked

| Area | Before this pass | Now | How |
|---|---|---|---|
| Browser visual verification | Recorded as impossible here | **DONE** — 120 pages measured, 1 defect found and fixed | Chrome over CDP, no new dependency |
| Dependency CVE scan | Recorded as not executed | **DONE** — 0 findings, Python and Node | `npm audit`, OSV API |
| Browser receipt verifier | Asserted, never driven | **VALIDATED** — detects a real tamper in a real browser | CDP, ledger altered on disk |
| Multi-process file writes | Documented as a limitation | **ENFORCED** — a second process refuses to start | `server/store_lock.py` |
| Ledger append cost | Unmeasured | **MEASURED** — linear; 11 ms at 100 entries, 505 ms at 100k | Direct measurement |
| Rate limiter / revocation semantics | Scattered through code comments | **DOCUMENTED**, including what they do *not* protect | `deploy/README.md` §6 |
| TLS chain exercised locally | Not attempted | **STILL NOT EXERCISED** — Docker daemon down, nginx absent | §5 below |

---

## 2. Browser visual verification — **DONE**

The previous pass reported that no browser automation existed. That was true of Playwright,
Puppeteer and Selenium, none of which are installed, and of the Chrome DevTools MCP server, which
failed to connect. It was **wrong as a conclusion**: Chrome itself is installed, and
`server/kiwi.py` already contains a complete RFC 6455 WebSocket client written for KiwiSDR. The
DevTools Protocol needs exactly those two things. The sweep was built on them with no new
dependency, as a throwaway harness outside the repository.

**Coverage: 15 routes × 4 viewports × 2 themes = 120 pages measured.**

Routes: landing, sign-in, command, monitor, analysis, signal library, signal detail, review,
incidents, spectrum, genome, intelligence, reports, system, lab. Viewports: 1366×768, 1440×900,
1920×1080, 390×844. Themes: dark and light.

Each page was measured in the DOM, not eyeballed, for: horizontal page overflow; interactive
elements clipped by an ancestor with `overflow: hidden`; elements outside the viewport, separated
from those inside a strip the user can genuinely scroll sideways; text truncated by hidden overflow
with no ellipsis; content cut vertically; tap targets under 20 px; and routes that rendered nothing.

### The one real defect, and its root cause

| | |
|---|---|
| Where | Landing page, second call to action, "Watch a real signal" |
| When | 390×844 only, **both themes**; all three desktop viewports were clean |
| Symptom | Button 4 px outside `.landing`, which has `overflow-x: hidden`, so it was cut |
| Root cause | At ≤1100 px `.land-hero` became `grid-template-columns: 1fr`. A grid column's implicit `min-width` is `auto`, so the column grew to its max-content width, the flex row inside it had room it should not have had, and it never wrapped |
| Fix | `minmax(0, 1fr)` — one token |
| Verified | Re-ran the full sweep: **0 clipping defects, 0 offscreen elements outside a scrollable strip** |

That is the genuine article of the class the earlier instruction described as "a button about 22 px
below the fold". There is still no element called Accept and no card called a figure card in this
codebase; what existed was a primary action cut off on a phone, and it is fixed.

### What the sweep found that is not a defect

48 findings at the mobile viewport are interactive elements sitting outside the viewport **inside a
horizontally scrollable strip** — the tab bars on lab, signals, signal detail, spectrum and
intelligence, and two buttons inside scrollable table wrappers. They are reachable by scrolling. The
checker separates these from real clipping precisely so they are not counted as defects.

**Observation, not a defect, and deliberately not "fixed":** `.tabs` sets `scrollbar-width: none`,
so on a phone there is no visual cue that the strip scrolls. On a desktop operations console that is
a reasonable trade; on a phone it costs discoverability. Recorded here rather than restyled, because
the console is not a phone product and inventing a scroll affordance is not a verification task.

**Empty, error and loading states** were exercised only incidentally: every one of the 120 pages
rendered more than 40 characters of content, so no route was blank and none failed to measure. No
route-level error state was *forced*, so those are not claimed as verified.

---

## 3. Dependency security — **SCAN EXECUTED, 0 findings**

| Ecosystem | Tool | Scope | Result |
|---|---|---|---|
| Node | `npm audit` | 91 dependencies (19 prod, 71 dev, 46 optional, 6 peer) | **0 vulnerabilities**: 0 critical, 0 high, 0 moderate, 0 low, 0 info |
| Python | OSV API (`api.osv.dev/v1/query`) | numpy 2.4.2, scipy 1.17.0, pytest 9.1.0 | **0 advisories** for each |

The Python runtime dependency surface is two packages, which is itself the strongest thing that can
be said about it: `requirements.txt` is `numpy==2.4.2` and `scipy==1.17.0`, and the server, the
authentication, the receipts and the CRM outbox are standard library only.

`pip-audit` is not installed here, so the OSV advisory database — the same one `pip-audit` queries —
was called directly rather than installing tooling into the user's environment.

**Not scanned, and not claimed:** the OS packages inside the `python:3.11-slim` and `node:22-slim`
base images. That needs an image scanner (Trivy, Grype, `docker scout`) and a running Docker daemon;
the daemon is not running here. **Container base-image CVE status: NOT ESTABLISHED.**

---

## 4. Evidence receipts — CLI **and** browser, both exercised

### CLI verifier

Untouched ledger → exit 0, `checked: 6`, no problems. One decision altered → exit 1, names index 2.
One entry deleted → exit 1, broken link at index 2. Two entries swapped → exit 1, three broken links.

### Browser verifier — newly exercised, and it works

Previously this was asserted from the source. It has now been driven in a real browser: open the
signal record's audit tab, press **Verify receipt**, read what the page says; then alter one
decision in the ledger on disk and press it again.

| | What the page said |
|---|---|
| Clean | "Entry 1 of 6 in evidence/ledger.jsonl, shipped with this build." · "6 receipts checked, each carrying the hash of the one before it. Head 7b607f03d540370d…." · **"Every hash recomputed here matches the stored ledger."** |
| Tampered | "Chain links intact" → **"entry 2: content does not match its hash (recomputed d5ce7ff74111…, stored 0bd64178ffe6…)"** · banner: **"Verification failed. Treat this decision as unproven: the record does not match what it claims."** |

Both ledgers were backed up first and restored byte-for-byte; `frontend/dist/evidence/ledger.jsonl`
is byte-identical to `frontend/public/evidence/ledger.jsonl` and both verify clean.

**A note on how this nearly went wrong, because it matters more than the result.** The first run
reported that the browser accepted a tampered ledger. It had not: the harness set the decision
status to `DECODED` on an entry that was *already* `DECODED`, rewrote the file identically, and
proved nothing. A tamper test that changes nothing always passes. The harness now asserts the file
bytes moved before drawing any conclusion. Without that check this document would have reported a
serious defect that did not exist.

---

## 5. TLS — still **IMPLEMENTED / CONFIGURED**, still not exercised

No change, and no upgrade of the claim. The configuration in `deploy/` was re-read against the
application it fronts and is consistent: the upload cap matches `MAX_UPLOAD` (64 MB), forwarded
headers match what `Handler._client` now expects, SSE has buffering off and a long read timeout, the
health endpoint is routed, HTTP is redirected with 308, and no CORS header is added anywhere.

**It was not exercised, and here is exactly why:** the Docker daemon on this machine is not running
(`failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine`), and nginx is
not installed natively. Without either, neither the compose stack nor `nginx -t` can run, so the
configuration has not been machine-validated, let alone served traffic. Standing up a Python TLS
socket instead would have tested nothing that `deploy/nginx.conf` actually says.

**TLS status: CONFIGURED. Not locally exercised. Not production. Not live.**

---

## 6. One writer per results directory — **ENFORCED**, not merely documented

The previous pass closed the concurrency hole within a process and honestly recorded the remaining
one: two *processes* on the same results directory would each read the ledger head and each append
against it, forking the chain.

The fix is not to make every append cross-process safe. It is to make the unsafe configuration
impossible. `server/store_lock.py` takes an exclusive OS lock on the results directory at start-up
(`fcntl.flock` on POSIX, `msvcrt.locking` on Windows) and holds it for the process lifetime.

Verified by actually starting two servers:

```
refusing to start: another ICHNOVA process is already writing
...\repo\results (last recorded holder: pid 15768, since 2026-09-19T22:15:57Z). The receipt
ledger and the CRM outbox are safe for one process only: a second writer forks the evidence
chain. Stop the other process, or give this one its own results directory.      [exit code 1]
```

Six tests, two of which start a genuinely separate interpreter — an in-process test cannot prove
this, because on POSIX a second `flock` from the same process succeeds. `deploy.replicas: 1` is now
explicit in the compose file, with the reason.

**Two implementation defects were found and fixed while building this**, both Windows-specific and
both found by running it rather than reading it: `msvcrt.locking` takes a *mandatory* lock, so a lock
on byte 0 also stopped anyone reading the holder's pid out of the file; and a handle whose lock
attempt has failed is left in an error state by the CRT, so every later read on it raises
`PermissionError`. The lock file now carries no data at all and the readable record lives beside it.

**Still NOT ESTABLISHED:** two ICHNOVA hosts against one shared network filesystem. Out of scope,
and nothing here makes it safe.

---

## 7. Performance — **DEVELOPMENT MEASUREMENT** only

There is still no "Bryman" anything in this repository; searching `reports/` and
`sih26147-constitution/` for "Phase F", "Phase G", "Phase H" and "Bryman" returns nothing. No
substitute was dressed up as one.

`eval/perf.py` was re-run for one reason — to check the ordering locks cost nothing — and the numbers
are in `reports/PERFORMANCE_REPORT.md` under a heading that says DEVELOPMENT MEASUREMENT and explains
why it is not a controlled comparison. The earlier table was not touched.

The measurement that *is* new and useful: the ledger append reads the whole ledger to find the head,
inside the writer lock. It is linear — 10.9 ms at 100 entries, 17.0 ms at 1,000, 64.1 ms at 10,000,
505 ms at 100,000 — and becomes the dominant cost somewhere between 10,000 and 100,000 receipts
against a ~0.15 s analysis. The deployed ledger holds 153. Verifying a 100,020-receipt chain end to
end took 1.8 s, so verification does not degrade the same way.

The O(1) upgrade is now *sound* because a process provably owns the directory, and is deliberately
not implemented: 153 receipts do not justify it.

---

## 8. Claim audit

The repository was searched for every term on the list — production-ready, field-tested, real-time,
secure, deployed, Salesforce connected, accuracy, best, first, unique, novel, 100%, general accuracy.

**One unsupported claim found and removed.** `COMPLETION_AND_UVP.md` UVP 1 said *"Most signal tools
always return an answer; this one returns an answer only when it can defend it."* We have not
surveyed other tools. It now states what this system does and the rate at which it refuses.

Everything else that matched is legitimate and was left alone: "best hypothesis" is the technical
term for the top-ranked candidate; "general accuracy" appears only inside denials of it; "guaranteed",
"universal" and "real-time interception" appear only in the Constitution's own list of claims that
must never be made; "Real time codes" means standard-time transmissions; and the Novelty Audit's use
of "novel" is scoped to a literature search it documents.

---

## 9. Status of every claim after this pass

| Claim | Status |
|---|---|
| SIH26147 engine requirements (RS, LDPC, concatenated, interleavers, framing, provenance) | **VALIDATED** |
| Sealed benchmark bench-v2, 9/9 pre-registered criteria | **BENCHMARK** — untouched by this pass |
| bench-v1 regression tripwire | **VALIDATED** — 30/30, 0 false accepts, re-run |
| Authentication, RBAC, rate limiting | **VALIDATED** |
| Forwarded-header trust, token redaction, receiver SSRF | **VALIDATED** — attack tests |
| Transaction ordering within a process | **VALIDATED** — 24-thread tests |
| Single writer per results directory | **VALIDATED** — enforced, two-process test |
| Evidence receipts, CLI verifier | **VALIDATED** |
| Evidence receipts, browser verifier | **VALIDATED** — driven in Chrome against a real tamper |
| Console layout, 4 viewports × 2 themes | **VALIDATED** — 120 pages measured |
| Dependency CVEs, Python and Node | **VALIDATED** — 0 findings |
| Container base-image CVEs | **NOT ESTABLISHED** — no scanner, no daemon |
| TLS reverse-proxy deployment | **CONFIGURED** — not exercised, not live |
| Live Indian signal sources | **LIVE** for one source (public KiwiSDR), under a freshness rule |
| Ledger append scaling | **DEVELOPMENT MEASUREMENT** |
| Engine performance | **DEVELOPMENT MEASUREMENT** — no validated benchmark claimed |
| 8PSK / 16-QAM | **EXPERIMENTAL** — unchanged, guarded by negative tests |
| Salesforce | **IMPLEMENTED**, not configured, **never connected to a real org** |
| Field deployment | **NOT ESTABLISHED** |
| General accuracy figure | **NOT CLAIMED** |
| External penetration test | **NOT ESTABLISHED** — the only adversarial testing is our own |

---

## 10. Re-verification and a live run — 2026-09-20

A later pass re-checked this document's claims rather than trusting them, and closed one open item.

**Re-verified by running it, not by reading it:**

| Claim | Result |
|---|---|
| 175 tests pass | **175 passed** in 155 s |
| Frontend typecheck and build clean | `tsc --noEmit` exit 0; build succeeded |
| Node dependencies clean | `npm audit --omit=dev`: **0 vulnerabilities** |
| CLI receipt verifier | Shipped ledger: exit 0, 6 checked. Tampered copy: **exit 1**, names index 2 |
| Mobile landing fix present | `.land-hero` at ≤1100 px uses `minmax(0, 1fr)` |
| One-writer enforcement present | `server/store_lock.py` in place |
| No completion theatre in the UI | No fake percentage, sync or LIVE indicator found |
| Everything pushed | `origin/main` = `origin/sih-readiness` = local HEAD |

The tamper test asserts the file bytes actually changed **before** verifying, so it cannot pass
vacuously — the trap §4 describes. Both tamper tests ran on copies in a scratch directory; the
repository's own ledgers were never modified, and `git status` is clean.

**Live source exercised end to end — the gap §9 of the brief asked to close.**

A 12-second capture was taken from a public KiwiSDR at 720 kHz and put through the whole chain:

| Stage | Result |
|---|---|
| SOURCE | Public KiwiSDR, Cha-Am, Thailand — 2,135 km from the Chennai transmitter, GPS-timed |
| INGEST | 144,384 samples @ 11,998.881 Hz; rate declared by the receiver |
| QUALITY | **GOOD**, no issues |
| AM receiver | Carrier offset −1.473 Hz, **carrier-to-noise 61.3 dB**, modulation depth 0.283, audio bandwidth 4,447 Hz |
| ANALYSIS | 0 FEC hypotheses reached the code search |
| DECISION | **SIGNAL_NO_CODE** |
| EVIDENCE | Receipt `5db9c8207a7ccbfb`, capture `9095ae2af2aa5d8a`, chain verifies clean |

This is the system behaving as designed on real radio: a strong AM broadcast carrier is plainly
present, and the engine declined to claim a catalogue code for it, because an AM broadcast has none.

**What this does not establish.** The only receiver available was 2,135 km away, far outside the
800 km range configured for the Chennai transmitter. At that distance on 720 kHz the carrier heard is
**not established to be All India Radio Chennai** — it may be another medium-wave station, or
skywave. What is established is a live public-SDR capture, a real AM carrier, a GOOD quality gate, an
honest SIGNAL_NO_CODE and a verifiable receipt. **Station identity: NOT ESTABLISHED.**

**Still blocked, unchanged:** the Docker daemon is not running, nginx is not installed, and none of
`trivy`, `grype` or `pip-audit` is present. TLS remains **CONFIGURED, never exercised**, and
container base-image CVEs remain **NOT ESTABLISHED**. No substitute was run and labelled as either.

---

## 11. What is still open

1. **TLS has never served traffic.** Needs a Docker daemon or a native nginx.
2. **Container base images are unscanned.** Needs an image scanner.
3. **No external security review.** Every attack tested here is one we thought of.
4. **No field deployment**, no operator feedback, no incident history.
5. **Two hosts on one shared filesystem** is unsafe and unaddressed by design.
6. **Mobile tab strips give no scroll cue.** Known, measured, judged not worth changing.

None of these is hidden in the interface or in the documents, which is the only property this
project has ever claimed about its own gaps.
