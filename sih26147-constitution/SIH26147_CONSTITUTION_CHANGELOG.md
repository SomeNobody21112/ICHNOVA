# SIH26147 — CONSTITUTION CHANGELOG
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
