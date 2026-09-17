"""Catalogue v1 primitives checked against references/ (CCSDS 131.0-B-5, CCSDS 231.0-B-4, 3GPP TS 36.212, reedsolo vectors)."""
import json, os, sys
import numpy as np
ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'src'))
import rs, ldpc, framing, interleavers as il   # noqa: E402

REF = lambda f: json.load(open(os.path.join(ROOT, 'references', f)))


def test_rs_encoder_matches_independent_vectors():
    for prof in REF('rs_ccsds_conventional_vectors.json')['profiles'].values():
        c = rs.code(prof['E'])
        assert c.gen_high == prof['generator_poly_high_to_low']
        for v in prof['vectors'] + prof['shortened_vectors']:
            msg = list(bytes.fromhex(v['message_hex']))
            assert list(c.encode(msg)[-c.nsym:]) == list(bytes.fromhex(v['parity_hex']))


def test_rs_dual_basis_annex_f():
    d = REF('ccsds_constants.json')['rs_dual_basis']
    assert rs.FROM_DUAL[0b10111001] == 0b00101010 and rs.TO_DUAL[0b01011001] == 0b11101000
    for _, poly, dual in d['table_F1_rows_power_polyInAlpha_dual']:
        assert rs.TO_DUAL[int(poly, 2)] == int(dual, 2)


def test_rs_codeblock_corrects_and_never_miscorrects_here():
    rng = np.random.default_rng(1)
    for E, I, Q in [(16, 1, 0), (16, 4, 40), (8, 5, 0)]:
        info = rng.integers(0, 256, rs.code(E).k * I - Q)
        bad = rs.encode_codeblock(info, E, I, Q)
        pos = rng.choice(len(bad), E * I // 2, replace=False)
        bad[pos] ^= rng.integers(1, 256, len(pos))
        out = rs.decode_codeblock(bad, E, I, Q)
        assert out['n_decoded'] == I and np.array_equal(out['info_dual'], info)
    c = rs.code(16)
    for _ in range(50):   # beyond capacity: failure is allowed, a wrong codeword is not (in this sample)
        cw = c.encode(rng.integers(0, 256, c.k)); r = cw.copy()
        r[rng.choice(255, 19, replace=False)] ^= rng.integers(1, 256, 19)
        d, _, ok = c.decode(r)
        assert not ok or np.array_equal(d, cw)


def test_ldpc_h_g_consistent_and_null_exact():
    assert not ((ldpc.H.astype(int) @ ldpc.G.T.astype(int)) % 2).any() and ldpc.gf2_rank(ldpc.H) == 64
    rng = np.random.default_rng(3)
    cw = ldpc.encode(rng.integers(0, 2, (20, 64)))
    assert (ldpc.satisfied_checks(cw) == 64).all() and (ldpc.satisfied_checks(1 - cw) == 64).all()
    llr = 2 * ((1 - 2.0 * cw) + 0.5 * rng.standard_normal(cw.shape)) / 0.25
    hard, conv, _ = ldpc.minsum_decode(llr)
    assert conv.all() and np.array_equal(hard, cw)


def test_randomizers_match_published_bits():
    for k, v in REF('ccsds_constants.json')['randomizers'].items():
        assert ''.join(map(str, framing.pn_sequence(k, 40))) == v['first_40_bits']


def test_frame_sync_finds_asm_and_rejects_noise():
    rng = np.random.default_rng(5)
    P = 2072
    s = np.concatenate([rng.integers(0, 2, 777)] + [np.concatenate([framing.MARKERS['ASM_1ACFFC1D'], rng.integers(0, 2, P - 32)]) for _ in range(4)]).astype(np.uint8)
    s ^= (rng.random(len(s)) < 0.05).astype(np.uint8)
    bar = np.log10(0.01 * 0.2 / framing.family_domain(len(s)))
    m = framing.marker_search(s, 'ASM_1ACFFC1D')
    assert m['period_bits'] == P and m['offset_bits'] == 777 and m['log10_p'] <= bar
    null = rng.integers(0, 2, len(s)).astype(np.uint8)
    for cand in (framing.marker_search(null, 'ASM_1ACFFC1D'), framing.blind_search(null)):
        assert cand is None or cand['log10_p'] > bar
    const = np.zeros(20000, np.uint8)
    assert framing.structural_rejection(framing.blind_search(const), const) is not None


def test_interleavers_round_trip_and_qpp_table():
    t = REF('lte_qpp_table.json')
    assert len(t) == 188
    for e in t:
        i = np.arange(e['K'], dtype=np.int64)
        assert len(np.unique((e['f1'] * i + e['f2'] * i * i) % e['K'])) == e['K']
    rng = np.random.default_rng(0)
    for spec in [('block', 8, 15), ('diag', 8, 15), ('qpp', 40, 3, 10)]:
        n = spec[1] * spec[2] if spec[0] != 'qpp' else spec[1]
        c = rng.integers(0, 2, n); s = il.interleave(c, spec)
        assert np.array_equal(s[il.deinterleave_index(spec, len(s))], c)
    c = rng.integers(0, 2, 200); s = il.interleave(c, ('conv', 4, 3))
    assert np.array_equal(s[il.deinterleave_index(('conv', 4, 3), len(s))], c)


def test_spec_scan_matches_per_pair_loop_and_decodes_every_type():
    import blind_id as bi
    from fec import conv_encode
    rng = np.random.default_rng(4)
    n_obs = 300
    th = np.tanh(rng.standard_normal(n_obs))
    specs = il.candidates(n_obs)
    assert {s[0] for s in specs} == set(il.TYPES)
    scan = bi.syndrome_scan(th, specs)
    k = 0
    for spec in scan['specs']:                           # (spec, code) order, same signs as the loop
        for code in bi.CODE_CATALOGUE:
            chk = bi.syndrome_checks(th[il.deinterleave_index(spec, n_obs)], code)
            if len(chk):
                assert scan['n'][k] == len(chk) and scan['pos'][k] == int((chk > 0).sum())
                k += 1
    assert k == len(scan['n'])
    K7 = bi.CODE_CATALOGUE[0]
    for spec in [('block', 8, 15), ('diag', 8, 15), ('qpp', 120, 103, 90), ('conv', 3, 2)]:
        info = rng.integers(0, 2, 60).astype(np.uint8)
        coded = conv_encode(info, K7['generators'], 7)[:120]
        llrs = 1.0 - 2.0 * il.interleave(coded, spec)
        d = bi.decode_hypothesis(llrs, K7, spec)
        assert d['consistency'] == 1.0 and np.array_equal(d['decoded_bits'], info[:len(d['decoded_bits'])]), spec


def test_8psk_16qam_demapping_and_modulation_gates():
    import constellations as cs, modem
    rng = np.random.default_rng(2)
    for mod in ('8PSK', '16QAM'):
        bits = rng.integers(0, 2, cs.BITS_PER_SYMBOL[mod] * 3000).astype(np.uint8)
        s = cs.modulate(bits, mod)
        assert abs(np.mean(abs(s) ** 2) - 1) < 0.03
        N = 10 ** (-2.0)                                   # Es/N0 20 dB, phase offset 0.3 rad
        y = s * np.exp(0.3j) + np.sqrt(N / 2) * (rng.standard_normal(len(s)) + 1j * rng.standard_normal(len(s)))
        ph, (S, Nn) = cs.carrier_phase(y, mod), cs.symbol_snr(y, mod)
        ber = min(np.mean((cs.llrs(y * np.exp(-1j * (ph + r)), mod, S, Nn) < 0) != bits) for r in cs.ROTATIONS[mod])
        assert ber < 1e-3, (mod, ber)
        gate = cs.constant_modulus_contradiction_log10p(y)
        assert (gate < -10) if mod == '16QAM' else (gate > -2)
        if mod == '8PSK':
            assert cs.qpsk_signature_log10p(y) > -2
    q = modem.modulate(rng.integers(0, 2, 6000).astype(np.uint8), 'QPSK')
    y = q + 0.1 * (rng.standard_normal(len(q)) + 1j * rng.standard_normal(len(q)))
    assert cs.qpsk_signature_log10p(y) < -10 and cs.constant_modulus_contradiction_log10p(y) > -2
