# Should 8PSK and 16-QAM be searched by default?

**Answer: no.** Enabling them gains nothing on the modulation they target, and on one capture it
turned a correct decode into a confident wrong one.

Run on 2026-09-19 at commit `63d950f`, engine `v0.3.0`, over the whole null set (1,350 captures),
with `eval/nullset.py run --higher`. The baseline arm is the existing `results/nullset_rows.jsonl`;
this arm is `results/nullset_rows_higher.jsonl`, kept in a separate file so the two can never be
confused. The sealed split was not touched and nothing was regenerated.

## What was measured

`SEARCH_HIGHER_MODULATIONS` gates the 8PSK and 16-QAM search. It has always been off by default, and
the reason given was that enabling it "could raise false accepts" — an argument, not a measurement.
This is the measurement.

| Class | n | Gate OFF (decoded / signal-no-code / unknown) | Gate ON |
| --- | --- | --- | --- |
| noise | 500 | 0 / 21 / 479 | 0 / 17 / 483 |
| uncoded BPSK | 150 | 0 / 134 / 16 | 0 / 133 / 17 |
| uncoded QPSK | 150 | 0 / 28 / 122 | 0 / 28 / 122 |
| **8PSK + K=7** | **100** | **0 / 5 / 95** | **0 / 5 / 95** |
| K=3 | 150 | 31 / 59 / 60 | 38 / 54 / 58 |
| K=5 | 150 | 37 / 50 / 63 | 39 / 49 / 62 |
| K=7 | 150 | 61 / 38 / 51 | 57 / 39 / 54 |

## The three findings

**1. No false accepts either way.** Across the 800 captures with no catalogue code (noise, uncoded
BPSK, uncoded QPSK): **0 decoded with the gate off, 0 with it on.** The original worry was not borne
out. The acceptance test holds.

**2. No recall on the class it exists for.** Of the 100 8PSK captures, **0 more decoded**. The gate
genuinely opened on 88 of them — the hypothesis count rose by a median of **21.8×** — so this is not
a closed gate being measured. The search ran and found nothing, because the multiple-testing
correction raises the bar by roughly the factor the search grows.

That mechanism is visible directly. Seven captures that decoded with the gate off stopped decoding
with it on, and for every one the evidence was *unchanged* while the bar moved past it:

| Capture | Hypotheses | Bar | Best evidence |
| --- | --- | --- | --- |
| `k7_060_003` | 6,771 → 225,420 | −5.83 → −7.65 | −7.22 (unchanged) |
| `k7_060_009` | 7,875 → 138,852 | −5.90 → −7.44 | −7.22 (unchanged) |
| `k5_060_022` | 13,491 → 384,387 | −6.13 → −7.89 | −7.83 (unchanged) |

This is the correction working as designed: a wider search is paid for with a higher bar. Twelve
other captures gained a decode as the ranking shifted, so the net is +5 decodes across the BPSK/QPSK
classes the feature was never meant to touch — movement in both directions on signals unrelated to
8PSK.

**3. It produced a confident wrong answer.** One capture, `k5_060_003`:

| | Gate OFF | Gate ON |
| --- | --- | --- |
| Verdict | DECODED | DECODED |
| Modulation | BPSK (true) | **8PSK** |
| Interleaver | [3, 20] (true) | **[9, 20]** |
| Evidence | 10^−10.23 | **10^−10.87** (stronger) |
| Payload BER | **0.0** | **0.4** |

The true signal is BPSK at 12 dB Es/N0, decoded bit-perfectly with the gate off. With the gate on an
8PSK hypothesis with three times the interleaver rows scores *better*, clears the raised bar, and
returns a payload that is 40 % wrong.

It is a structural alias, not a fluke: 8PSK carries three bits per symbol where BPSK carries one, so
the same symbol burst yields three times the bits, and a 9 × 20 interleaver explains them as exactly
as 3 × 20 explains the truth. The parity checks really are satisfied, so no statistical test can
catch it — the p-value is honest and the answer is wrong. The gate-off arm produced no such capture.

## Decision

`SEARCH_HIGHER_MODULATIONS` stays `False`. The coverage list records 8PSK/16-QAM as **EXPERIMENTAL**:
implemented, tested, available per call, and off by default — now for a measured reason rather than a
cautious one.

The cost of turning it on, for completeness: total runtime over the 1,350 captures went from 289 s to
2,088 s, **7.2×**.

## What would change this

A modulation classifier confident enough to select the constellation *before* the code search, so
8PSK hypotheses are tested only when the symbols really are 8PSK. That removes both problems at
once: the hypothesis count stops multiplying, and the BPSK-as-8PSK alias never enters the pool.
Until then, searching a modulation that is not present can only cost bar and invite aliases.

## Reproducing

```
python eval/nullset.py run --higher      # writes results/nullset_rows_higher.jsonl
python eval/nullset.py report --higher
```

`NULLSET_WORKERS` caps the pool size on a machine short of memory.
