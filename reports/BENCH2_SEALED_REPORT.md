# bench-v2 — sealed split (430 files)

Dataset: `data\bench2/sealed`, seeds 400000–400429, generator `eval/bench2_gen.py`. Engine commit `d790e99`. Criteria: `eval/bench2_criteria.json` (committed before any sealed run).

**SEALED split — final evaluation only.** Every run is recorded in `eval/bench2_access_log.jsonl`.

## Catalogue families (a correct structure exists)

| class | N | TP | partial | false accepts (95% upper) | FN | recall |
|---|---|---|---|---|---|---|
| blind_framed | 10 | 5 | 0 | 0 (27.8%) | 5 | 0.50 |
| burst_16QAM_k3_block | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_16QAM_k3_conv | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_16QAM_k3_diag | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_16QAM_k3_qpp | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_16QAM_k5_block | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_16QAM_k5_conv | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_16QAM_k5_diag | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_16QAM_k5_qpp | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_16QAM_k7_block | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_16QAM_k7_conv | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_16QAM_k7_diag | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_16QAM_k7_qpp | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_8PSK_k3_block | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_8PSK_k3_conv | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_8PSK_k3_diag | 5 | 0 | 0 | 1 (62.4%) | 4 | 0.00 |
| burst_8PSK_k3_qpp | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_8PSK_k5_block | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_8PSK_k5_conv | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_8PSK_k5_diag | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_8PSK_k5_qpp | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_8PSK_k7_block | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_8PSK_k7_conv | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_8PSK_k7_diag | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_8PSK_k7_qpp | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_BPSK_k3_block | 5 | 2 | 0 | 0 (43.4%) | 3 | 0.40 |
| burst_BPSK_k3_conv | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_BPSK_k3_diag | 5 | 3 | 0 | 0 (43.4%) | 2 | 0.60 |
| burst_BPSK_k3_qpp | 5 | 3 | 0 | 0 (43.4%) | 2 | 0.60 |
| burst_BPSK_k5_block | 5 | 2 | 0 | 0 (43.4%) | 3 | 0.40 |
| burst_BPSK_k5_conv | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_BPSK_k5_diag | 5 | 2 | 0 | 0 (43.4%) | 3 | 0.40 |
| burst_BPSK_k5_qpp | 5 | 3 | 0 | 0 (43.4%) | 2 | 0.60 |
| burst_BPSK_k7_block | 5 | 4 | 0 | 0 (43.4%) | 1 | 0.80 |
| burst_BPSK_k7_conv | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_BPSK_k7_diag | 5 | 4 | 0 | 0 (43.4%) | 1 | 0.80 |
| burst_BPSK_k7_qpp | 5 | 5 | 0 | 0 (43.4%) | 0 | 1.00 |
| burst_QPSK_k3_block | 5 | 1 | 0 | 0 (43.4%) | 4 | 0.20 |
| burst_QPSK_k3_conv | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_QPSK_k3_diag | 5 | 1 | 0 | 0 (43.4%) | 4 | 0.20 |
| burst_QPSK_k3_qpp | 5 | 2 | 0 | 0 (43.4%) | 3 | 0.40 |
| burst_QPSK_k5_block | 5 | 1 | 0 | 0 (43.4%) | 4 | 0.20 |
| burst_QPSK_k5_conv | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_QPSK_k5_diag | 5 | 2 | 0 | 0 (43.4%) | 3 | 0.40 |
| burst_QPSK_k5_qpp | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_QPSK_k7_block | 5 | 2 | 0 | 0 (43.4%) | 3 | 0.40 |
| burst_QPSK_k7_conv | 5 | 0 | 0 | 0 (43.4%) | 5 | 0.00 |
| burst_QPSK_k7_diag | 5 | 2 | 0 | 0 (43.4%) | 3 | 0.40 |
| burst_QPSK_k7_qpp | 5 | 3 | 0 | 0 (43.4%) | 2 | 0.60 |
| ccsds_concat | 20 | 16 | 2 | 1 (23.6%) | 1 | 0.80 |
| rs_framed | 10 | 6 | 0 | 0 (27.8%) | 4 | 0.60 |
| stream_k7 | 20 | 19 | 0 | 1 (23.6%) | 0 | 0.95 |
| tc_ldpc_cltu | 10 | 10 | 0 | 0 (27.8%) | 0 | 1.00 |

## Non-catalogue nulls (any DECODED is a false accept)

| class | N | TP | partial | false accepts (95% upper) | FN | recall |
|---|---|---|---|---|---|---|
| asm_random | 10 | 0 | 0 | 0 (27.8%) | 0 | — |
| conv_k9 | 10 | 0 | 0 | 0 (27.8%) | 0 | — |
| idle_carrier | 10 | 0 | 0 | 0 (27.8%) | 0 | — |
| linear_128_64 | 10 | 0 | 0 | 0 (27.8%) | 0 | — |
| mod_64qam | 10 | 0 | 0 | 0 (27.8%) | 0 | — |
| noise | 10 | 0 | 0 | 0 (27.8%) | 0 | — |
| perm_random | 10 | 0 | 0 | 0 (27.8%) | 0 | — |
| rs_dvb_204_188 | 10 | 0 | 0 | 0 (27.8%) | 0 | — |
| uncoded_16QAM | 10 | 0 | 0 | 0 (27.8%) | 0 | — |
| uncoded_8PSK | 10 | 0 | 0 | 0 (27.8%) | 0 | — |
| uncoded_BPSK | 10 | 0 | 0 | 0 (27.8%) | 0 | — |
| uncoded_QPSK | 10 | 0 | 0 | 0 (27.8%) | 0 | — |

## By Es/N0 (catalogue classes, recall)

| family | 3 dB | 6 dB | 9 dB | 12 dB | 15 dB |
|---|---|---|---|---|---|
| F1 | 1/48 | 9/48 | 8/48 | 13/48 | 11/48 |
| F2 | 3/4 | 4/4 | 4/4 | 4/4 | 4/4 |
| F2+F3+F4 | 2/4 | 4/4 | 4/4 | 2/4 | 4/4 |
| F3 | 1/2 | 2/2 | 1/2 | 0/2 | 1/2 |
| F3+F4 | 0/2 | 1/2 | 1/2 | 2/2 | 2/2 |
| F4 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |

## By channel (all classes)

| channel | N | TP | false accepts | recall (catalogue only) |
|---|---|---|---|---|
| none | 10 | 0 | 0 | — |
| awgn | 88 | 24 | 0 | 24/65 |
| phase_noise | 52 | 12 | 0 | 12/41 |
| cfo_drift | 70 | 13 | 3 | 13/52 |
| rician | 46 | 9 | 0 | 9/27 |
| amplitude | 76 | 20 | 0 | 20/60 |
| timing | 88 | 20 | 0 | 20/65 |

**Totals.** Null classes: 0/120 false accepts (95% Wilson upper bound 3.10%). Catalogue classes: 98/310 fully correct, 2 partially correct (true but fewer layers), 3 wrong structure or payload (95% upper bound 2.81%), 207 refusals.
Mean runtime 2.38 s, max 64.3 s.

## Pre-registered criteria

| criterion | required | measured | verdict |
|---|---|---|---|
| no_false_accept_on_non_catalogue_signals | ≤ 1% of null-class files DECODED, and the 95% Wilson upper bound ≤ 5% | 0/120 = 0.00% (≤3.10%) | PASS |
| wrong_structure_or_payload_is_rare | ≤ 2% of catalogue-class files DECODED with a wrong structure or a wrong payload | 3/310 = 0.97% | PASS |
| continuous_stream_code_recall | ≥ 80% of continuous K7 streams at Es/N0 ≥ 6 dB fully decoded | 16/16 = 100% | PASS |
| ccsds_concatenated_chain_recall | ≥ 60% of CCSDS concatenated captures at Es/N0 ≥ 9 dB decoded fully to the RS payload | 10/12 = 83% | PASS |
| tc_ldpc_cltu_recall | ≥ 80% of TC LDPC CLTUs at Es/N0 ≥ 6 dB decoded | 8/8 = 100% | PASS |
| rs_framed_recall | ≥ 50% of framed RS captures at Es/N0 ≥ 9 dB decoded to the RS payload | 5/6 = 83% | PASS |
| blind_framed_signal_no_code | ≥ 50% of non-catalogue framed streams reported as SIGNAL_NO_CODE with the true frame period | 5/10 = 50% | PASS |
| burst_block_interleaver_recall | ≥ 50% of BPSK/QPSK block-interleaved bursts at Es/N0 ≥ 12 dB fully decoded | 6/12 = 50% | PASS |
| ccsds_concatenated_chain_not_wrong | ≥ 85% of CCSDS concatenated captures at Es/N0 ≥ 9 dB answered without a wrong claim (full or partial decode) | 11/12 = 92% | PASS |
