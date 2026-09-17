"""Acceptance families wired into the engine (Constitution v2.5 §13.1): F2 continuous stream code.

Each family is checked on a signal it should explain and on signals it must refuse. The bars come
from the engine (pipeline.FAMILY_WEIGHTS), never from a constant written here.
"""
import os
import sys

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'src'))

import modem, pipeline, stream                      # noqa: E402
from fec import conv_encode, viterbi_decode         # noqa: E402


def _bpsk(bits, rng, snr_db=6.0, sps=4, beta=0.35, cfo=0.004, phase=0.7):
    sig = modem.pulse_shape(modem.modulate(bits, 'BPSK'), sps, modem.rrc_filter(beta, sps))
    return modem.channel(sig, snr_db, cfo, 0.0, phase, rng)[0]


def _ber(decoded, original):
    d, o = np.asarray(decoded), np.asarray(original)
    L = min(len(d), len(o))
    return 1.0 if L == 0 else float(min(np.mean(d[:L] != o[:L]), np.mean(d[:L] != 1 - o[:L])))


def test_viterbi_any_start_state_beats_zero_start_midstream():
    """A stream that did not start with a reset encoder is only decodable with start='any'."""
    rng = np.random.RandomState(4)
    info = rng.randint(0, 2, 400).astype(np.uint8)
    coded = conv_encode(info, stream.CODE['generators'], 7)[200:]        # cut mid-stream
    llrs = 4.0 * (1.0 - 2.0 * coded)
    bits_any = viterbi_decode(llrs, stream.CODE['generators'], 7, terminated=False, start='any')
    bits_zero = viterbi_decode(llrs, stream.CODE['generators'], 7, terminated=False, start='zero')
    truth = info[100:]
    assert _ber(bits_any, truth) == 0.0
    assert _ber(bits_zero, truth) > 0.0


def test_f2_continuous_stream_decodes_with_and_without_g2_inversion():
    rng = np.random.RandomState(11)
    for inverted in (False, True):
        info = rng.randint(0, 2, 1200).astype(np.uint8)
        coded = conv_encode(info, stream.CODE['generators'], 7).copy()
        if inverted:
            coded[1::2] ^= 1                        # CCSDS 131.0-B-5 §3.3.1 G2 inversion
        r = pipeline.analyze_iq(_bpsk(coded, rng))
        f2 = r['stream_code']
        assert r['status'] == 'DECODED' and r['code'] == stream.CODE_NAME
        assert f2['accepted_hypothesis']['g2_inverted'] is inverted
        assert f2['best_log10_p'] <= f2['log10_threshold']
        assert _ber(r['payload_bits'], info) < 0.01


def test_f2_refuses_noise_and_uncoded_stream():
    rng = np.random.RandomState(12)
    noise = (rng.standard_normal(6000) + 1j * rng.standard_normal(6000)) / np.sqrt(2)
    uncoded = _bpsk(rng.randint(0, 2, 2400).astype(np.uint8), rng, snr_db=8.0)
    for iq in (noise, uncoded):
        r = pipeline.analyze_iq(iq)
        assert r['status'] != 'DECODED'
        assert not r['stream_code']['accepted']
        assert r['stream_code']['best_log10_p'] > r['stream_code']['log10_threshold']


def _asm_frames(n_frames, rng, period=512):
    """Frames of ASM + a 16-bit counter + random payload (a non-catalogue but framed format)."""
    import framing
    asm = framing.MARKERS['ASM_1ACFFC1D']
    out = []
    for i in range(n_frames):
        hdr = np.array([int(b) for b in f'{i:016b}'], np.uint8)
        out.append(np.concatenate([asm, hdr,
                                   rng.randint(0, 2, period - len(asm) - len(hdr)).astype(np.uint8)]))
    return np.concatenate(out).astype(np.uint8)


def test_f3_finds_asm_frames_without_a_code_and_reports_the_map():
    rng = np.random.RandomState(21)
    r = pipeline.analyze_iq(_bpsk(_asm_frames(12, rng), rng, snr_db=8.0))
    f3, acc = r['frame'], r['frame']['accepted_hypothesis']
    assert r['status'] == 'SIGNAL_NO_CODE' and f3['accepted']          # a frame is not a code
    assert acc['kind'] == 'catalogue_marker' and acc['marker'] == 'ASM_1ACFFC1D'
    assert acc['period_bits'] == 512 and acc['offset_bits'] == 0 and acc['n_frames'] == 12
    assert f3['best_log10_p'] <= f3['log10_threshold']
    # M3 covers the whole declared domain, not just the evaluated hypotheses.
    import framing
    assert f3['tested_hypotheses'] == sum(framing.family_domain(s['bits']) for s in f3['streams_tested'])
    m = f3['map']
    assert m['period_bits'] == 512 and m['header_bits'][0] == 0 and m['header_bits'][1] >= 32
    assert m['undetermined_columns'] + m['proven_constant_columns'] + m['proven_alternating_columns'] == 512
    assert m['frames_needed_per_column'] > 12                          # honest about what 12 frames prove


def test_f3_on_concatenated_stream_runs_on_the_f2_output():
    """Inner K7 over ASM frames: F2 accepts the stream, then the frame is found in its Viterbi output."""
    rng = np.random.RandomState(1000)
    info = _asm_frames(10, rng)
    r = pipeline.analyze_iq(_bpsk(conv_encode(info, stream.CODE['generators'], 7), rng, snr_db=8.0))
    assert r['status'] == 'DECODED' and r['code'] == stream.CODE_NAME
    assert _ber(r['payload_bits'], info) < 0.01
    acc = r['frame']['accepted_hypothesis']
    assert acc is not None and acc['source'] == 'f2_viterbi_output'
    assert acc['kind'] == 'catalogue_marker' and acc['period_bits'] == 512


def test_f3_refuses_noise_and_a_constant_carrier():
    rng = np.random.RandomState(22)
    noise = (rng.standard_normal(8000) + 1j * rng.standard_normal(8000)) / np.sqrt(2)
    idle = _bpsk(np.zeros(3000, np.uint8), rng, snr_db=12.0)
    for iq in (noise, idle):
        r = pipeline.analyze_iq(iq)
        assert not r['frame']['accepted'] and r['status'] != 'DECODED'


def test_serial_gate_keeps_the_coherent_front_end_of_a_framed_stream():
    """A repeating sync marker makes neighbouring decisions mildly dependent; the gate must target
    oversampled front ends (~75% agreement), not that."""
    rng = np.random.RandomState(1000)
    coded = conv_encode(_asm_frames(10, rng), stream.CODE['generators'], 7)
    r = pipeline.analyze_iq(_bpsk(coded, rng, snr_db=8.0))
    best = r['stream_code']['accepted_hypothesis']
    assert best is not None and best['agreement'] > 0.99      # the coherent front end, not a flipping one
    assert pipeline.SERIAL_AGREEMENT_MAX == 0.60


def test_family_bars_are_the_pre_registered_weights():
    """The weights are pre-registered (§13.1) and the bars must follow α·w/M, not a tuned constant."""
    assert pipeline.FAMILY_WEIGHTS == {'F1_burst_code': 0.50, 'F2_stream_code': 0.10,
                                       'F3_frame': 0.20, 'F4_block_code': 0.20}
    assert abs(sum(pipeline.FAMILY_WEIGHTS.values()) - 1.0) < 1e-12
    rng = np.random.RandomState(13)
    r = pipeline.analyze_iq(_bpsk(conv_encode(rng.randint(0, 2, 300).astype(np.uint8),
                                              stream.CODE['generators'], 7), rng))
    for fam in r['accept']['families']:
        w, M = fam['weight'], fam['tested_hypotheses']
        expected = np.log10(pipeline.ALPHA * w / max(M, 1))
        assert abs(fam['log10_threshold'] - expected) < 1e-9, fam['name']
