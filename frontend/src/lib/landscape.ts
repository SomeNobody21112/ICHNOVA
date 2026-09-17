/** Positioning against existing tools and published methods. Claims about other products are limited to what
 * their public product pages state; see reports/RESEARCH_LANDSCAPE.md for the full notes. */

export interface Approach {
  group: string
  name: string
  what: string
  strength: string
  gap: string
  sources: { title: string; url: string }[]
}

export const APPROACHES: Approach[] = [
  {
    group: 'Commercial signal analysis',
    name: 'Rohde & Schwarz CA120 / CA100',
    what: 'Multichannel detection, classification, demodulation and decoding of communications signals on R&S monitoring receivers.',
    strength: 'Automatic classifier for modulation and transmission system; production monitoring integration.',
    gap: 'Closed, receiver-bound and licensed; public material describes known-system recognition, not a published statistical acceptance criterion.',
    sources: [{ title: 'R&S CA120 product page', url: 'https://www.rohde-schwarz.com/us/products/aerospace-defense-security/online-signal-analysis/rs-ca120-multichannel-signal-analysis-software_63493-52993.html' }],
  },
  {
    group: 'Commercial signal analysis',
    name: 'PROCITEC go2signals (go2MONITOR, go2DECODE)',
    what: 'Automated HF-SHF monitoring: detection, modulation classification, modem recognition and decoding; analysis suite for developing new decoders.',
    strength: 'Hundreds of signals simultaneously; large library of known modems.',
    gap: 'Unknown protocols go to manual analysis and decoder development; evidence behind an automatic label is not exposed as a test statistic.',
    sources: [{ title: 'PROCITEC go2signals', url: 'https://procitec.com/en/go2signals' }, { title: 'go2DECODE brochure', url: 'https://procitec.com/file_access/3916/2195/5266/PROCITEC_Broschure_go2DECODE.pdf' }],
  },
  {
    group: 'Commercial signal analysis',
    name: 'WAVECOM W-CODE',
    what: 'Classifier and decoder for 300+ HF/VHF/UHF data modes from IQ or audio.',
    strength: 'Very broad catalogue of standardised modes (e.g. STANAG, MIL-STD).',
    gap: 'Catalogue decoding of known modes; not designed to establish unknown FEC or interleaver structure blindly.',
    sources: [{ title: 'WAVECOM W-CODE', url: 'https://www.wavecomusa.com/w-code.html' }],
  },
  {
    group: 'Deep-learning RF classification',
    name: 'DeepSig OmniSIG; RadioML-style CNNs',
    what: 'Neural detection and classification of signals in spectrum; RadioML datasets (24 modulations, 1024-sample examples).',
    strength: 'Fast wideband detection and modulation classification; trainable on new emitters.',
    gap: 'Outputs a class, not the code, interleaver or payload; confidence is a network score, not a calibrated error rate; performance depends on training-data match.',
    sources: [{ title: 'DeepSig OmniSIG', url: 'https://www.deepsig.ai/omnisig/' }, { title: "O'Shea, Roy, Clancy 2018 (IEEE JSTSP)", url: 'https://arxiv.org/abs/1712.04578' }],
  },
  {
    group: 'Open source',
    name: 'Universal Radio Hacker (URH)',
    what: 'Capture, demodulation with automatic parameter detection, and protocol reverse engineering for short-range digital links.',
    strength: 'Interactive, transparent, free.',
    gap: 'Analyst-driven; no blind FEC/interleaver identification or statistical acceptance.',
    sources: [{ title: 'URH (WOOT 2017 paper)', url: 'https://dl.acm.org/doi/pdf/10.1145/3139937.3139951' }, { title: 'jopohl/urh', url: 'https://github.com/jopohl/urh' }],
  },
  {
    group: 'Published blind-identification methods',
    name: 'Algebraic / rank methods for code reconstruction',
    what: 'Recover convolutional or linear codes from noisy bit streams (Côte & Sendrier, ISIT 2009; Moosavi & Larsson, IEEE TCOM 2014, syndrome posterior probability).',
    strength: 'Principled use of code structure; the SPP idea is close to this engine’s parity statistic.',
    gap: 'Algorithms, not an operator system; SPP needs calibrated LLRs, whereas the sign test used here is exact under its null without calibration.',
    sources: [{ title: 'Côte & Sendrier 2009 (dblp)', url: 'https://dblp.org/rec/conf/isit/CoteS09.html' }, { title: 'Moosavi & Larsson 2014', url: 'https://www.diva-portal.org/smash/get/diva2:678868/FULLTEXT01.pdf' }],
  },
  {
    group: 'Published blind-identification methods',
    name: 'Blind interleaver parameter estimation',
    what: 'Estimate interleaver size, start and function from coded streams (Sicot, Houcke & Barbier, Signal Processing 89(4), 2009) and later statistical tests.',
    strength: 'Theoretical detection thresholds.',
    gap: 'Studied in isolation from demodulation, symbol-rate and carrier uncertainty; this engine searches them jointly and controls the family-wise error across all of them.',
    sources: [{ title: 'Sicot, Houcke, Barbier 2009', url: 'https://www.sciencedirect.com/science/article/abs/pii/S0165168408003046' }],
  },
  {
    group: 'Published blind-identification methods',
    name: 'Deep-learning channel-code recognition',
    what: 'CNN/LSTM/Transformer classifiers for convolutional, LDPC, turbo and polar code types and parameters.',
    strength: 'Covers many code families; robust features at moderate SNR.',
    gap: 'Reported as accuracy on synthetic test sets; no per-decision guarantee and no refusal mechanism.',
    sources: [{ title: 'Blind identification of convolutional codes based on deep learning (DSP 2021)', url: 'https://www.sciencedirect.com/science/article/abs/pii/S1051200421001251' }, { title: 'ConvLSTM code recognition (2025)', url: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC11858941/' }],
  },
]

export const DIFFERENTIATORS = [
  ['Refusal is a result', 'Every accept is a Bonferroni-corrected exact test plus structural checks; on 900 non-catalogue benchmark files it asserted a code 0 times, and on a real weak WWVB capture it detected the station but refused to state a time.'],
  ['Checked against the world, not a test set', 'Real transmissions from NIST, PTB, NPL, NICT and DWD decode blind, and the decoded minute is compared with the receiving station’s GPS clock (0.6 to 23 ms). India: AIR carriers matched to Prasar Bharati’s official list.'],
  ['Evidence travels with the answer', 'Each record carries hypotheses tested, p-values, rejected alternatives and timings, so a supervisor can audit why, not just what.'],
  ['Operational from edge to nation', 'Field capture, review queue, incidents, regional and national aggregation share one evidence model.'],
]
