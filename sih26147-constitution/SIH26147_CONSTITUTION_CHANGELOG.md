# SIH26147 — CONSTITUTION CHANGELOG

## v2.5.4 — 2026-09-20 — Deployment amendment: one writer, honest freshness, TLS configured

No rule, weight, catalogue item or acceptance threshold changed. The document is brought level with
a hardening pass and a verification pass that both landed after v2.5.3.

- **§9.12 — one writer per results directory.** The receipt ledger and the CRM outbox are
  append-only files whose head is read before each append. Two processes on one results directory
  each append against the head they read, which forks the evidence chain — precisely what a receipt
  exists to prevent. The response was not to make every append cross-process safe, but to make the
  unsafe configuration impossible: `server/store_lock.py` takes an exclusive OS lock on the
  directory at start-up (`fcntl.flock` on POSIX, `msvcrt.locking` on Windows) and a second process
  refuses to start, naming the holder. `deploy/docker-compose.yml` pins `deploy.replicas: 1` with
  the reason. Proven by starting two servers, not by reading the code. Two hosts against one shared
  network filesystem remains unsafe and **NOT ESTABLISHED**.

- **§9.13 — reachable is not fresh.** A source that answers is not a source that is delivering. A
  reachable receiver network with no recent data now reports STALE rather than a green light, and
  "last received" is read from what this installation actually received.

- **Limitation 8 rewritten.** A TLS reverse proxy is **CONFIGURED** in `deploy/` and consistent with
  the application it fronts, but has **never been exercised or served traffic** — no Docker daemon
  and no native nginx on the development machine. It is not upgraded to LIVE on the strength of
  being written down. Container base-image CVEs are **NOT ESTABLISHED**: no image scanner is
  available. Python and Node dependency scans are clean.

- **Limitation 8a added.** Rate limiting and session revocation are in-process and in memory. They
  protect one process and are not a distributed quota; a restart clears both, which invalidates every
  issued session when `ICHNOVA_SECRET_KEY` is unset — the safe direction. No database was introduced
  to make demo sessions persistent, because §9.2 keeps the engine air-gap capable.

## v2.5.3 — 2026-09-19 — Platform amendment: authenticated API, approved CRM, evidence receipts

No rule, weight, catalogue item or acceptance threshold changed. The document is brought into
agreement with an engine and a web tier that had moved past it.

- **§25.8 — the API is authenticated.** Passwords are stored with `hashlib.scrypt`
  (n = 2¹⁴, r = 8, p = 1); sessions are HMAC-SHA256 tokens carrying an absolute expiry and a
  revocation id; every endpoint but `/api/health` and the sign-in routes requires a token, and each
  is checked against a role permission server-side. A fixed-window rate limiter answers 429 with
  `Retry-After`. The standing limitation "unauthenticated API" is therefore **retired**; what
  remains is that `http.server` terminates no TLS, so a deployment needs TLS in front of it.
  `ICHNOVA_OPEN_API=1` restores the open behaviour for a single-user offline workstation.
  Measured: 2,709 single-character forgeries of a valid signature, 0 accepted.

- **§9.2 — one cloud integration approved.** The clause required any CRM to have its own amendment;
  this is it. The Salesforce case hand-off (`server/crm.py`) writes a case to a local append-only
  outbox, and delivery is a separate explicit step, so no analysis waits on it or fails without it.
  The record is built from a fixed field list — decision, statistics, receipt hash — and
  `assert_no_bulk_data` refuses any payload carrying IQ, payload bits, views, audio or oversized
  fields. An item is marked SENT only on a Salesforce record id: an unconfigured or unreachable CRM
  reports that it delivered nothing rather than claiming success. Credentials are environment-only.
  No Salesforce organisation has ever been connected, so the integration is IMPLEMENTED, not LIVE.

- **Three orthogonal reports recorded, none of which may change a verdict.**
  `src/quality.py` grades the capture GOOD / DEGRADED / FAILED on clipping, DC offset, dropouts,
  I/Q balance, non-finite samples and declared rate — reported beside the verdict, never part of it.
  `src/sufficiency.py` states what would settle a refusal, in parity checks derived from the sign
  test that refused it, and separates ACHIEVABLE from IMPOSSIBLE_IN_DOMAIN, STRUCTURALLY_REJECTED and
  NO_TREND so no refusal asks for capture that cannot help. `src/receipt.py` chains decisions by
  SHA-256 so a decision can be re-verified by someone who does not trust this system; the console
  recomputes the chain in the browser.

- **`server/sources.py` — signal provenance is declared, not assumed.** Five sources, each carrying
  who operates it, under what terms, what it may feed (ENGINE / REFERENCE ONLY / METADATA ONLY) and
  health measured on request. Only publicly offered, openly documented transmissions are listed.

- **§24 row 34 re-measured** over the full 1,350-capture null set
  (`reports/HIGHER_MODULATION_EXPERIMENT.md`). Enabling 8PSK/16-QAM decodes 0 of 100 8PSK captures
  while raising the search a median 21.8× and runtime 7.2×; false accepts are 0/800 either way, so
  the original concern was not the real one. The real cost is a wrong decode: `k5_060_003`, BPSK,
  decodes bit-perfectly with the gate off and as 8PSK with a stronger p-value and a 40 %-wrong
  payload with it on — a structural alias whose parity checks genuinely pass. The gate stays off,
  now for a measured reason, and the path to changing that is named: a modulation classifier
  confident enough to choose the constellation before the code search.

## v2.5.1 — 2026-09-18 — Status amendment: families F1–F4 in the engine

No rule, weight or catalogue item changed. Acceptance families F1–F4 (§13.1) were implemented in
`src/pipeline.py`, so §24 is brought into agreement with what is now measured:

- **Row 33 (frame sync / bit-stream correlation)** LOCKED → IMPLEMENTED, measured: family F3 finds
  the CCSDS ASM blind at P = 512 and P = 2,072 with a header/payload map, reports SIGNAL_NO_CODE for
  a framed stream with no code, and refuses noise and an idle carrier.
- **Row 35 (Reed-Solomon, concatenated)** LOCKED → IMPLEMENTED, measured: the full CCSDS chain
  (RS(255,223) E = 16, I = 1 + TM 131071 randomizer + ASM + inner K7) decodes blind with every
  parameter identified and payload BER 0, on the exact tail statistic, with degenerate codewords
  refused.
- **Row 36 (diagonal / convolutional / QPP interleavers, TC LDPC)** LOCKED → IMPLEMENTED, measured:
  all four interleaver types are in the default search with bench-v1 and the null set unchanged
  (sealed 30/30, 0/900 false accepts) and wrong-structure accepts improved from 2/225 to 0/225; a TC
  LDPC CLTU decodes blind with 1,536/1,536 satisfied checks.
- **Row 36b (randomizers)** LOCKED → IMPLEMENTED, verified against the published bits and identified
  blind as part of an F4 hypothesis.
- **Row 34 (8PSK, 16-QAM)** LOCKED → **EXPERIMENTAL, off by default**. Both modulations decode blind
  when enabled (payload BER 0 at 20 dB; development sweep 18/96 bursts at Es/N0 11–20 dB, 0 wrong
  decodes), but enabling them by default was measured to cost bench-v1 sealed 5 of 30 files, to add
  one null false accept (1/900) and one wrong K5 decode, and to raise runtime about 20×: on a weak or
  short capture the QPSK y⁴ signature is not significant because the capture is weak, so the gate
  opens without higher-modulation evidence and M₁ grows about tenfold. Moving them into the default
  path therefore needs a real amendment (an F1 sub-weight split and a gate with a power condition),
  and §12.1 now says so.

The default engine path is unchanged by this amendment: 0 decision differences on all 1,350 null-set
files, sealed 30/30, train 63/100.

## v2.5 (SIH-readiness amendment, 2026-09-17)

Triggered by the engineering & SIH readiness audit (2026-09-17). Nothing measured changed at the time of amendment. The amendment **pre-registers** design decisions before implementation.

| Item | v2.4 | v2.5 |
|---|---|---|
| Priorities (audit C5) | bench-v2 → detection calibration → waterfall → frame sync; RS/QAM P1; LDPC and interleavers P2 | Explicit SIH26147 capabilities are **P0** under the existing acceptance discipline (§35); CRM, list diff, canaries, pooling DEFERRED |
| Catalogue | BPSK/QPSK, K7/K5/K3, block interleaver | Catalogue v1 (§12.1): + 8PSK, 16-QAM, diagonal/convolutional/QPP interleavers, CCSDS ASM + blind frame sync, CCSDS randomizers, CCSDS RS dual basis + depth, concatenated, CCSDS TC LDPC (128,64). Each item cites its defining document |
| Multiple testing | One Bonferroni bar α/M | Weighted Bonferroni families F1–F4 (0.5 / 0.1 / 0.2 / 0.2), file-level bound α unchanged (§13.1); RS success alone never accepts |
| Benchmarks | bench-v2 described as future | bench-v2 policy: calibration/train/sealed splits, committed sealed manifest, criteria committed before any sealed run, access log (§18.1) |
| Sample rate (audit C1) | "Told to the engine" | `fs_source` provenance; no silent default (§10) |
| Cloud (audit C9) | Silent on optional cloud integrations | One-way, never required, needs its own amendment; none approved (§9.2) |
| Verification header (audit C7) | `cb51397` | `acf4201` + re-measured baseline report |
| Terminology (audit C2–C4) | "held-out split" in UI/CURRENT_STATE/PROGRESS; withdrawn "93%" still listed in NOVELTY_AUDIT | "evaluation split"; PROGRESS annotated as historical; NOVELTY_AUDIT line struck through with the reason. Earlier changelog entries are left as written (history) |

Baseline re-measured before any change (`reports/AUTONOMOUS_EXECUTION_BASELINE.md`): tests 30/30, sealed 30/30, train 63/100, null set 0/900 and 0/450. One count differs from v2.4 §19: uncoded QPSK → UNKNOWN is 122/150, not 121.

## v2.4 (consolidated single source of truth, 2026-09-17)

The Constitution was rewritten so that it alone describes the whole project. Nothing measured changed; everything stale was corrected.

| Item | v2.0/v2.1 text | v2.4 |
|---|---|---|
| Authority | Constitution + roadmap + rescue spec + current state in parallel | Constitution governs everything; document map (§3); CURRENT_STATE is a derived snapshot; roadmap and rescue spec marked HISTORICAL |
| Identity | "SIH26147" only | **ICHNOVA** brand, taglines, disclaimer, forbidden name/emblems (§1, §26) |
| Thesis | Decoding as a sensor (SAGE-Lite next) | **Evidence first** is operative; decoding as a sensor kept as a BLOCKED research direction with reasons (§5, §36.3) |
| Acceptance | Re-encode consistency ≥ 0.98 | Sign test + Bonferroni + MC/BL/PM; consistency RETIRED (§13) |
| Baseline | 28/30 → 30/30, 60/100 | 30/30 and 63/100 with 0 false accepts; sealed renamed a tripwire (§8.3, §18) |
| Evidence | Sealed set only; real IQ "not yet executed" | Null set, wrong-structure null, scoring comparison, oracle ladder, 8 real transmissions, performance (§19–§23) |
| Status table | 17 rows in constitution, 40 in current state | 47 rows, authoritative, in the constitution (§24) |
| Product | "GUI — outside MVP" | Operator console, routes, data honesty, UX/accessibility/theme rules modelled on DoT Tarang Sanchar / Saral Sanchar (§27–§29) |
| Runtime | ~8.6 s per file | Sealed 1.5 s, train 4.4 s (§23) |
| Environment | Python 3.12.3, numpy 2.4.4, scikit-learn, matplotlib | Python 3.11, numpy 2.4.2 + scipy 1.17.0 only (§31) |
| Claims | "93% blind payload recovery on sealed held-out" allowed | **Withdrawn**; may-say / must-not-say lists rewritten (§37) |
| Governance | — | Quality gates (§32), workflows (§34), risk register and change control (§41, §46) |

---

## v2.3 (2026-09-17) — structural acceptance, real transmissions, performance

- Wrong-structure null exposed 17.3% wrong accepts under the syndrome-only rule; adopted MC + BL + PM checks: 0/900 false accepts, 0/450 wrong decodes, 0.9% wrong-structure (held-out split). `reports/STRUCTURAL_ACCEPTANCE_REPORT.md`
- Government transmissions received blind through public KiwiSDR receivers: JJY, DCF77, MSF, WWV decoded (GPS +1.9…+23.4 ms), WWVB time refused, DWD DDH47 ITA2 text, AIR MW 5/5. `reports/REAL_SIGNAL_VALIDATION.md`
- Live monitor (SSE) and replays from the same processor; tests 9 → 30.
- Vectorised syndrome search, 3–4× faster, decision-identical on 1,480 files. `reports/PERFORMANCE_REPORT.md`

## v2.2 (2026-09-16) — evidence-first baseline hardening

- Dataset leakage removed (sps=6 forcing, sps/β lists, 0.12 bonus, K7-only search).
- Acceptance replaced by dual-code syndrome sign test with Bonferroni α = 0.01; three outcomes DECODED / SIGNAL_NO_CODE / UNKNOWN.
- Viterbi proven equal to exhaustive ML (terminated traceback bug fixed); 1,350-file null set; scoring comparison; oracle ladder; train 60 → 63/100 with 0 false accepts.
- CI added. `reports/BASELINE_HARDENING_REPORT.md`

---

## v2.1 (code-verified, 2026-09-16)

| Item | v2.0 claim | v2.1 (measured) |
|---|---|---|
| Sealed benchmark | 28/30, fails test_020/025 (2 dB QPSK) | **30/30**, consistency 1.000 on all files. v2.0 failures don't reproduce on regenerated data |
| Codeword termination | "zero-terminated" | Truncated by the interleaver (60/120 of 812 bits), no tail. Root cause of the consistency ceiling |
| Consistency separation | success ≥0.984 / failure ≤0.866 | correct = 1.000, wrong ≤0.942; accept threshold 0.98 |
| Modulation ID | cumulant C20 | lag-1 autocorrelation of s² (CFO-invariant) |
| CFO | M-power on symbols | x⁴ on raw IQ, 16× zero-pad, top-3 candidates selected by decode |
| Regression tests | 6/6 (`tests/test_core.py` not in repo) | 4/4, new `tests/test_core.py` |
| Phase 2 commit 677241f | — | Unverified push scored 4/30; reverted |
| Held-out evidence | sealed set | Train set: 60/100 (Phase 1: 35/100) |

Unchanged: research direction, novelty audit, P1/P2 feature list. Cyclic-CAF and SAGE-Lite move from P0 to P1 pending train-set evidence.

---

## v1.0 (Gemini audit, 2026-09-11) → v2.0 (Opus research-verified audit, 2026-09-16)

---

## Summary

v2.0 is a research-verified consolidation. All claimed references were checked via web search. The project direction and evidence base are unchanged. Major improvements:

1. **Every reference verified** — exact journal, volume, pages, DOI confirmed for all cited papers
2. **Literature gap identified and verified** — blind FEC identification + decode-aided sync refinement is genuinely unexplored in open literature
3. **"Decoding as a Sensor" confirmed novel** — phrase not found in IEEE/Scholar/arXiv
4. **Competitor intelligence updated** — PROCITEC product renamed go2signals, "revolver principle" confirmed as same approach, URH archived March 2026, NVIDIA Sionna identified as new platform
5. **Open-source gaps confirmed** — no CAF symbol-rate estimator, no turbo sync implementation exists anywhere
6. **Cyclostationary theory strengthened** — no-SNR-wall property verified, supporting CAF at 2 dB
7. **Consolidation** — 84 sections → 41 sections without content loss

---

## Key Factual Corrections From Research

| Item | v1.0 State | v2.0 Correction | Source |
|---|---|---|---|
| PROCITEC product name | "go2DECODE / go2ANALYSE" | **go2signals** (consolidated brand) | PROCITEC website |
| PROCITEC approach | Not described | **"Revolver principle"** (2003) = catalogue cycling | PROCITEC product documentation |
| URH status | Listed as active GPL-3.0 | **Archived March 2026** — read-only | GitHub repository |
| scikit-dsp-comm license | "BSD-3-Clause" | **BSD-2-Clause** | GitHub repository |
| RadioML dataset quality | Listed as benchmark | **Known errata** per DeepSig themselves | DeepSig dataset page |
| NVIDIA Sionna | Not mentioned | **Apache-2.0 GPU simulation platform** (new) | GitHub: NVlabs/sionna |
| DeepSig products | Not mentioned | **OmniSIG** (spectrum awareness), **OmniPHY-5G** | deepsig.ai |
| DRDO relevant lab | Not specified | **DLRL (Defence Electronics Research Laboratory), Hyderabad** | DRDO website |
| DRDO paper | Mentioned but unverified | **Tamakuwala, DSJ 69(3):274-279, 2019, DOI: 10.14429/dsj.69.13370** | Defence Science Journal |
| Turbo-sync standard term | "SAGE-inspired" | Standard term is **"code-aided synchronization"** | Herzet et al. Proc. IEEE 2007 |
| SNR wall for cyclostationary | Not mentioned | **No SNR wall** (unlike energy detection) | Tandra & Sahai; verified via CSP Blog |
| AFF3CT FEC support | "Viterbi/RS/LDPC/Polar" | Also **Turbo codes, BCH, Turbo Product Codes** | AFF3CT GitHub |

---

## New Content Added (not in v1.0)

| Section | Content | Source |
|---|---|---|
| §4 | "Decoding as a Sensor" phrase verified as not in literature | Google Scholar, arXiv, CrossRef search |
| §13 | PROCITEC "revolver principle" parallel documented | PROCITEC product research |
| §14 | Rich prior-art table for blind interleaver (9 papers, Hanyang group) | Web search: IEEE Access, ISIT, etc. |
| §20.2 | No-SNR-wall property explained and cited | Tandra & Sahai; Gardner 1991 |
| §20.4 | Open-source CAF landscape confirmed empty | GitHub search, CSP Blog |
| §21.2 | Complete verified reference list for turbo sync (6 papers with exact citations) | IEEE Xplore, CrossRef |
| §21.3 | Literature gap formally identified and documented | Cross-referencing turbo-sync vs blind-FEC corpora |
| §21.7 | No open-source turbo sync confirmed | GitHub search across Python/MATLAB/C++ |
| §31 | Full competitor table with verified license/status | Multiple web searches |
| §34 | DLRL identified as relevant DRDO lab | DRDO website |
| §35 | Three-tier novelty classification with verified evidence | Complete novelty audit |

---

## Sections Consolidated (v1.0 → v2.0)

| v1.0 Sections | v2.0 Section | Reason |
|---|---|---|
| §§62-66 (metrics, ablation, comparison, failure taxonomy, error attribution) | §27 (Core Evaluation Metrics) | Reduced redundancy |
| §§67-69 (reproducibility, dataset separation, ground truth) | §29 (Experimental Discipline) | Consolidated |
| §§70-72 (genie, rescue contract, interpretation) | §23 (Rescue Experiment) + companion doc | Detail moved to experiment spec |
| §§73-78 (invariants, dependencies, documentation, config, logging, precision) | §§8, 12, 32, 15 | Integrated into relevant sections |
| §§79-83 (presentation, evidence chain, completion, authority, principle) | §§7, 40, 41 | Consolidated |

No content was lost — all constraints and rules are preserved in fewer, denser sections.

---

## Changes NOT Made (and why)

| Proposed | Decision | Reason |
|---|---|---|
| Add BCJR implementation details | NOT ADDED | Not MVP; would imply commitment |
| Add conformal prediction math | NOT ADDED | FUTURE; formulas imply readiness |
| Change consistency threshold | NOT CHANGED | Experimentally validated separation |
| Add CNN second-opinion | NOT ADDED | C20 achieves 100%; kill-test doctrine |
| Add Numba/Cython | NOT ADDED to MVP | No runtime bottleneck (13ms Viterbi) |
| Add NVIDIA Sionna integration | NOT ADDED | GPU-dependent; violates CPU constraint |

---

## v2.0 Post-Research Agent Updates (2026-09-16, late)

Three research agents completed after initial document finalization:

| Update | Document | Change |
|---|---|---|
| Re-encode consistency survey (33 papers) | Novelty Audit §5 | Enriched with candidate-set literature (Yu 2016, Wu 2020, Bonvard 2018, Liventsev 2026); confirmed term "re-encode consistency" is novel; marked recommended search as COMPLETED |
| Candidate-set literature | Novelty Audit §4 | Added dominant candidate-set references (Yu 2016, Wu 2020/2026, Wang 2024, Dehdashtian 2021, open-set: Jiang 2026) |
| GF(2) rank fragility quantification | Novelty Audit §10 | Added Marazin et al. (EURASIP JWCN 2011, 88 citations) quantitative threshold: BER < 10⁻⁴ to 10⁻⁵; added Wu et al. (IEEE TSP 2020) "average cosine conformity" as soft-decision alternative |

No classification changes — all three updates confirm existing assessments with richer evidence.

---

**CHANGELOG COMPLETE**
