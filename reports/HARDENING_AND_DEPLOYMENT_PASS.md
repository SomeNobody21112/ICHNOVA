# ICHNOVA — hardening, ordering and deployment pass

Independent Smart India Hackathon prototype for problem statement **SIH26147**.
**Not an official Government of India system.**

Baseline for this pass: commit `08ee9a7` on `sih-readiness`, engine `v0.3.0`, **126 tests passing**.
After it: **169 tests passing**, 43 of them new. Every number below came from a command run during
this pass; nothing is carried forward from an earlier report without being re-run.

---

## 1. What this pass changed, in one table

| Area | Defect found | Fix | Evidence |
|---|---|---|---|
| Transaction ordering | The receipt ledger read its head and appended in two steps | `receipt.append_chained`, serialised per ledger path | `tests/test_ordering.py` — 24 concurrent writers, chain verifies clean |
| Transaction ordering | The CRM outbox read every row, changed one and rewrote the file | `_OUTBOX_LOCK` around `add` and `update` | `tests/test_ordering.py` — 24 concurrent queues, nothing lost |
| Rate limiting | `X-Forwarded-For` was believed from anyone | Honoured only from `ICHNOVA_TRUSTED_PROXIES`, rightmost hop | `tests/test_security_hardening.py` |
| Credential handling | Session tokens in the query string were written to the access log | Redacted in `log_message` | `tests/test_security_hardening.py` |
| Server-side request forgery | `POST /api/live/start?receiver=…` dialled any host and port and reported the result | Only receivers the public directory lists may be named | `tests/test_security_hardening.py`, 5 hostile targets |
| Source health | A reachable service and a green light meant the same thing | State derived from reachability **and** a freshness rule | `tests/test_sources_health.py` |
| Claims | Replays and recordings carried the pulsing **LIVE** tag | Replay → `BENCHMARK`; live and recorded split apart | `frontend/src/pages/Analysis.tsx`, `Monitor.tsx` |
| Claims | The sources panel tagged every ENGINE source **LIVE** | The feeds label is no longer a liveness badge | `frontend/src/components/sources.tsx` |
| TLS | Not addressed at all | Reverse-proxy deployment, configured and documented | `deploy/` |
| Higher modulation | No test guarded the structural alias that keeps QAM off | Four negative tests across four seeds | `tests/test_modulation_aliasing.py` |

---

## 2. Transaction ordering — the invariant that was missing

**The invariant.** *An append to either append-only store must be serialised with the read that
produced it.* Both stores are read-modify-write, and the analysis server is a
`ThreadingHTTPServer`, so both races were reachable from the API.

**The ledger.** `evidence.build_pack` read `receipts.last_hash(path)` and later called
`receipts.append(...)`. Two analyses finishing at the same moment both read the same head, both
claimed it as `prev_hash`, and the chain forked. `verify_chain` then reports a broken link at an
entry nobody touched. For this system that is worse than a missed tamper: the whole value of the
receipt is that a break means something, and a verifier that cries wolf is a verifier that gets
ignored. Fixed by `receipt.append_chained(path, build)`, which holds a per-path lock across the
read, the build and the append.

**The outbox.** `Outbox.add` and `Outbox.update` each read every row, changed one and rewrote the
whole file through `os.replace`. Two concurrent writers both wrote from the snapshot they had read,
and the later write silently dropped the earlier one's row — a case the operator was told had been
queued simply disappeared. The same race defeated the idempotency check, so a double click could
queue two cases for one decision. Fixed by a module-level `RLock` around both.

**Tests.** `tests/test_ordering.py`, 7 tests. Each pair starts with the defect stated as a
deterministic test (`test_reading_the_head_and_appending_separately_forks_the_chain`,
`test_rewriting_from_a_stale_snapshot_drops_a_case`), so if the locks are ever removed these keep
failing for the reason they were written. Then 24 threads released together by a barrier:

- 24 receipts, chain verifies clean, 24 distinct hashes and 24 distinct predecessors;
- 24 cases queued, all 24 present;
- 12 concurrent queues of the *same* decision → exactly one row, exactly one `created=True`;
- a case queued while delivery is updating rows → neither is lost.

**The ceiling, stated.** These are in-process locks. Two *processes* writing the same ledger or
outbox can still interleave; an OS file lock is the upgrade path and is marked as such in the code.
The shipped deployment runs one process (`deploy/docker-compose.yml`), so the invariant holds as
deployed, and that limit is documented rather than left to be discovered.

---

## 3. Security — what was actually attempted

Each finding below was reproduced before it was fixed and is covered by a test that performs the
attack.

### 3.1 The forwarded header bought an unlimited number of password guesses

`Handler._client` returned the first entry of `X-Forwarded-For` whenever the header was present.
`X-Forwarded-For` is a request header. A client sending a new value per request received a new rate
limit bucket per request, which removed the login limiter (10/min) and the analysis limiter (12/min)
entirely — the only brute-force defence the server had.

Fixed: the header is honoured only when the peer address is in `ICHNOVA_TRUSTED_PROXIES` (empty by
default), and then the **rightmost** entry is taken, because that is the address our own proxy
observed. Entries to its left were supplied by the client.

Measured after the fix, with the limiter at 3 per minute: eight login attempts, each with a
different forged `X-Forwarded-For`, produced a 429 by the fourth. With the proxy trusted, two
genuinely different clients still get one bucket each, and a client-prepended hop is ignored.

### 3.2 Session tokens were written to the access log

`EventSource` cannot set an `Authorization` header, so `/api/live/events` carries the session token
in the query string — a deliberate and bounded trade-off. `log_message` then wrote the request line
verbatim to stderr, putting live credentials into whatever collects it. Redacted at the log call.

### 3.3 The live-session endpoint was a server-side request forgery with an oracle

`POST /api/live/start?receiver=<host:port>` passed the operator's string straight through to
`socket.create_connection`, and the per-receiver failure was streamed back over SSE. An authenticated
analyst — or anyone at all with `ICHNOVA_OPEN_API=1` — could make the server open TCP connections to
arbitrary hosts and read back whether each one answered: internal services, cloud instance metadata,
private addresses, the analysis server itself.

Fixed at the single point all receiver selection routes through: an operator-named receiver must
appear in the public KiwiSDR directory. The station's own `preferred` list is configuration, not
input, and stays trusted. Tested against five hostile targets, plus two tests that the legitimate
uses still work.

### 3.4 Audited and found sound

| Check | Result |
|---|---|
| Password storage | scrypt n=2^14 r=8 p=1, per-password salt, `hmac.compare_digest` |
| Token forgery | Signature compared as issued text; exhaustive single-character test, 0 accepted |
| Expiry and revocation | Absolute `exp`, revocation set swept on use |
| Demo-account isolation | Distinct non-admin roles, never `ADMIN`, no password ever returned |
| Privilege escalation | Viewer → 403 on analyse, live and admin; Analyst → 403 on admin |
| Upload validation | Refused on declared length before the body is read; malformed `.iq`/`.wav` → 400 |
| Numeric input | `fs` of `fast`, `-1`, `0`, `NaN`, `Infinity` → 400 |
| Path traversal | Four encoded probes → 400/404, no source file served |
| Error leakage | No traceback, path or library name in any error body |
| Security headers | CSP `default-src 'self'`, nosniff, `no-referrer`, `DENY`, Permissions-Policy |
| CORS | No `Access-Control-Allow-Origin` emitted, checked with a hostile `Origin` |
| CSRF | **Not applicable.** The console authenticates with a bearer token from `sessionStorage`, never a cookie, so there is no ambient credential for another origin to ride |
| Bulk data to the CRM | `assert_no_bulk_data` refuses samples, audio and views; enforced on a fixed field list |
| Secrets | No credential, key or certificate in any tracked file; `deploy/certs`, `deploy/config`, `deploy/.env` ignored |

### 3.5 Limitations that remain

- The rate limiter is a fixed window in one process. It stops a loop; it is not a defence against a
  distributed flood, and it does not survive a restart.
- Sessions are stateless and signed. Without `ICHNOVA_SECRET_KEY` a restart invalidates every
  session, which is safe but is not session persistence.
- The revocation set is in memory. A logout does not survive a restart — it does not need to, since
  the restart invalidates everything, but with a fixed key it would.
- `ICHNOVA_OPEN_API=1` disables authentication entirely. It exists for an offline single-user
  workstation and must never be set on anything reachable.
- No penetration test by anyone other than this pass. No dependency CVE scan was run here; the
  runtime dependencies are numpy and scipy only.

---

## 4. TLS — **IMPLEMENTED / CONFIGURED**, not live

`deploy/` now carries an HTTPS reverse-proxy deployment: `nginx.conf`, `docker-compose.yml` and a
`README.md` with the issuing, renewal and verification steps. It covers HTTPS with modern ciphers, an
HTTP→HTTPS redirect, certificate configuration through ACME or an internal CA, forwarded-header
handling that matches what the application now expects, restrictive CORS (none), the health endpoint,
proxy connection and request limits, an upload cap that matches `MAX_UPLOAD`, and timeouts long
enough that a slow-but-correct analysis is not turned into a 504.

The application does not terminate TLS and is not meant to.

**What is not established:** no certificate has been issued for a real host from this repository, no
traffic has been served through this configuration, and the stack has never been operated in
production. It is marked CONFIGURED for that reason, and `deploy/README.md` §5 says so in its own
table.

---

## 5. Source health — what a green light is now allowed to mean

The registry previously reported `AVAILABLE / DEGRADED / UNAVAILABLE / NOT CONFIGURED`, where
AVAILABLE meant only that a check had succeeded. Two things followed that should not have:
published specifications reported AVAILABLE with a green dot, and a receiver network reported
AVAILABLE on a directory that answered even when nothing had been received from it for days.

The state is now **derived**, by `SignalSource.health_state`, under two rules:

1. **A source that cannot produce a verdict never reports a liveness state.** It reports
   `REFERENCE ONLY` or `METADATA ONLY` instead, so no indicator ever sits beside documentation as
   though it were a feed.
2. **ONLINE requires a recent observation, not merely a reachable service.** Each source declares a
   freshness window; reachable-but-nothing-recent is `STALE`, with the age and the window both
   published in the response so the rule can be checked rather than trusted.

Vocabulary: `ONLINE · DEGRADED · STALE · OFFLINE · AUTH_REQUIRED · UNSUPPORTED · NOT CONFIGURED ·
REFERENCE ONLY · METADATA ONLY`. `AUTH_REQUIRED` and `UNSUPPORTED` exist so a source that needs
credentials or offers nothing usable can say so instead of being called OFFLINE. **No source in this
registry produces either today**, and a test records that fact so neither is presented as exercised.

Current registry, from `python server/sources.py` with the network check skipped:

| Source | Feeds | Freshness window | State |
|---|---|---|---|
| Public KiwiSDR receiver network | ENGINE | 24 h | measured per check; STALE when nothing recent |
| Operator-supplied capture | ENGINE | not applicable — a local capability, not a stream | ONLINE when the endpoint is up |
| Benchmark generator | ENGINE | not applicable | ONLINE when the sealed set is present |
| Published transmission specifications | REFERENCE ONLY | — | REFERENCE ONLY |
| SatNOGS open ground-station network | METADATA ONLY | — | METADATA ONLY |

**One live-capable external source, one local capability, one local generator, one reference-only
source, one metadata-only source.** The console shows *Last observation* as a timestamp with the
freshness beside it.

---

## 6. Evidence receipts — tamper detection, re-exercised

Run during this pass against a copy of the shipped ledger (6 entries), through the CLI a third party
can use without running ICHNOVA: `python server/verify_receipt.py --ledger <path>`.

| Ledger | Exit | What the verifier said |
|---|---|---|
| Untouched | 0 | `checked: 6`, no problems, head `7b607f03…` |
| One decision altered in place | 1 | index 2 — `content does not match its hash (recomputed 8b7c27ac…, stored 82ebeb65…)` |
| One entry deleted | 1 | index 2 — `broken link: prev_hash 82ebeb65… does not match the previous receipt 0bd64178…` |
| Two entries swapped | 1 | indexes 1, 2 and 3 — three broken links |

Each failure names the affected position. The browser verifier recomputes the same chain from the
raw ledger text, and `.jsonl` is on the no-store list so a tampered ledger cannot verify green from
cache — a defect found and fixed in an earlier pass and not re-broken by this one.

---

## 7. Higher-order modulation — still EXPERIMENTAL, now with negative tests

Nothing about the status changed, and nothing should have: the evidence in
`reports/HIGHER_MODULATION_EXPERIMENT.md` still stands. What was missing was a test guarding the
specific failure — a structural alias, where a higher-order constellation explains a lower-order
signal, every statistic is satisfied, and the answer is confidently wrong.

`tests/test_modulation_aliasing.py`, 15 tests across four seeds:

- the default search never answers a clean BPSK capture with a gated modulation, and decodes it
  bit-exactly;
- with the search forced on, the 8PSK gate stays **closed** on a capture whose fourth-power
  signature contradicts it — that is the path that produced the 40 %-wrong answer;
- the 16-QAM gate stays closed on a constant-modulus capture, compared against the engine's own
  `ALPHA` rather than a threshold written into the test;
- forcing the search must not *improve* a capture the default already decodes. If it ever returns a
  higher-order answer that is also bit-exact, the test fails and says to re-run the experiment
  before the EXPERIMENTAL label is touched.

The research direction is unchanged and is the right one: modulation characterisation → modulation
selection → code search, not try-everything-and-pick-what-looks-good.

---

## 8. What this pass did **not** do

Stated plainly, because partial completion is not completion.

- **No browser-rendered visual sweep.** The instruction was to fix a figure card whose Accept button
  sits about 22 px below the fold, and to sweep 1366×768, 1440×900, 1920×1080 and 390×844.
  **There is no Accept button and no figure card in this codebase** — `grep -rni "accept
  button\|below the fold"` across source and documentation returns nothing, and the review cards
  carry Mark known / Add to library / Request deep analysis / Dismiss. No browser automation is
  available here either: the Chrome DevTools MCP server failed to connect, and neither Playwright nor
  Puppeteer is installed. Claiming a four-viewport verification would be exactly the kind of
  unsupported claim the rest of this document exists to remove. One real clipping defect of the same
  family was found by reading and fixed: `Analysis.tsx` overrode the shared `.result-summary` rule
  down to a 90 px scroll box; the override is gone.
- **No micro-status clutter to remove.** Searching for "100 completed", "100%" or "X completed" above
  a primary button returns nothing. Nothing of that kind was added either.
- **No new performance measurement.** `reports/PERFORMANCE_REPORT.md` stands unchanged. This pass
  made no claim about latency or throughput, so it measured none.
- **No benchmark re-run.** The sealed corpus and its pre-registration are untouched, by design. No
  measurement in this pass went near it.
- **No Salesforce connection.** The outbox architecture is unchanged and still correct: nothing is
  reported SENT without a record id, and an unconfigured installation says NOT CONFIGURED. No org has
  ever been connected, and this pass did not change that.
- **No field deployment.** Unchanged, and still the honest distance between this prototype and an
  operational system.

---

## 9. Test position after this pass

`169 passed` in 65 s from `python -m pytest -q tests`, and `npm run build` clean (type-check and
bundle). The 43 new tests:

| File | Tests | What it protects |
|---|---|---|
| `tests/test_ordering.py` | 7 | Ledger chain and outbox integrity under concurrency |
| `tests/test_security_hardening.py` | 11 | Forwarded-header trust, token redaction, receiver SSRF |
| `tests/test_sources_health.py` | 10 | Health vocabulary, the freshness rule, no permanent green |
| `tests/test_modulation_aliasing.py` | 15 | Structural aliasing, and the evidence behind EXPERIMENTAL |

Every one was written to fail if the behaviour it protects regresses, and the four that reproduce a
defect were confirmed to fail against the code as it stood before the fix.
