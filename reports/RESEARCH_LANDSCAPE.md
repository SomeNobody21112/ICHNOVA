# Research and Product Landscape

**Date:** 2026-09-17. Claims about other products are limited to their public descriptions (linked). This note explains where this platform sits and why its design choices differ.

## Commercial signal analysis

| Product | Public description | Relevance |
|---|---|---|
| Rohde & Schwarz CA120 / CA100 | Multichannel detection, classification, demodulation and decoding of communications signals; automatic classifier for modulation type and transmission system ([CA120](https://www.rohde-schwarz.com/us/products/aerospace-defense-security/online-signal-analysis/rs-ca120-multichannel-signal-analysis-software_63493-52993.html)) | Reference class for operational monitoring; closed and receiver-bound |
| PROCITEC go2signals (go2MONITOR, go2DECODE) | Automated HF–SHF monitoring: detection, modulation classification, modem recognition, decoding of hundreds of signals; go2DECODE supports manual analysis and development of new decoders ([go2signals](https://procitec.com/en/go2signals), [go2DECODE brochure](https://procitec.com/file_access/3916/2195/5266/PROCITEC_Broschure_go2DECODE.pdf)) | Large known-modem libraries; unknown protocols go to manual analysis |
| WAVECOM W-CODE | Classifier/decoder for 300+ HF/VHF/UHF data modes from IQ or audio ([W-CODE](https://www.wavecomusa.com/w-code.html)) | Catalogue decoding of standardised modes |
| DeepSig OmniSIG | Deep-learning signal detection and classification, trainable on new signals ([OmniSIG](https://www.deepsig.ai/omnisig/)) | Fast classification; output is a class, not code/interleaver/payload |

India's own monitoring context: the Wireless Monitoring Organisation (DoT/WPC) operates international and wireless monitoring stations across the country ([WMO](https://dotws.cdot.in/wireless-monitoring-organisation)); SIH26147 is sponsored by NTRO.

## Open source

- **Universal Radio Hacker** — capture, demodulation with automatic parameter detection and protocol reverse engineering, analyst-driven ([WOOT 2017 paper](https://dl.acm.org/doi/pdf/10.1145/3139937.3139951), [repository](https://github.com/jopohl/urh)).

## Published methods

| Topic | Work | How this platform relates |
|---|---|---|
| Convolutional code reconstruction from noisy bits | Côte & Sendrier, "Reconstruction of convolutional codes from noisy observation", ISIT 2009 ([dblp](https://dblp.org/rec/conf/isit/CoteS09.html)) | Uses code structure; this engine tests a catalogue with the dual-code parity relation instead of reconstructing arbitrary codes |
| Syndrome-based recognition | Moosavi & Larsson, "Fast blind recognition of channel codes", IEEE Trans. Commun. 62(5), 2014 — syndrome posterior probability from soft values ([paper](https://www.diva-portal.org/smash/get/diva2:678868/FULLTEXT01.pdf)) | Closest in spirit; SPP needs calibrated LLRs, whereas the sign test here is exact under its null without LLR calibration, and is Bonferroni-corrected over the joint front-end × code × interleaver search |
| Interleaver parameters | Sicot, Houcke & Barbier, "Blind detection of interleaver parameters", Signal Processing 89(4), 2009 ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0165168408003046)) | Studied on bit streams; here interleaver search is joint with carrier, symbol-rate and modulation uncertainty, with structural checks against wrong-structure accepts |
| Deep-learning code recognition | e.g. "Blind identification of convolutional codes based on deep learning", DSP 2021 ([link](https://www.sciencedirect.com/science/article/abs/pii/S1051200421001251)); ConvLSTM recognition 2025 ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC11858941/)) | Reported as accuracy on synthetic sets; no per-decision error control or refusal |
| Modulation recognition | O'Shea, Roy & Clancy, "Over-the-air deep learning based radio signal classification", IEEE JSTSP 2018 ([arXiv](https://arxiv.org/abs/1712.04578)) | Classification only; the platform keeps ML for prioritisation/similarity (roadmap) and leaves acceptance to exact tests |

## What is different here

1. **Refusal is a result with a number attached.** Every accept is an exact test with family-wise error control plus structural checks; 0/900 false accepts on non-catalogue benchmark files; on a real weak WWVB capture the station is detected but the time refused.
2. **Checked against the world.** Real government transmissions decoded blind and compared with receiver GPS time, the transmission's own content and India's official transmitter list (`reports/REAL_SIGNAL_VALIDATION.md`).
3. **Evidence travels with the answer** into review, incidents, reports and national aggregation.
4. **Measured before claimed.** Oracle ladder, null sets, split-sample calibration (constants fitted on one half of the null set, reported on the other) and a performance change that is proven decision-identical on 1,480 files.
