# Phase 2 — fingerprint similarity search (EXPERIMENTAL)

Data: data/nullset (synthetic, labelled by the generator). 675 reference captures, 675 held-out queries.

Protocol: split by seed index (even = reference, odd = held-out query); standardisation fitted on the reference only; a query is correct when its nearest reference capture has the same generator class.

| Measure | Value |
|---|---|
| Top-1 same-class retrieval | **54.2%** (366/675; 95% CI 50.5%–57.9%) |
| Precision at 5 | 47.7% |
| Baseline: random reference | 20.4% |
| Baseline: verdict only | 31.5% |
| Signal classes only (noise queries excluded) | 39.8% (169/425); random 10.7% |
| Refused captures that carried a signal (not DECODED, not noise) | 28.2% (100/354) |

## By class

| Class | Queries | Top-1 | 95% CI |
|---|---|---|---|
| 8psk_k7 | 50 | 24.0% | 14.3%–37.4% |
| k3 | 75 | 29.3% | 20.2%–40.4% |
| k5 | 75 | 40.0% | 29.7%–51.3% |
| k7 | 75 | 50.7% | 39.6%–61.7% |
| noise | 250 | 78.8% | 73.3%–83.4% |
| uncoded_bpsk | 75 | 54.7% | 43.4%–65.4% |
| uncoded_qpsk | 75 | 34.7% | 24.9%–45.9% |

## By coded length

| Coded bits | Queries | Top-1 |
|---|---|---|
| 30 | 135 | 34.8% |
| 60 | 135 | 43.0% |
| 120 | 135 | 57.8% |
| 240 | 135 | 65.2% |
| 384 | 135 | 70.4% |

Fingerprint features (16): `presence`, `line_x2_db`, `line_x4_db`, `structure_q4`, `symbol_rate`, `raw_rate`, `bpsk_ratio`, `evidence_k3`, `evidence_k5`, `evidence_k7`, `symbol_snr`, `interleaver_bits`, `margin`, `v_decoded`, `v_signal_no_code`, `v_unknown`.

Scope: Synthetic benchmark captures only. Not validated on real transmissions; never part of a decision.

Engine commit: `9ea2032`. Reproduce: `python eval/nullset.py generate` (deterministic seeds), then `python eval/similarity.py`.
