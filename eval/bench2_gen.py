"""bench-v2 signal and channel generators (Constitution v2.5 §18.1; `src/generate.py` stays untouched).

Every transmitter here is built from the catalogue v1 definitions (§12.1) or is a deliberate
**non-catalogue** null. Nothing in this file reads a receiver result, so a generator change can never
be a response to a sealed measurement.

Classes
-------
Catalogue (a correct answer exists):
  `burst_<mod>_<code>_<interleaver>`  zero-start burst: rate-½ convolutional code × burst interleaver
  `stream_k7`                          continuous K7, with or without CCSDS G2 inversion
  `ccsds_concat`                       RS(255, 255−2E) + randomizer + ASM + inner K7 (CCSDS order)
  `rs_framed`                          ASM + randomized RS codeblock, no inner code
  `tc_ldpc_cltu`                       64-bit start sequence + BTG-randomized (128,64) codewords
  `blind_framed`                       non-catalogue framed stream: constant header + counter + payload
                                       (the correct answer is SIGNAL_NO_CODE with a frame map)

Nulls (no catalogue structure; any structural accept is a false accept):
  `noise`, `uncoded_<mod>`, `mod_64qam` (out of catalogue), `conv_k9` (out of catalogue code),
  `rs_dvb_204_188` (wrong RS: conventional basis, DVB field), `linear_128_64` (wrong LDPC),
  `asm_random` (catalogue marker, random data — a frame but no code),
  `idle_carrier`, `perm_random` (non-catalogue random permutation interleaver)

Channels (§12 declares the receiver's assumptions; these deliberately go past some of them):
  `awgn`, `phase_noise` (Wiener), `cfo_drift` (linear), `rician` (block flat fading),
  `amplitude` (slow variation), `timing` (fractional delay)
"""

import numpy as np

import constellations as cs
import framing
import interleavers as il
import ldpc
import modem
import rs
from fec import conv_encode

CODES = {'k7': ([0o171, 0o133], 7), 'k5': ([0o23, 0o35], 5), 'k3': ([0o7, 0o5], 3)}
CODE_K9 = ([0o561, 0o753], 9)                 # out of catalogue
MODS = ('BPSK', 'QPSK', '8PSK', '16QAM')
SPECS = {'block': ('block', 12, 16), 'diag': ('diag', 12, 16),
         'conv': ('conv', 3, 2), 'qpp': ('qpp', 192, 23, 48)}
CHANNELS = ('awgn', 'phase_noise', 'cfo_drift', 'rician', 'amplitude', 'timing')
ESN0_DB = (3, 6, 9, 12, 15)
BITS_PER_SYMBOL = cs.BITS_PER_SYMBOL


# ------------------------------------------------------------------ modulation helpers
def modulate(bits, mod):
    return cs.modulate(bits, mod) if mod in ('8PSK', '16QAM') else modem.modulate(bits, mod)


def modulate_64qam(bits):
    """Square 64-QAM, Gray per axis — outside catalogue v1 (§12.1 'not in catalogue')."""
    bits = np.asarray(bits, dtype=np.uint8)
    b = bits[:len(bits) // 6 * 6].reshape(-1, 6)
    levels = np.array([-7, -5, -1, -3, 7, 5, 1, 3]) / np.sqrt(42)      # Gray-ordered PAM8
    idx = b[:, 0] * 4 + b[:, 1] * 2 + b[:, 2]
    idy = b[:, 3] * 4 + b[:, 4] * 2 + b[:, 5]
    return levels[idx] + 1j * levels[idy]


# ------------------------------------------------------------------ wrong-structure codes
_DVB_EXP, _DVB_LOG = None, None


def _dvb_tables():
    """GF(2⁸) with the DVB/conventional primitive polynomial x⁸+x⁴+x³+x²+1 (0x11d)."""
    global _DVB_EXP, _DVB_LOG
    if _DVB_EXP is None:
        exp = np.zeros(512, dtype=np.int64)
        log = np.zeros(256, dtype=np.int64)
        x = 1
        for i in range(255):
            exp[i] = x
            log[x] = i
            x <<= 1
            if x & 0x100:
                x ^= 0x11d
        exp[255:] = np.tile(exp[:255], 2)[:len(exp) - 255]
        _DVB_EXP, _DVB_LOG = exp, log
    return _DVB_EXP, _DVB_LOG


def rs_dvb_encode(msg, nsym=16):
    """RS(204,188) over the DVB field in the conventional basis: a Reed-Solomon code the catalogue
    does not contain (different field polynomial, different generator roots, no dual basis)."""
    exp, log = _dvb_tables()

    def mul(a, b):
        return 0 if a == 0 or b == 0 else int(exp[log[a] + log[b]])

    gen = [1]
    for i in range(nsym):
        gen = [0] + gen
        for j in range(len(gen) - 1):
            gen[j] ^= mul(gen[j + 1], int(exp[i]))
    out = list(np.asarray(msg, dtype=np.int64)) + [0] * nsym
    for i in range(len(msg)):
        c = out[i]
        if c:
            for j in range(1, len(gen)):
                out[i + j] ^= mul(gen[j], c)
    return np.array(list(np.asarray(msg, dtype=np.int64)) + out[len(msg):], dtype=np.int64)


def random_linear_128_64(rng, n_words):
    """Codewords of a random systematic (128,64) binary linear code — a 'wrong LDPC' null."""
    P = rng.randint(0, 2, (64, 64)).astype(np.uint8)
    info = rng.randint(0, 2, (n_words, 64)).astype(np.uint8)
    return info, np.concatenate([info, (info @ P) % 2], axis=1).astype(np.uint8)


# ------------------------------------------------------------------ bit-stream builders
BURST_CODED_BITS = 192          # one interleaver block: 12x16 = 192 = the QPP K used here


def burst_coded_bits(spec):
    """Coded bits one burst of this spec carries.

    A block or diagonal spec is rows x cols and a QPP spec is K, but a **convolutional** spec is
    (branches, delay) and says nothing about length: its block is as long as the transmitter chooses,
    and the interleaver adds (B-1)*D*B fill positions. Treating spec[1]*spec[2] as the length here
    generated 6-bit bursts for the convolutional class, which is why its recall was 0/60 in the first
    bench-v2 calibration run (a generator bug, not an engine one)."""
    if spec[0] == 'qpp':
        return spec[1]
    if spec[0] == 'conv':
        return BURST_CODED_BITS
    return spec[1] * spec[2]


def burst_bits(rng, code, spec, mod):
    """One zero-start burst: info → convolutional code → interleaver, sized to the spec."""
    n_coded = burst_coded_bits(spec)
    info = rng.randint(0, 2, n_coded // 2).astype(np.uint8)
    gens, K = CODES[code]
    coded = conv_encode(info, gens, K)[:n_coded]
    return il.interleave(coded, spec), info


def stream_bits(rng, n_info=1200, g2_inverted=False):
    info = rng.randint(0, 2, n_info).astype(np.uint8)
    coded = conv_encode(info, *CODES['k7']).copy()
    if g2_inverted:
        coded[1::2] ^= 1
    return coded, info


def rs_frames(rng, n_frames=4, E=16, I=1, Q=0, randomizer='tm_131071'):
    """ASM + randomized RS codeblock per frame; returns (bits, transmitted information symbols)."""
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


def ccsds_concat_bits(rng, n_frames=4, E=16, I=1, Q=0, randomizer='tm_131071', g2_inverted=True):
    """The CCSDS concatenated chain: RS → randomizer → ASM → inner K7 (§12.1 'Concatenated')."""
    frames, info = rs_frames(rng, n_frames, E, I, Q, randomizer)
    coded = conv_encode(frames, *CODES['k7']).copy()
    if g2_inverted:
        coded[1::2] ^= 1
    return coded, info


def cltu_bits(rng, n_codewords=24, randomizer='tc_btg'):
    pn = framing.pn_sequence(randomizer, ldpc.N) if randomizer else np.zeros(ldpc.N, np.uint8)
    info = rng.randint(0, 2, (n_codewords, 64)).astype(np.uint8)
    words = [c ^ pn for c in ldpc.encode(info)]
    return np.concatenate([framing.MARKERS['ASM_034776C7272895B0']] + words).astype(np.uint8), info.reshape(-1)


def blind_framed_bits(rng, n_frames=8, period=512):
    """Non-catalogue framing: a constant 32-bit header word that is not a catalogue marker, a 16-bit
    frame counter and a random payload. The correct answer is SIGNAL_NO_CODE with a frame map."""
    header = rng.randint(0, 2, 32).astype(np.uint8)
    out = []
    for i in range(n_frames):
        counter = np.array([int(b) for b in f'{i:016b}'], dtype=np.uint8)
        out.append(np.concatenate([header, counter,
                                   rng.randint(0, 2, period - 48).astype(np.uint8)]))
    return np.concatenate(out).astype(np.uint8), header


def asm_random_bits(rng, n_frames=6, period=2072):
    asm = framing.MARKERS['ASM_1ACFFC1D']
    return np.concatenate([np.concatenate([asm, rng.randint(0, 2, period - len(asm)).astype(np.uint8)])
                           for _ in range(n_frames)]).astype(np.uint8)


# ------------------------------------------------------------------ channels
def apply_channel(syms, sps, beta, esn0_db, channel, rng):
    """Pulse-shape and impair. Returns (iq, meta). Es/N0 is per symbol at the matched-filter output."""
    h = modem.rrc_filter(beta, sps)
    sig = modem.pulse_shape(syms, sps, h)
    meta = {'channel': channel, 'sps': sps, 'beta': beta, 'esn0_db': esn0_db}
    n = np.arange(len(sig))
    cfo = float(rng.uniform(-0.008, 0.008))
    tau = 0.0
    if channel == 'phase_noise':
        # Wiener phase noise: increments ~ N(0, sigma^2), sigma per sample (0.5–2 deg)
        sigma = float(rng.uniform(0.5, 2.0)) * np.pi / 180
        phi = np.cumsum(rng.standard_normal(len(sig)) * sigma)
        sig = sig * np.exp(1j * phi)
        meta['phase_noise_deg_per_sample'] = sigma * 180 / np.pi
    elif channel == 'cfo_drift':
        rate = float(rng.uniform(-2e-7, 2e-7))          # cycles/sample per sample
        sig = sig * np.exp(2j * np.pi * (0.5 * rate * n ** 2))
        meta['cfo_drift_per_sample'] = rate
    elif channel == 'rician':
        k_db = float(rng.uniform(6, 14))
        block = int(rng.choice([64, 128, 256]))
        k = 10 ** (k_db / 10)
        n_blocks = -(-len(sig) // block)
        diff = (rng.standard_normal(n_blocks) + 1j * rng.standard_normal(n_blocks)) / np.sqrt(2)
        gain = (np.sqrt(k / (k + 1)) + np.sqrt(1 / (k + 1)) * diff).repeat(block)[:len(sig)]
        sig = sig * gain
        meta.update(rician_k_db=k_db, fading_block=block)
    elif channel == 'amplitude':
        depth = float(rng.uniform(0.1, 0.4))
        period = float(rng.uniform(len(sig) / 4, len(sig)))
        sig = sig * (1.0 + depth * np.sin(2 * np.pi * n / period))
        meta.update(amplitude_depth=depth)
    elif channel == 'timing':
        tau = float(rng.uniform(-0.5, 0.5))
        meta['timing_offset'] = tau
    snr_per_sample = esn0_db - 10 * np.log10(len(sig) / max(len(syms), 1))
    iq, _ = modem.channel(sig, snr_per_sample, cfo, tau, float(rng.uniform(0, 2 * np.pi)), rng)
    meta.update(cfo=cfo, snr_per_sample_db=snr_per_sample, n_symbols=int(len(syms)))
    return iq, meta
