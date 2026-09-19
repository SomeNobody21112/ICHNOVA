"""The Salesforce hand-off, including the three things it must never do:

report a synchronisation that did not happen, carry signal data off the machine, or raise the same
case twice.
"""

import datetime as dt
import json
import os
import sys
import urllib.error

import pytest

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'server'))

import crm                                                    # noqa: E402


PACK = {
    'id': 'CAP-2026-0007',
    'analysed_at': '2026-09-19T04:15:00Z',
    'source': {'kind': 'UPLOAD', 'file': 'capture.iq'},
    'result': {'status': 'DECODED', 'code': 'conv_k7_r12_171_133', 'modulation': 'QPSK', 'sps': 6,
               'interleaver': [10, 12], 'payload_bits': list(range(512))},
    'accept': {'log10_p': -9.4, 'log10_threshold': -6.8, 'n_hypotheses': 50916},
    'receipt': {'hash': 'a' * 64, 'capture': {'sha256': 'b' * 64}},
    'data_quality': {'status': 'GOOD'},
    'sufficiency': None,
    'views': {'spectrogram': {'db': [[0] * 100] * 100}},
}


class FakeSalesforce:
    """A stand-in with the real client's contract, so delivery can be tested without an org."""

    def __init__(self, *, outcomes=(), configured=True):
        self.outcomes, self.calls, self._configured = list(outcomes), [], configured

    @property
    def configured(self):
        return self._configured

    def status(self):
        return {'state': crm.CONFIGURED if self._configured else crm.NOT_CONFIGURED, 'missing_env': []}

    def create(self, payload, timeout=20):
        crm.assert_no_bulk_data(payload)
        self.calls.append(payload)
        outcome = self.outcomes.pop(0) if self.outcomes else '500ABCDEFGHIJKL'
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def outbox(tmp_path):
    return crm.Outbox(str(tmp_path / 'outbox.jsonl'))


# ---------------------------------------------------------------- what may leave the machine
def test_case_payload_carries_the_decision_and_nothing_else():
    p = crm.case_payload(PACK, summary='Unlicensed carrier', raised_by='a.rao', station='MS-07')
    assert p['status'] == 'DECODED' and p['receipt_hash'] == 'a' * 64
    assert p['capture_sha256'] == 'b' * 64 and p['data_quality'] == 'GOOD'
    assert set(p) <= set(crm.CASE_FIELDS)
    for forbidden in ('payload_bits', 'views', 'iq', 'capture'):
        assert forbidden not in p
    assert len(json.dumps(p)) < 4000                  # a CRM record, not a capture


def test_signal_data_is_refused_loudly():
    for bad in ({'iq': [1, 2, 3]},
                {'note': {'views': {'psd': [1]}}},
                {'payload_bits': [0, 1]},
                {'audio': 'UklGRiQ='},
                {'blob': 'x' * 40000},
                {'many': list(range(500))}):
        with pytest.raises(crm.BulkDataRefused):
            crm.assert_no_bulk_data(bad)


def test_queueing_refuses_a_payload_with_signal_data(tmp_path):
    box = outbox(tmp_path)
    with pytest.raises(crm.BulkDataRefused):
        box.add('id-1', 'case', {'pack_id': 'CAP-1', 'views': {'psd': [1, 2]}})
    assert box.counts()['total'] == 0


# ---------------------------------------------------------------- the queue
def test_outbox_survives_a_restart_and_is_idempotent(tmp_path):
    box = outbox(tmp_path)
    payload = crm.case_payload(PACK)
    item, created = box.add(PACK['receipt']['hash'], 'case', payload)
    assert created and item['state'] == crm.PENDING
    again, created_again = box.add(PACK['receipt']['hash'], 'case', payload)
    assert not created_again and again['id'] == item['id']
    assert crm.Outbox(box.path).counts() == {'pending': 1, 'sent': 0, 'dead': 0, 'total': 1}


def test_a_torn_line_does_not_block_the_queue(tmp_path):
    box = outbox(tmp_path)
    box.add('good-1', 'case', {'pack_id': 'CAP-1'})
    with open(box.path, 'a', encoding='utf-8') as f:
        f.write('{"id": "half-written", "sta\n')       # a crash mid-write
    assert box.counts()['total'] == 1 and len(box.due()) == 1


def test_items_view_never_includes_the_payload(tmp_path):
    box = outbox(tmp_path)
    box.add('id-1', 'case', {'pack_id': 'CAP-1', 'summary': 'operational note'})
    rows = box.items()
    assert rows and 'payload' not in rows[0]
    assert 'operational note' not in json.dumps(rows)


# ---------------------------------------------------------------- delivery
def test_delivery_marks_sent_only_with_a_record_id(tmp_path):
    box = outbox(tmp_path)
    box.add('id-1', 'case', crm.case_payload(PACK))
    client = FakeSalesforce(outcomes=['5003X00000ABCDE'])
    report = crm.flush(box, client)
    assert report['sent'] == 1 and report['dead'] == 0
    row = box.items()[0]
    assert row['state'] == crm.SENT and row['remote_id'] == '5003X00000ABCDE' and row['sent_utc']
    assert not box.due()                               # a delivered case is not attempted again


def test_an_unconfigured_crm_never_reports_a_synchronisation(tmp_path):
    """The whole point: no Salesforce, no claim of having reached it."""
    box = outbox(tmp_path)
    box.add('id-1', 'case', crm.case_payload(PACK))
    report = crm.flush(box, FakeSalesforce(configured=False))
    assert report['sent'] == 0 and report['attempted'] == 0
    assert 'not configured' in report['detail']
    assert box.items()[0]['state'] == crm.PENDING      # still queued, nothing lost
    assert box.counts()['sent'] == 0


def test_a_transient_failure_is_retried_later_not_dropped(tmp_path):
    box = outbox(tmp_path)
    box.add('id-1', 'case', crm.case_payload(PACK))
    client = FakeSalesforce(outcomes=[crm.SalesforceError('cannot reach Salesforce', permanent=False)])
    report = crm.flush(box, client)
    assert report['sent'] == 0 and report['retry'] == 1 and report['dead'] == 0
    row = box.items()[0]
    assert row['state'] == crm.PENDING and row['attempts'] == 1 and row['last_error']
    assert not box.due()                               # backed off: not due immediately
    later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=crm.BACKOFF_S[0] + 1)
    assert len(box.due(later)) == 1                    # and it does come back


def test_a_permanent_rejection_goes_to_dead_letter_once(tmp_path):
    box = outbox(tmp_path)
    box.add('id-1', 'case', crm.case_payload(PACK))
    client = FakeSalesforce(outcomes=[crm.SalesforceError('field Foo__c does not exist', permanent=True)])
    report = crm.flush(box, client)
    assert report['dead'] == 1 and report['sent'] == 0
    assert box.items()[0]['state'] == crm.DEAD
    assert not box.due() and crm.flush(box, client)['attempted'] == 0


def test_retries_stop_after_max_attempts(tmp_path):
    box = outbox(tmp_path)
    box.add('id-1', 'case', crm.case_payload(PACK))
    now = dt.datetime.now(dt.timezone.utc)
    for attempt in range(crm.MAX_ATTEMPTS):
        client = FakeSalesforce(outcomes=[crm.SalesforceError('timeout', permanent=False)])
        crm.flush(box, client, now=now + dt.timedelta(days=attempt))
    row = box.items()[0]
    assert row['state'] == crm.DEAD and row['attempts'] == crm.MAX_ATTEMPTS


def test_flush_with_nothing_queued_says_so(tmp_path):
    report = crm.flush(outbox(tmp_path), FakeSalesforce())
    assert report['attempted'] == 0 and report['detail'] == 'nothing due for delivery'


# ---------------------------------------------------------------- credentials
def test_client_reports_missing_configuration_without_leaking_anything():
    client = crm.Salesforce(env={})
    s = client.status()
    assert s['state'] == crm.NOT_CONFIGURED and not client.configured
    assert set(s['missing_env']) == {'SALESFORCE_CLIENT_ID', 'SALESFORCE_CLIENT_SECRET',
                                     'SALESFORCE_REFRESH_TOKEN'}
    assert 'not configured' in s['detail']


def test_a_configured_client_never_echoes_its_secrets():
    client = crm.Salesforce(env={'SALESFORCE_CLIENT_ID': 'id-123', 'SALESFORCE_CLIENT_SECRET': 'not-a-real-secret',
                                 'SALESFORCE_REFRESH_TOKEN': 'not-a-real-token'})
    blob = json.dumps(client.status())
    assert client.configured and 'not-a-real-secret' not in blob and 'not-a-real-token' not in blob


def test_an_unconfigured_client_refuses_to_authenticate():
    with pytest.raises(crm.SalesforceError) as e:
        crm.Salesforce(env={}).authenticate()
    assert e.value.permanent


def test_a_response_without_a_record_id_is_an_error_not_a_success(monkeypatch):
    """Salesforce answering 200 with no id must never be recorded as delivered."""
    client = crm.Salesforce(env={'SALESFORCE_CLIENT_ID': 'i', 'SALESFORCE_CLIENT_SECRET': 's',
                                 'SALESFORCE_REFRESH_TOKEN': 'r'})
    client._token, client._instance = 'tok', 'https://example.my.salesforce.com'

    class Resp:
        def read(self):
            return b'{"success": true}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(crm.urllib.request, 'urlopen', lambda *a, **k: Resp())
    with pytest.raises(crm.SalesforceError) as e:
        client.create({'pack_id': 'CAP-1'})
    assert 'without returning a record id' in str(e.value) and e.value.permanent


def test_http_status_decides_whether_a_retry_could_help(monkeypatch):
    client = crm.Salesforce(env={'SALESFORCE_CLIENT_ID': 'i', 'SALESFORCE_CLIENT_SECRET': 's',
                                 'SALESFORCE_REFRESH_TOKEN': 'r'})
    client._token, client._instance = 'tok', 'https://example.my.salesforce.com'

    def raise_status(code):
        def fake(*a, **k):
            raise urllib.error.HTTPError('u', code, 'boom', {}, None)
        monkeypatch.setattr(crm.urllib.request, 'urlopen', fake)

    for code, permanent in ((400, True), (403, True), (429, False), (500, False), (503, False)):
        raise_status(code)
        with pytest.raises(crm.SalesforceError) as e:
            client.create({'pack_id': 'CAP-1'})
        assert e.value.permanent is permanent, code
