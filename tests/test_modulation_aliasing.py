"""Structural aliasing: the failure that keeps 8PSK and 16-QAM EXPERIMENTAL.

`reports/HIGHER_MODULATION_EXPERIMENT.md` measured the real cost of enabling the higher-order
search. It was not false accepts — those were 0 either way over 1,350 null captures. It was that a
BPSK capture which decoded bit-exactly came back as a confident 8PSK answer that was 40 % wrong.

That is a structural alias: a higher-order constellation can explain a lower-order signal, the
statistics are satisfied, and no p-value catches it because nothing is statistically wrong. The only
defences are the gate that refuses to search a modulation the signal contradicts, and keeping the
search off by default.

These tests are negative: they check that the wrong answer is not produced, and they fail loudly if
the evidence behind the EXPERIMENTAL label ever stops holding.
"""

import os
import sys

import numpy as np
import pytest

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'src'))

import constellations as cs                         # noqa: E402
import interleavers as il                           # noqa: E402
import modem                                        # noqa: E402
import pipeline                                     # noqa: E402
import stream                                       # noqa: E402
from fec import conv_encode                         # noqa: E402


def _burst(mod, spec, rng, esn0_db=20.0, sps=4, beta=0.35):
    """One interleaved, convolutionally coded burst on the given constellation."""
    n = spec[1] * spec[2]
    info = rng.randint(0, 2, n // 2).astype(np.uint8)
    bits = il.interleave(conv_encode(info, stream.CODE['generators'], 7)[:n], spec)
    # constellations.modulate handles the gated pair only; BPSK and QPSK live in modem.
    syms = cs.modulate(bits, mod) if mod in pipeline.GATED_MODULATIONS else modem.modulate(bits, mod)
    sig = modem.pulse_shape(syms, sps, modem.rrc_filter(beta, sps))
    snr = esn0_db - 10 * np.log10(len(sig) / len(syms))
    return modem.channel(sig, snr, 0.003, 0.0, 0.5, rng)[0], info


def _ber(decoded, original):
    d, o = np.asarray(decoded), np.asarray(original)
    n = min(len(d), len(o))
    return 1.0 if n == 0 else float(min(np.mean(d[:n] != o[:n]), np.mean(d[:n] != 1 - o[:n])))


SEEDS = (41, 51, 61, 71)


@pytest.mark.parametrize('seed', SEEDS)
def test_the_default_search_never_answers_a_bpsk_capture_with_a_higher_modulation(seed):
    """The regression guard. Whatever else changes, the shipped configuration must not do this."""
    iq, info = _burst('BPSK', ('block', 12, 16), np.random.RandomState(seed))
    r = pipeline.analyze_iq(iq)
    assert r['modulation'] not in pipeline.GATED_MODULATIONS, r['modulation']
    assert r['status'] == 'DECODED' and _ber(r['payload_bits'], info) == 0.0
    assert all(h['modulation'] in pipeline.MODULATIONS for h in r['diagnostics']['top_hypotheses'])


@pytest.mark.parametrize('seed', SEEDS)
def test_the_gate_refuses_8psk_on_a_signal_whose_fourth_power_contradicts_it(seed):
    """The gate is the defence that has to work even when the search is switched on.

    A BPSK or QPSK capture has a significant y^4 signature, which contradicts an 8PSK hypothesis
    outright. The gate must close on that evidence rather than letting the search find a rotation
    of an 8PSK mapping that happens to fit.
    """
    iq, _ = _burst('BPSK', ('block', 12, 16), np.random.RandomState(seed))
    r = pipeline.analyze_iq(iq, search_higher_modulations=True)
    gates = r['diagnostics']['modulation_gates']
    assert gates['8PSK']['enabled'] is True, 'this test is meaningless if the search stayed off'
    assert gates['8PSK']['searched'] is False, (
        'the 8PSK gate opened on a capture whose fourth-power signature contradicts it: this is the '
        'exact path that produced a confident, 40 % wrong answer in HIGHER_MODULATION_EXPERIMENT.md')


@pytest.mark.parametrize('seed', SEEDS)
def test_forcing_the_experimental_search_does_not_improve_a_capture_it_already_decodes(seed):
    """A tripwire in both directions.

    If the forced search returns a higher-order answer, it must be a *wrong* answer — that is what
    makes it an alias rather than an improvement. If it ever returns a higher-order answer that is
    also bit-exact, the evidence for keeping the gate off has changed and the experiment has to be
    re-run before anything is claimed. This test says so instead of quietly passing.
    """
    iq, info = _burst('BPSK', ('block', 12, 16), np.random.RandomState(seed))
    forced = pipeline.analyze_iq(iq, search_higher_modulations=True)
    if forced['modulation'] in pipeline.GATED_MODULATIONS:
        assert _ber(forced['payload_bits'], info) > 0.05, (
            'forcing the experimental gate produced a higher-order answer that is ALSO correct. '
            'That contradicts reports/HIGHER_MODULATION_EXPERIMENT.md. Re-run the experiment before '
            'leaving 8PSK/16-QAM labelled EXPERIMENTAL, and do not change the label on this test.')
    else:
        assert _ber(forced['payload_bits'], info) == 0.0, (
            'the forced search did not change the modulation but did damage the payload')


@pytest.mark.parametrize('mod', ['BPSK', 'QPSK'])
def test_a_constant_modulus_capture_closes_the_16qam_gate(mod):
    """16-QAM has three amplitude rings, so it is searched only when constant modulus is
    *contradicted*. A BPSK or QPSK capture does not contradict it, and the gate must stay closed
    on that evidence rather than letting a 16-QAM mapping alias onto a one-ring signal.

    The bar is the engine's own ALPHA, read from the engine. Writing a threshold here would make
    the test agree with a number nobody derived.
    """
    iq, _ = _burst(mod, ('block', 12, 16), np.random.RandomState(41))
    r = pipeline.analyze_iq(iq, search_higher_modulations=True)
    gate = r['diagnostics']['modulation_gates']['16QAM']
    log_alpha = float(np.log10(pipeline.ALPHA))
    assert gate['constant_modulus_contradiction_log10p'] > log_alpha, gate
    assert gate['searched'] is False, gate


def test_the_gates_are_measured_even_when_nothing_is_searched():
    """The evidence for the default has to be visible on every analysis, not only when asked for.
    A label that cannot be checked from the result is a claim, not a measurement."""
    iq, _ = _burst('BPSK', ('block', 12, 16), np.random.RandomState(41))
    gates = pipeline.analyze_iq(iq)['diagnostics']['modulation_gates']
    assert set(gates) == set(pipeline.GATED_MODULATIONS)
    for mod, g in gates.items():
        assert g['enabled'] is False and g['searched'] is False, (mod, g)
        assert any(k.endswith('log10p') for k in g), f'{mod} reports no evidence for its gate'
