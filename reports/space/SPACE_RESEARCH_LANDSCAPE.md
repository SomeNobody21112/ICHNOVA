# SPACE_RESEARCH_LANDSCAPE
**ICHNOVA · SIH26147 — space ground-segment research landscape**
**Status: RESEARCH (2026-09-25). Design-proposal documents in this folder implement nothing.**
**Claim discipline:** every external statement is labelled **FACT** (verified against a source consulted this session), **INTERPRETATION** (source-derived), **INFERENCE** (engineering judgement from facts), or **DESIGN PROPOSAL** (what we propose to build, not yet built). No blog is cited for a standards claim. Sources consulted 2026-09-25 unless noted.

---

## 1. CCSDS — the governing standards family

### 1.1 Which documents matter and which revision is current

| Standard | Subject | Issue used in this research | Status |
|---|---|---|---|
| CCSDS 131.0-B-5 | TM Synchronization and Channel Coding | **B-5, September 2023** | FACT — current issue at ccsds.org/Pubs/131x0b5.pdf |
| CCSDS 132.0-B | TM Space Data Link Protocol | B-3 (Dec 2021 + later corrections) | FACT — current blue book family |
| CCSDS 231.0-B | TC Synchronization and Channel Coding | B-4 (2023-era) | FACT — current blue book family |
| CCSDS 401.0-B | Radio Frequency and Modulation Systems | B (living, many amendments) | FACT — current blue book family |
| CCSDS 133.0-B | Space Packet Protocol | B-2 (2023-era) | FACT — current blue book family |

> **Correction to the original brief.** The tasking mentioned "CCSDS 131.0-B-6". The current published
> issue of TM Synchronization and Channel Coding is **131.0-B-5 (September 2023)** — FACT, from the
> CCSDS publications page and the B-5 PDF itself. All ICHNOVA documents must cite **B-5**, never B-6.
> (Search results also surfaced a pink-book process report 131x0p51 dated 2024/2025; a pink book is a
> proposal track, not a standard — INTERPRETATION, so it does not change the citation.)

### 1.2 What 131.0-B-5 actually specifies (the layers SPACE-BENCH and the CCSDS profile must respect)

FACT — all from the B-5 blue book summary and MathWorks' official CCSDS end-to-end example, both consulted this session:
- **ASM (Attached Sync Marker)** `0x1ACFFC1D` for TM frame sync; a **64-bit marker** `0x034776C7272895B0` for the LDPC-coded stream. ICHNOVA already carries both in `src/framing.py` (`MARKERS` loaded from `references/ccsds_constants.json`) — FACT from code.
- **Channel-coding families**: RS; convolutional (r=1/2, K=7, G2-first polynomials); concatenated RS+conv; **TC LDPC** (arithmetic-based, e.g. (128,64), (512,256), (1024,512), (4096,2048)); block-LDPC for TM (8161, 8144, k=1024-family); turbo where legacy. ICHNOVA's `src/rs.py`, `src/ldpc.py`, `src/blockcode.py`, `src/blind_id.py` catalogue and `src/framing.py` already implement/validate the RS, conv, concatenated and TC-LDPC subsets — FACT from code + bench-v2 sealed results.
- **Pseudo-randomizers**: TM 255 / TM 131071 sequences and the TC BTG randomizer — implemented and standards-verified in `src/framing.py` (`RANDOMIZERS`, each reproduces the first 40 bits printed in the standards; `tests/test_catalogue.py`) — FACT from code.
- **Transfer frames / sync**: defined in 132.0 (TM space data link), not in 131.0 — INTERPRETATION of the standard-family division.

## 2. ISRO / ISTRAC — the positioning backdrop

FACT — from isro.gov.in (ISTRAC page, Ground Segment Activities page) consulted this session:
- ISTRAC operates a TTC ground-station network: Bengaluru, Lucknow, Sriharikota, Thiruvananthapuram, Port Blair, plus Brunei, Biak (Indonesia), Mauritius, Príncipe.
- Bands used across the network include S, C and X band; small-satellite TTC work happens at VHF/UHF/S.
- ISRO publishes its ground-segment architecture (TTC stations, ranging, mission control) on official pages.

INTERPRETATION (ours, clearly separated): a ground-segment *analysis layer* sits between the RF front end and mission operations. ICHNOVA would occupy exactly that slot. Nothing in this research, and nothing in the repository, constitutes ISRO involvement, endorsement, or knowledge of ISRO's internal systems. **No ISRO branding anywhere** (see SPACE_CLAIM_FIREWALL.md).

## 3. Doppler physics of LEO passes (the impairment that defines space links)

FACT — from the sources consulted this session (orbitalradar.com glossary, rfessentials.com RF knowledge base, USU SmallSat conference paper Zantou et al., MathWorks `dopplershiftcircularorbit` reference, satnow.com calculator):
- LEO relative velocities ≈ 7.5 km/s ⇒ maximum Doppler shift scales with carrier frequency: about **±3.5 kHz at 2 m band (VHF)**, **±10 kHz at 70 cm (UHF)**, **±5 kHz at S-band (~2 GHz)**, **±30 kHz at 12 GHz (Ku-band)**.
- Doppler **rate** for LEO passes reaches **tens of Hz/s (≈ 32 Hz/s cited)**, peaking near acquisition-of-signal; the shift is near-linear over short windows, S-curved over a full pass.
- Ground terminals commonly correct Doppler with TLE-based prediction at 10 s steps; residual error remains.

INFERENCE (engineering, clearly labelled): residual Doppler at the demodulator is a **time-varying CFO** with rate up to ~tens of Hz/s at the carrier — in ICHNOVA's normalised units (cyc/sample at fs ≈ 1 MHz, symbol rates 50–500 ksym/s) that is a slow phase rotation across a capture. **This maps directly onto ICHNOVA's existing, measured failure class:** `pipeline.py` already documents that a linear CFO drift / phase noise leaves no single phase fitting the whole capture, and therefore adds a **tracked front-end variant** (`_track_phase`, coherence-adaptive block length chosen by the data, `TRACK_MIN_SYMBOLS = 512`) when a capture is long enough to drift — FACT from code. The bench-v2 generator already has the `cfo_drift` (linear) channel class — FACT from `eval/bench2_gen.py`.

## 4. Existing systems — what each actually does (no invented capabilities)

| System | Inputs required | Blind inference? | Validates decode? | Can refuse? | Evidence exposure? | CCSDS? | Real satellite use? | Overlap with ICHNOVA |
|---|---|---|---|---|---|---|---|---|
| **gr-satellites** (daniestevez/gr-satellites, GitHub + destevez.net docs) | Per-satellite **SatYAML**: modulation, baud, framing, deframers must be known/chosen | **No** — parameters known per satellite | Frame/packet structure implied by deframers | Not as a statistical outcome | Decoded KISS frames; not statistical evidence | Partial (amateur-relevant subsets) | FACT — widely used by amateurs | Low: known-parameter decoding vs ICHNOVA's hypothesis-tested blindness |
| **SatNOGS** (wiki.satnogs.org, Libre Space community docs) | Network DB **known-mode** demodulator presets per satellite | **No** — mode selected from DB | Community-verified decodes; artifacts | No explicit refusal semantics | Artifacts + demod data uploaded | Partial, via gr-satnogs flowgraphs | FACT — global station network | Low-medium: capture infrastructure exists; the *analysis* gap is ours |
| **Universal Radio Hacker** (jopohl/urh GitHub; Pohl & Lantz, USENIX WOOT '18) | IQ file; **autofocus** estimates modulation params; human-guided protocol RE | **Semi** — auto parameter estimation, manual protocol inference | Human-in-the-loop decoders | No statistical refusal | Visual tools; no formal evidence package | Not CCSDS-oriented | FACT — general wireless RE, not satellite-specific | Medium: shares the "understand unknown signal" goal; different epistemics (visual/manual vs statistical/refusing) |
| **GNU Radio** | — | Framework, not a decision system | — | — | — | Via OOT modules | FACT — ubiquitous | None directly: ICHNOVA is NumPy/SciPy and could accept GNU-Radio-produced IQ |
| **MathWorks CCSDS toolbox examples** (mathworks.com satcom examples) | Standards + configured parameters | No — known-parameter simulation/reference chain | Conformance to standard | — | — | FACT — full CCSDS chain | Reference implementations | Complementary: benchmark-vector generator inspiration |

INFERENCE (the honest gap): **no surveyed system ships statistical, family-wise-error-controlled *blind* inference with explicit refusal semantics and independently verifiable evidence packages for space links.** Known-parameter decoders dominate because knowing the satellite is easy; the partially-unknown case (uncooperative, mislabelled, degraded, or new emitter) is exactly where ICHNOVA's architecture already operates — FACT about ICHNOVA, INFERENCE about the gap. This does not establish superiority over commercial/defence systems we cannot inspect — explicitly NOT CLAIMED (see SPACE_TECH_RESEARCH_GAP.md §5).

## 5. What space links change versus terrestrial/bench captures

| Dimension | ICHNOVA bench-v2 assumption | Space-link reality (FACT, sources above) | Consequence |
|---|---|---|---|
| CFO | static, ±1.25% of fs | time-varying (Doppler), rate to ~32 Hz/s, plus oscillator offsets | Existing `cfo_drift` channel + tracked front ends cover a *model* of it; measured-trajectory reporting is missing (DESIGN PROPOSAL: DOPPLER_EXPERIMENT_DESIGN.md) |
| Fading | none sealed (rician exists in generator) | passes through fades, multipath | `rician` class exists; not in any sealed family (FACT from criteria file) |
| SNR | bench floor ~6 dB Es/N0 for coded families | low-SNR, elevation-dependent | SPACE-BENCH family B pushes below the sealed floor with honest refusal expected |
| Frame sync | catalogue ASMs + blind constant fields | CCSDS ASMs, mission-specific frames | Already covered: both ASMs + **blind** sync detection — FACT from framing.py |
| Payload semantics | synthetic payloads | CCSDS transfer frames, space packets | Layer-by-layer honesty profile required (CCSDS_TELEMETRY_PROFILE.md) |
| Pass geometry | N/A | elevation-dependent C/N over ~8–12 min | SIMULATED Mission Replay (SATELLITE_PASS_REPLAY_DESIGN.md) |

## 6. Source register

Every source below was consulted 2026-09-25 via live search/reading during this research session.

| # | TITLE | ORGANIZATION | DATE | URL | RELEVANT CLAIM | EFFECT ON ICHNOVA |
|---|---|---|---|---|---|---|
| S1 | TM Synchronization and Channel Coding, 131.0-B-5 | CCSDS | 2023-09 | https://ccsds.org/Pubs/131x0b5.pdf | Current issue; ASM, coding families, randomizers | Citation basis for the CCSDS profile; corrects "B-6" |
| S2 | CCSDS Blue Books index | CCSDS | current | https://ccsds.org/publications/bluebooks/ | 131.0-B-5 current; family structure | Version verification |
| S3 | End-to-end CCSDS TM sync & channel coding simulation | MathWorks | current | https://www.mathworks.com/help/satcom/ug/end-to-end-ccsds-telemetry-synchronization-and-channel-coding-simulation-with-rf-impairments-and-corrections.html | Coding/ASM pipeline shape; RF impairments | SPACE-BENCH family design reference |
| S4 | ISRO Telemetry, Tracking and Command Network | ISRO | current | https://www.isro.gov.in/ISTRAC.html | ISTRAC station list, TTC role | Positioning backdrop, §2 |
| S5 | Ground Segment Activities | ISRO | current | https://www.isro.gov.in/GroundSegmentActivities.html | TTC/ranging ground-segment structure | Positioning backdrop, §2 |
| S6 | gr-satellites repository | D. Estévez | current | https://github.com/daniestevez/gr-satellites | SatYAML known-parameter decoders | Competitor matrix, §4 |
| S7 | gr-satellites command-line docs | D. Estévez | current | https://gr-satellites.readthedocs.io/en/latest/command_line.html | Satellite selected by name/NORAD/YAML | Competitor matrix, §4 |
| S8 | Decode Telemetry and Packets | SatNOGS Wiki | 2026-05 | https://wiki.satnogs.org/Decode_Telemetry_and_Packets | Built-in demods for known formats | Competitor matrix, §4 |
| S9 | urh repository | J. Pohl et al. | current | https://github.com/jopohl/urh | Autofocus modulation parameter detection | Competitor matrix, §4 |
| S10 | URH: A Suite for Analyzing and Attacking Stateful Wireless Protocols | Pohl & Lantz, USENIX WOOT | 2018 | https://www.usenix.org/system/files/conference/woot18/woot18-paper-pohl.pdf | URH design intent (protocol RE for humans) | Competitor matrix, §4 |
| S11 | Doppler Shift in Satellite Radio | orbitalradar.com | current | https://orbitalradar.com/glossary/doppler-shift | ±3.5 kHz @ 2 m, ±10 kHz @ 70 cm | Doppler magnitudes, §3 |
| S12 | LEO Doppler Compensation | rfessentials.com | current | https://rfessentials.com/rf-knowledge-base/how-does-doppler-shift-affect-a-leo-satellite-communication-link-and-how-do-i-co/ | ±5 kHz @ 2 GHz, ±30 kHz @ 12 GHz | Doppler magnitudes, §3 |
| S13 | Orbit Calculation and Doppler Correction Algorithm (SmallSat) | Zantou et al., USU SmallSat | current | https://digitalcommons.usu.edu/cgi/viewcontent.cgi?article=1659&context=smallsat | ≤10 kHz UHF, ~32 Hz/s rate, 10 s correction steps | Doppler rate, §3 |
| S14 | dopplerShiftCircularOrbit | MathWorks | current | https://www.mathworks.com/help/satcom/ref/dopplershiftcircularorbit.html | Geometry-based Doppler model API | Pass-replay model design reference |

**Interpretation labelling note:** statements about *other* systems' internals that come from their own docs are FACT; statements that those systems therefore lack ICHNOVA-like features are INTERPRETATION (absence of evidence from docs, not proof of absence) — and the gap claim in §4 is worded accordingly. Nothing in this document claims ICHNOVA is superior to commercial or defence ground systems, which are outside our visibility.

**END OF SPACE RESEARCH LANDSCAPE**
