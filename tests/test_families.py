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


def _ccsds_frames(n_frames, rng, E=16, I=1, Q=0, randomizer='tm_131071'):
    """ASM + randomized RS codeblock per frame (CCSDS 131.0-B-5 order); also returns the payload."""
    import framing, rs
    asm = framing.MARKERS['ASM_1ACFFC1D']
    out, infos = [], []
    for _ in range(n_frames):
        info = rng.randint(0, 256, rs.code(E).k * I - Q).astype(np.int64)
        bits = rs.symbols_to_bits(rs.encode_codeblock(info, E, I, Q))
        if randomizer:
            bits = bits ^ framing.pn_sequence(randomizer, len(bits))
        out.append(np.concatenate([asm, bits]))
        infos.append(info)
    return np.concatenate(out).astype(np.uint8), np.concatenate(infos)


def test_rs_profiles_follow_the_frame_period():
    import blockcode
    assert (16, 1, 0) in blockcode.rs_profiles(2072 - 32)        # ASM + RS(255,223), I = 1
    assert (16, 4, 0) in blockcode.rs_profiles(8192 - 32)        # depth 4
    assert blockcode.rs_profiles(1001) == []                     # not a whole number of symbols
    assert blockcode.rs_profiles(8 * 255 * 9) == []               # longer than the deepest codeblock
    # A short codeblock is virtual fill, which is in the catalogue: 125 symbols is I = 1, Q = 130.
    assert (16, 1, 130) in blockcode.rs_profiles(1000)


def test_f4_decodes_the_full_ccsds_chain():
    """RS + randomizer + ASM + inner K7: all four layers of the concatenated catalogue chain."""
    import rs
    rng = np.random.RandomState(31)
    frames, info = _ccsds_frames(4, rng)
    r = pipeline.analyze_iq(_bpsk(conv_encode(frames, stream.CODE['generators'], 7), rng, snr_db=8.0))
    a4 = r['block_code']['accepted_hypothesis']
    assert r['status'] == 'DECODED' and r['code'] == 'ccsds_rs_255_223'
    assert (a4['E'], a4['I'], a4['Q'], a4['randomizer']) == (16, 1, 0, 'tm_131071')
    assert a4['n_decoded'] == a4['n_codewords'] == 4 and not a4['degenerate']
    assert a4['log10_p'] <= r['block_code']['log10_threshold']
    assert _ber(r['payload_bits'], rs.symbols_to_bits(info)) < 0.01
    assert [layer['layer'] for layer in r['structure']['layers']] == ['stream_code', 'frame', 'block_code']
    assert r['frame']['accepted_hypothesis']['period_bits'] == 2072


def test_f4_decodes_a_tc_ldpc_cltu_and_reports_unresolved_polarity():
    import framing, ldpc
    rng = np.random.RandomState(32)
    info = rng.randint(0, 2, (24, 64)).astype(np.uint8)
    pn = framing.pn_sequence('tc_btg', ldpc.N)
    cltu = np.concatenate([framing.MARKERS['ASM_034776C7272895B0']]
                          + [c ^ pn for c in ldpc.encode(info)]).astype(np.uint8)
    r = pipeline.analyze_iq(_bpsk(cltu, rng, snr_db=9.0))
    a4 = r['block_code']['accepted_hypothesis']
    assert r['status'] == 'DECODED' and r['code'] == 'ccsds_tc_ldpc_128_64'
    assert a4['offset'] == 64 and a4['randomizer'] == 'tc_btg'      # right after the start sequence
    assert a4['satisfied_checks'] == a4['total_checks']
    # H has only even-weight rows, so a complemented codeword is a codeword: without a periodic
    # marker to anchor it the polarity cannot be resolved, and the engine must say so.
    assert a4['polarity'] == 'unresolved' and a4['polarity_resolved'] is False
    assert _ber(r['payload_bits'], info.reshape(-1)) < 0.01         # complement-tolerant


def test_f4_refuses_a_frame_with_no_code_and_a_degenerate_codeblock():
    import framing
    rng = np.random.RandomState(33)
    asm = framing.MARKERS['ASM_1ACFFC1D']
    random_frames = np.concatenate([np.concatenate([asm, rng.randint(0, 2, 2040).astype(np.uint8)])
                                    for _ in range(6)]).astype(np.uint8)
    r = pipeline.analyze_iq(_bpsk(random_frames, rng, snr_db=9.0))
    assert r['status'] == 'SIGNAL_NO_CODE' and r['frame']['accepted'] and not r['block_code']['accepted']
    # Constant fill decodes as a Reed-Solomon codeword, so an RS claim on it must be refused on the
    # degenerate-codeword rule (§13.1 note 5), never accepted on decoder success.
    fill = np.concatenate([np.concatenate([asm, np.zeros(2040, np.uint8)]) for _ in range(6)]).astype(np.uint8)
    r2 = pipeline.analyze_iq(_bpsk(fill, rng, snr_db=12.0))
    assert r2['status'] != 'DECODED'
    for row in r2['block_code']['top']:
        assert not (row['log10_p'] <= r2['block_code']['log10_threshold'] and not row.get('degenerate')), row


def _higher_mod_burst(mod, spec, rng, esn0_db=20.0, sps=4, beta=0.35):
    import constellations as cs, interleavers as il
    n = spec[1] * spec[2]
    info = rng.randint(0, 2, n // 2).astype(np.uint8)
    bits = il.interleave(conv_encode(info, stream.CODE['generators'], 7)[:n], spec)
    syms = cs.modulate(bits, mod)
    sig = modem.pulse_shape(syms, sps, modem.rrc_filter(beta, sps))
    snr = esn0_db - 10 * np.log10(len(sig) / len(syms))
    return modem.channel(sig, snr, 0.003, 0.0, 0.5, rng)[0], info


def test_higher_modulations_are_off_by_default():
    """EXPERIMENTAL: 8PSK/16-QAM must not be searched unless asked for, and the gates are reported."""
    assert pipeline.SEARCH_HIGHER_MODULATIONS is False
    rng = np.random.RandomState(51)
    iq, _ = _higher_mod_burst('16QAM', ('block', 12, 16), rng)
    r = pipeline.analyze_iq(iq)
    gates = r['diagnostics']['modulation_gates']
    assert all(not g['enabled'] and not g['searched'] for g in gates.values())
    assert 'constant_modulus_contradiction_log10p' in gates['16QAM']       # still measured
    assert all(h['modulation'] in pipeline.MODULATIONS for h in r['diagnostics']['top_hypotheses'])
    assert r['modulation'] in (None,) + pipeline.MODULATIONS


def test_higher_modulations_decode_when_enabled():
    rng = np.random.RandomState(41)
    for mod in ('8PSK', '16QAM'):
        iq, info = _higher_mod_burst(mod, ('block', 12, 16), rng)
        r = pipeline.analyze_iq(iq, search_higher_modulations=True)
        assert r['status'] == 'DECODED' and r['modulation'] == mod, (mod, r['status'])
        assert r['interleaver'] == [12, 16] and _ber(r['payload_bits'], info) < 0.01


def test_eighth_power_estimators_are_what_8psk_needs():
    """8PSK: y^4 and x^4 are data-dependent, so the q4/order-4 estimators cannot see it."""
    rng = np.random.RandomState(41)
    iq, _ = _higher_mod_burst('8PSK', ('block', 12, 16), rng, esn0_db=26.0)
    table = pipeline._sps_table(iq, higher=True)
    assert max(table, key=lambda r: r['q8'])['sps'] == 4          # the true symbol rate
    assert max(table, key=lambda r: r['q4'])['sps'] != 4          # q4 ranks it nowhere
    assert 4 in pipeline._sps_candidates(table, 4.0, higher=True)
    low, _ = pipeline._cfo_candidates(iq, orders=(2, 4))
    high, _ = pipeline._cfo_candidates(iq, orders=(2, 4, 8))
    # The x^8 line locates the carrier; x^2/x^4 are off by ~10^-3 cycles/sample, which is enough to
    # rotate a burst out of coherence.
    assert min(abs(c['cfo'] - 0.003) for c in high) < 1e-4
    assert min(abs(c['cfo'] - 0.003) for c in low) > 1e-3


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
