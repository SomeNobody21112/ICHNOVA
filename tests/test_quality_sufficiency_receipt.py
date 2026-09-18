"""Data-quality gate, evidence sufficiency and the receipt chain.

These three sit around the verdict: quality says whether the capture can be trusted, sufficiency says
what would settle a refusal, and the receipt makes the decision checkable by someone else.
"""

import json
import os
import subprocess
import sys

import numpy as np
import pytest

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'src'))
sys.path.insert(0, os.path.join(ROOT, 'server'))

import quality                                   # noqa: E402
import receipt as receipts                       # noqa: E402
import sufficiency                               # noqa: E402
from evidence import build_pack                  # noqa: E402
from test_core import _coded_signal              # noqa: E402


def clean_capture(n=8000, seed=0):
    rng = np.random.default_rng(seed)
    return (rng.standard_normal(n) + 1j * rng.standard_normal(n)) / np.sqrt(2)


# ---------------------------------------------------------------- data quality
def test_clean_capture_is_good():
    q = quality.assess(clean_capture(), fs=1e6)
    assert q['status'] == 'GOOD', q['reasons']
    assert q['metrics']['samples'] == 8000 and q['metrics']['duration_s'] == pytest.approx(0.008)


def test_clipping_is_detected():
    iq = clean_capture()
    peak = np.max(np.abs(iq))
    iq[:400] = peak * np.exp(1j * np.angle(iq[:400]))      # 5 % of samples pinned at full scale
    q = quality.assess(iq, fs=1e6)
    assert q['status'] == 'FAILED' and any('full scale' in r for r in q['reasons'])


def test_dropouts_and_truncation_are_detected():
    iq = clean_capture()
    iq[1000:1400] = 0                                       # a dropped block
    q = quality.assess(iq, fs=1e6)
    assert q['status'] == 'FAILED' and any('zero runs' in r for r in q['reasons'])
    short = quality.assess(clean_capture(2000), fs=1e6, declared_samples=8000)
    assert short['status'] in ('DEGRADED', 'FAILED') and any('ends early' in r for r in short['reasons'])


def test_a_short_clean_capture_is_not_called_degraded():
    """Length is sufficiency's question, not the gate's, and one sample at the peak is not clipping."""
    q = quality.assess(clean_capture(420, seed=7), fs=1e6)
    assert q['status'] == 'GOOD', q['reasons']
    assert q['metrics']['clipped_fraction'] == 0.0


def test_dc_offset_and_real_valued_capture():
    iq = clean_capture() + 0.9
    assert quality.assess(iq, fs=1e6)['status'] == 'FAILED'
    real_only = clean_capture().real.astype(complex)         # no Q at all
    q = quality.assess(real_only, fs=1e6)
    assert q['status'] == 'FAILED' and any('quadrature' in r for r in q['reasons'])


def test_nonfinite_and_empty_and_bad_rate():
    iq = clean_capture(200)
    iq[5] = np.nan
    assert quality.assess(iq)['status'] == 'FAILED'
    assert quality.assess(np.array([], dtype=complex))['status'] == 'FAILED'
    assert quality.assess(clean_capture(), fs=float('nan'))['status'] == 'FAILED'


def test_quality_never_changes_the_verdict():
    """A clipped copy of a decodable capture still decodes; only the quality flag changes."""
    import pipeline
    iq, _ = _coded_signal(6, 'QPSK', seed=21)
    base = pipeline.analyze_iq(iq)
    limit = 0.35 * np.max(np.abs(iq))
    clipped = np.clip(iq.real, -limit, limit) + 1j * np.clip(iq.imag, -limit, limit)
    assert quality.assess(clipped)['status'] in ('DEGRADED', 'FAILED')
    assert pipeline.analyze_iq(clipped)['status'] == base['status'] == 'DECODED'


# ---------------------------------------------------------------- sufficiency
def test_decoded_needs_no_recapture():
    import pipeline
    iq, _ = _coded_signal(6, 'QPSK', seed=22)
    assert sufficiency.assess(pipeline.analyze_iq(iq)) is None


def test_noise_reports_no_trend_or_no_signal():
    import pipeline
    s = sufficiency.assess(pipeline.analyze_iq(clean_capture(3000, seed=3)))
    assert s['verdict'] in ('NO_TREND', 'NO_SIGNAL_EVIDENCE', 'IMPOSSIBLE_IN_DOMAIN', 'ACHIEVABLE')
    assert s['what_would_prove_it']


def test_short_block_is_reported_as_impossible_not_as_a_longer_capture():
    """A block too small to reach the bar must say so: more signal cannot help."""
    n_checks = 10                                            # a 32-bit block yields about this many
    assert sufficiency.best_attainable_log10p(n_checks) > -6.4
    fake = {'status': 'UNKNOWN',
            'accept': {'log10_p': -2.0, 'log10_threshold': -6.4, 'n_hypotheses': 20000},
            'diagnostics': {'top_hypotheses': [{'code': 'conv_k7_r12_171_133', 'interleaver': [4, 8],
                                                'modulation': 'BPSK', 'sps': 6, 'n_checks': n_checks,
                                                'n_positive': n_checks, 'log10_p': -3.0}]}}
    s = sufficiency.assess(fake)
    assert s['verdict'] == 'IMPOSSIBLE_IN_DOMAIN'
    assert s['required']['achievable'] is False and 'cannot help' in s['what_would_prove_it']


def test_trending_hypothesis_asks_for_a_derived_amount_of_signal():
    # -6.0 from 20 000 hypotheses is 10^-1.7 after correcting for the search: a real trend, short of
    # the bar. (A weaker one is covered by test_best_of_many_on_noise_is_not_a_trend.)
    fake = {'status': 'UNKNOWN',
            'accept': {'log10_p': -6.0, 'log10_threshold': -6.4, 'n_hypotheses': 20000},
            'diagnostics': {'top_hypotheses': [{'code': 'conv_k7_r12_171_133', 'interleaver': [8, 16],
                                                'modulation': 'BPSK', 'sps': 8, 'n_checks': 120,
                                                'n_positive': 78, 'log10_p': -6.0}]}}
    s = sufficiency.assess(fake, fs=1e6)
    assert s['verdict'] == 'ACHIEVABLE'
    req = s['required']
    # the number is derived from the observed agreement rate, not invented
    expected = sufficiency.checks_needed(78 / 120, -6.4)
    assert req['parity_checks_needed'] == expected > 120
    assert req['extra_parity_checks'] == expected - 120
    assert req['extra_coded_bits'] == req['extra_parity_checks'] * 2
    assert req['extra_seconds'] == pytest.approx(req['extra_samples'] / 1e6)


def test_best_of_many_on_noise_is_not_a_trend():
    """The best of tens of thousands of hypotheses agrees well by construction. Promising a decode
    from it would send an operator to capture signal that cannot help."""
    fake = {'status': 'UNKNOWN',
            'accept': {'log10_p': -5.3, 'log10_threshold': -6.8, 'n_hypotheses': 32076},
            'diagnostics': {'top_hypotheses': [{'code': 'conv_k7_r12_171_133', 'interleaver': [8, 16],
                                                'modulation': 'QPSK', 'sps': 8, 'n_checks': 116,
                                                'n_positive': 82, 'log10_p': -5.3}]}}
    s = sufficiency.assess(fake)
    assert s['verdict'] == 'NO_TREND' and s['required']['achievable'] is False
    assert 'best of 32076' in s['reason']


def test_evidence_refused_on_structure_does_not_ask_for_more_capture():
    """A hypothesis that passed the bar and failed a structural check is not short of evidence."""
    fake = {'status': 'UNKNOWN',
            'accept': {'log10_p': -7.5, 'log10_threshold': -7.1, 'n_hypotheses': 67950},
            'diagnostics': {'top_hypotheses': [{'code': 'conv_k7_r12_171_133', 'interleaver': [8, 16],
                                                'modulation': 'BPSK', 'sps': 8, 'n_checks': 127,
                                                'n_positive': 94, 'log10_p': -7.5,
                                                'structural_rejection': 'soft path metric 0.851 below floor 0.926'}]}}
    s = sufficiency.assess(fake)
    assert s['verdict'] == 'STRUCTURALLY_REJECTED'
    assert s['required']['achievable'] is False
    assert 'would not change this' in s['what_would_prove_it']


def test_more_evidence_is_needed_when_agreement_is_weaker():
    strong = sufficiency.checks_needed(0.80, -6.4)
    weak = sufficiency.checks_needed(0.55, -6.4)
    assert weak > strong > 0


def test_sufficiency_on_a_truncated_real_capture():
    """Truncation experiment: a capture that decodes in full is cut until it refuses, and the
    refusal must come with a usable explanation."""
    import pipeline
    iq, _ = _coded_signal(8, 'BPSK', seed=31, bits=240, dims=(16, 24))
    assert pipeline.analyze_iq(iq)['status'] == 'DECODED'
    for fraction in (0.5, 0.4, 0.3):
        r = pipeline.analyze_iq(sufficiency.truncate_capture(iq, fraction))
        if r['status'] == 'DECODED':
            continue
        s = sufficiency.assess(r)
        assert s is not None and s['verdict'] in ('ACHIEVABLE', 'IMPOSSIBLE_IN_DOMAIN',
                                                  'NO_TREND', 'NO_SIGNAL_EVIDENCE')
        if s['verdict'] == 'ACHIEVABLE':
            assert s['required']['extra_parity_checks'] > 0
        return
    pytest.skip('capture still decoded at every truncation tested')


# ---------------------------------------------------------------- receipts
def test_receipt_chain_verifies_and_detects_tampering(tmp_path):
    ledger = str(tmp_path / 'ledger.jsonl')
    rng = np.random.default_rng(5)
    for i in range(3):
        iq = rng.standard_normal(500) + 1j * rng.standard_normal(500)
        rec = receipts.build(capture_sha256=receipts.sha256_array(iq),
                             engine={'version': '0.3.0', 'commit': 'abc1234'},
                             decision={'status': 'UNKNOWN', 'pack_id': f'CAP-{i}'},
                             statistics={'log10_p': -1.0}, prev_hash=receipts.last_hash(ledger))
        receipts.append(rec, ledger)
    chain = receipts.verify_chain(receipts.read_ledger(ledger))
    assert chain['ok'] and chain['checked'] == 3

    # alter one decision: that receipt must fail
    rows = receipts.read_ledger(ledger)
    rows[1]['decision']['status'] = 'DECODED'
    broken = receipts.verify_chain(rows)
    assert not broken['ok'] and any(p['index'] == 1 for p in broken['problems'])

    # remove a receipt: the chain must not close over the gap
    assert not receipts.verify_chain([rows[0], rows[2]])['ok']


def test_receipt_is_bound_to_its_capture():
    iq = clean_capture(400)
    rec = receipts.build(capture_sha256=receipts.sha256_array(iq), engine={}, decision={}, statistics={})
    ok, detail = receipts.verify_against_capture(rec, iq)
    assert ok and detail['capture_sha256'] == detail['receipt_capture_sha256']
    assert not receipts.verify_against_capture(rec, clean_capture(400, seed=9))[0]


def test_hash_is_content_addressed_not_order_dependent():
    body = {'capture': {'sha256': 'a'}, 'decision': {'status': 'UNKNOWN'}, 'prev_hash': receipts.GENESIS}
    reordered = {'prev_hash': receipts.GENESIS, 'decision': {'status': 'UNKNOWN'}, 'capture': {'sha256': 'a'}}
    assert receipts.receipt_hash(body) == receipts.receipt_hash(reordered)


def test_pack_carries_quality_sufficiency_and_receipt(tmp_path):
    ledger = str(tmp_path / 'ledger.jsonl')
    iq, _ = _coded_signal(6, 'QPSK', seed=41)
    pack = build_pack(iq, 1e6, 'CAP-TEST', {'kind': 'UPLOAD'}, ledger_path=ledger)
    assert pack['data_quality']['status'] in ('GOOD', 'DEGRADED', 'FAILED')
    assert pack['receipt']['decision']['status'] == pack['result']['status']
    assert pack['receipt']['capture']['sha256'] == receipts.sha256_array(iq)
    if pack['result']['status'] == 'DECODED':
        assert pack['sufficiency'] is None
    json.dumps(pack, default=str)                            # the pack still serialises
    assert receipts.verify_chain(receipts.read_ledger(ledger))['ok']


def test_verify_receipt_cli(tmp_path):
    ledger = tmp_path / 'ledger.jsonl'
    rec = receipts.build(capture_sha256='deadbeef', engine={}, decision={'status': 'UNKNOWN'},
                         statistics={}, prev_hash=receipts.GENESIS)
    receipts.append(rec, str(ledger))
    script = os.path.join(ROOT, 'server', 'verify_receipt.py')
    out = subprocess.run([sys.executable, script, '--ledger', str(ledger), '--json'],
                         capture_output=True, text=True, timeout=180)
    assert out.returncode == 0 and json.loads(out.stdout)['ledger']['ok'] is True

    tampered = tmp_path / 'tampered.jsonl'
    rows = receipts.read_ledger(str(ledger))
    rows[0]['decision']['status'] = 'DECODED'
    tampered.write_text(receipts.canonical(rows[0]) + '\n', encoding='utf-8')
    out = subprocess.run([sys.executable, script, '--ledger', str(tampered), '--json'],
                         capture_output=True, text=True, timeout=180)
    assert out.returncode == 1 and json.loads(out.stdout)['ledger']['ok'] is False
