"""Salesforce hand-off: the operational workforce layer, built for a link that is usually down.

A monitoring station is not a reliable client of a cloud CRM. The network is intermittent, the
analysis is the part that must never wait, and a case that silently fails to reach Salesforce is
worse than one that was never raised. So nothing here talks to Salesforce on the request path:

1. Raising a case writes it to a local outbox and returns. That write is the only thing that has to
   succeed for the operator to be done.
2. Delivery is a separate, explicit step. Each attempt reports exactly what happened, and an item is
   marked SENT only when Salesforce returns a record id. **There is no code path that reports a
   successful synchronisation without one.** When Salesforce is not configured, the outbox says
   NOT CONFIGURED and the items stay PENDING; that is the honest answer, not a failure to hide.
3. Retries back off, and an item Salesforce rejects for a reason retrying cannot fix (a malformed
   field, a permission error) moves to DEAD so a human looks at it, rather than being attempted
   forever.

What is sent is a decision, never a signal. `case_payload` builds the record from a fixed list of
fields: identifiers, the verdict, the statistics behind it and the receipt hash that lets anyone
re-verify it. Raw IQ, audio and the views in an evidence pack are never attached and cannot be:
anything not on the list is dropped, and `assert_no_bulk_data` fails loudly if a caller tries.
Exporting a capture is a separate, deliberate, operator-initiated action; it is not something a
background sync does.

Configuration is environment-only (never a file in the repo):

    SALESFORCE_LOGIN_URL      https://login.salesforce.com (or your My Domain / test instance)
    SALESFORCE_CLIENT_ID      connected app consumer key
    SALESFORCE_CLIENT_SECRET  connected app consumer secret
    SALESFORCE_REFRESH_TOKEN  refresh token for the integration user
    SALESFORCE_OBJECT         API name of the target object (default: Case)
"""

import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTBOX = os.path.join(ROOT, 'results', 'outbox.jsonl')

PENDING, SENT, DEAD = 'PENDING', 'SENT', 'DEAD'
CONFIGURED, NOT_CONFIGURED = 'CONFIGURED', 'NOT CONFIGURED'

MAX_ATTEMPTS = 6
BACKOFF_S = (30, 120, 600, 1800, 7200, 21600)     # ~30 s to 6 h; the last is reused if reached
USER_AGENT = 'SIH26147-research'

# The only fields that may leave this machine. Everything else in an evidence pack stays here.
CASE_FIELDS = ('pack_id', 'status', 'code', 'modulation', 'sps', 'interleaver', 'log10_p',
               'log10_threshold', 'n_hypotheses', 'receipt_hash', 'capture_sha256', 'analysed_at',
               'station', 'source_kind', 'data_quality', 'sufficiency_verdict', 'summary',
               'raised_by', 'priority')
# Anything carrying samples, audio or images. Named so the check fails loudly rather than quietly.
BULK_KEYS = ('iq', 'payload_bits', 'views', 'spectrogram', 'psd', 'constellation', 'timeseries',
             'audio', 'wav', 'samples_b64', 'capture', 'raw')


def _now():
    return dt.datetime.now(dt.timezone.utc)


def _iso(when=None):
    return (when or _now()).astimezone(dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def _parse(iso):
    try:
        return dt.datetime.fromisoformat(str(iso).replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None


class BulkDataRefused(ValueError):
    """Raised when a caller tries to put signal data into a CRM record."""


def assert_no_bulk_data(payload):
    """Refuse anything that would carry a capture off this machine."""
    def walk(node, path='payload'):
        if isinstance(node, dict):
            for k, v in node.items():
                if k.lower() in BULK_KEYS:
                    raise BulkDataRefused(
                        f'{path}.{k} would carry signal data to the CRM. Captures, audio and views '
                        f'are never synchronised; export them deliberately instead.')
                walk(v, f'{path}.{k}')
        elif isinstance(node, (list, tuple)):
            if len(node) > 64:
                raise BulkDataRefused(f'{path} has {len(node)} elements: too large for a CRM field')
            for i, v in enumerate(node):
                walk(v, f'{path}[{i}]')
        elif isinstance(node, str) and len(node) > 32000:
            raise BulkDataRefused(f'{path} is {len(node)} characters: too large for a CRM field')
    walk(payload)
    return payload


def case_payload(pack, *, summary='', raised_by=None, priority='Medium', station=None):
    """The record a case carries: a decision and how to check it, never a signal.

    Built by picking known fields out of the evidence pack, so a pack gaining new content can never
    widen what is sent."""
    result = pack.get('result') or {}
    accept = pack.get('accept') or {}
    receipt = pack.get('receipt') or {}
    quality = pack.get('data_quality') or {}
    suff = pack.get('sufficiency') or {}
    out = {
        'pack_id': pack.get('id'),
        'status': result.get('status'),
        'code': result.get('code'),
        'modulation': result.get('modulation'),
        'sps': result.get('sps'),
        'interleaver': result.get('interleaver'),
        'log10_p': accept.get('log10_p'),
        'log10_threshold': accept.get('log10_threshold'),
        'n_hypotheses': accept.get('n_hypotheses'),
        'receipt_hash': receipt.get('hash'),
        'capture_sha256': (receipt.get('capture') or {}).get('sha256'),
        'analysed_at': pack.get('analysed_at'),
        'station': station,
        'source_kind': (pack.get('source') or {}).get('kind'),
        'data_quality': quality.get('status'),
        'sufficiency_verdict': suff.get('verdict'),
        'summary': summary,
        'raised_by': raised_by,
        'priority': priority,
    }
    out = {k: v for k, v in out.items() if k in CASE_FIELDS}
    return assert_no_bulk_data(out)


class Outbox:
    """An append-only queue on disk. Survives a restart, a crash and a flat network."""

    def __init__(self, path=OUTBOX):
        self.path = path

    def _read(self):
        if not os.path.exists(self.path):
            return []
        rows = []
        with open(self.path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue                      # a torn write never blocks the queue
        return rows

    def _write(self, rows):
        os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
        tmp = self.path + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            for r in rows:
                f.write(json.dumps(r, sort_keys=True, separators=(',', ':')) + '\n')
        os.replace(tmp, self.path)                    # atomic: readers never see a half file

    def add(self, item_id, kind, payload):
        """Queue one item. The id is the idempotency key: queueing it twice queues it once.

        For an evidence case the natural key is the receipt hash, which is already unique per
        decision, so a double click cannot raise two cases for the same analysis."""
        assert_no_bulk_data(payload)
        rows = self._read()
        for r in rows:
            if r['id'] == item_id:
                return r, False
        item = {'id': item_id, 'kind': kind, 'payload': payload, 'state': PENDING, 'attempts': 0,
                'created_utc': _iso(), 'next_attempt_utc': _iso(), 'last_error': None,
                'sent_utc': None, 'remote_id': None}
        rows.append(item)
        self._write(rows)
        return item, True

    def due(self, now=None):
        now = now or _now()
        return [r for r in self._read()
                if r['state'] == PENDING and (_parse(r['next_attempt_utc']) or now) <= now]

    def update(self, item_id, **fields):
        rows = self._read()
        for r in rows:
            if r['id'] == item_id:
                r.update(fields)
        self._write(rows)

    def counts(self):
        rows = self._read()
        return {'pending': sum(1 for r in rows if r['state'] == PENDING),
                'sent': sum(1 for r in rows if r['state'] == SENT),
                'dead': sum(1 for r in rows if r['state'] == DEAD),
                'total': len(rows)}

    def items(self, limit=50):
        """Newest first, without the payload: the queue view, not the data."""
        rows = self._read()[-limit:]
        return [{k: v for k, v in r.items() if k != 'payload'} for r in reversed(rows)]


class SalesforceError(RuntimeError):
    def __init__(self, message, *, permanent=False, status=None):
        super().__init__(message)
        self.permanent = permanent                     # retrying will not help
        self.status = status


class Salesforce:
    """Minimal Salesforce REST client: OAuth refresh-token flow, then sObject create.

    Credentials come from the environment and are never logged, echoed in an API response or written
    to the outbox."""

    API_VERSION = 'v60.0'

    def __init__(self, env=None):
        env = env or os.environ
        self.login_url = (env.get('SALESFORCE_LOGIN_URL') or 'https://login.salesforce.com').rstrip('/')
        self.client_id = env.get('SALESFORCE_CLIENT_ID')
        self.client_secret = env.get('SALESFORCE_CLIENT_SECRET')
        self.refresh_token = env.get('SALESFORCE_REFRESH_TOKEN')
        self.object_name = env.get('SALESFORCE_OBJECT') or 'Case'
        self._token = None
        self._instance = None

    @property
    def configured(self):
        return bool(self.client_id and self.client_secret and self.refresh_token)

    def status(self):
        """What this installation can actually do, with no credential in the answer."""
        missing = [name for name, value in (('SALESFORCE_CLIENT_ID', self.client_id),
                                            ('SALESFORCE_CLIENT_SECRET', self.client_secret),
                                            ('SALESFORCE_REFRESH_TOKEN', self.refresh_token))
                   if not value]
        return {'state': CONFIGURED if self.configured else NOT_CONFIGURED,
                'login_url': self.login_url, 'object': self.object_name,
                'missing_env': missing,
                'detail': ('Ready to deliver queued cases.' if self.configured else
                           'Salesforce is not configured on this machine, so nothing is delivered. '
                           'Cases are queued in the local outbox and no synchronisation is reported.')}

    def _post_form(self, url, fields, timeout):
        data = urllib.parse.urlencode(fields).encode()
        req = urllib.request.Request(url, data=data, method='POST', headers={
            'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8', 'replace'))

    def authenticate(self, timeout=15):
        if not self.configured:
            raise SalesforceError('Salesforce is not configured', permanent=True)
        try:
            tok = self._post_form(f'{self.login_url}/services/oauth2/token', {
                'grant_type': 'refresh_token', 'client_id': self.client_id,
                'client_secret': self.client_secret, 'refresh_token': self.refresh_token}, timeout)
        except urllib.error.HTTPError as e:
            # 400/401 here means the credentials are wrong: retrying with the same ones cannot help.
            raise SalesforceError(f'authentication refused ({e.code})', permanent=e.code in (400, 401),
                                  status=e.code) from None
        except (urllib.error.URLError, OSError) as e:
            raise SalesforceError(f'cannot reach Salesforce: {e}', permanent=False) from None
        self._token = tok.get('access_token')
        self._instance = (tok.get('instance_url') or '').rstrip('/')
        if not self._token or not self._instance:
            raise SalesforceError('authentication returned no access token', permanent=True)
        return True

    def create(self, payload, timeout=20):
        """Create one record. Returns its Salesforce id, or raises. Never returns a fabricated id."""
        assert_no_bulk_data(payload)
        if not self._token:
            self.authenticate(timeout=timeout)
        url = f'{self._instance}/services/data/{self.API_VERSION}/sobjects/{self.object_name}/'
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), method='POST', headers={
            'Authorization': f'Bearer {self._token}', 'Content-Type': 'application/json',
            'User-Agent': USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = json.loads(r.read().decode('utf-8', 'replace'))
        except urllib.error.HTTPError as e:
            detail = e.read().decode('utf-8', 'replace')[:300]
            if e.code == 401:                          # the token expired mid-flight: retry later
                self._token = None
                raise SalesforceError(f'session expired: {detail}', permanent=False, status=401) from None
            permanent = 400 <= e.code < 500 and e.code not in (408, 429)
            raise SalesforceError(f'Salesforce refused the record ({e.code}): {detail}',
                                  permanent=permanent, status=e.code) from None
        except (urllib.error.URLError, OSError) as e:
            raise SalesforceError(f'cannot reach Salesforce: {e}', permanent=False) from None
        record_id = body.get('id')
        if not record_id:
            raise SalesforceError(f'Salesforce accepted the request without returning a record id: {body}',
                                  permanent=True)
        return record_id


def flush(outbox=None, client=None, limit=25, now=None):
    """Attempt delivery of everything due. Reports what happened; invents nothing.

    An item becomes SENT only on a Salesforce record id. A permanent rejection moves it to DEAD after
    the attempt; a transient one is retried later with a longer wait."""
    outbox = outbox or Outbox()
    client = client if client is not None else Salesforce()
    now = now or _now()
    report = {'attempted': 0, 'sent': 0, 'retry': 0, 'dead': 0, 'errors': [],
              'crm': client.status() if hasattr(client, 'status') else {}}
    due = outbox.due(now)[:limit]
    if not due:
        report['detail'] = 'nothing due for delivery'
        return report
    if hasattr(client, 'configured') and not client.configured:
        # Honest refusal: the queue is untouched and no synchronisation is claimed.
        report['detail'] = (f'{len(due)} case(s) are queued and stay queued: Salesforce is not '
                            f'configured on this machine.')
        report['retry'] = len(due)
        return report
    for item in due:
        report['attempted'] += 1
        attempts = item['attempts'] + 1
        try:
            record_id = client.create(item['payload'])
        except SalesforceError as e:
            wait = BACKOFF_S[min(attempts - 1, len(BACKOFF_S) - 1)]
            dead = e.permanent or attempts >= MAX_ATTEMPTS
            nxt = _iso(now + dt.timedelta(seconds=wait))
            outbox.update(item['id'], attempts=attempts, last_error=str(e),
                          state=DEAD if dead else PENDING, next_attempt_utc=nxt)
            report['dead' if dead else 'retry'] += 1
            report['errors'].append({'id': item['id'], 'error': str(e), 'permanent': e.permanent,
                                     'attempts': attempts, 'next_attempt_utc': None if dead else nxt})
            continue
        outbox.update(item['id'], state=SENT, attempts=attempts, sent_utc=_iso(now),
                      remote_id=record_id, last_error=None)
        report['sent'] += 1
    report['detail'] = (f"{report['sent']} delivered, {report['retry']} to retry, "
                        f"{report['dead']} moved to dead letter")
    return report


def status(outbox=None, client=None):
    outbox = outbox or Outbox()
    client = client if client is not None else Salesforce()
    return {'crm': client.status(), 'outbox': outbox.counts(), 'items': outbox.items(),
            'never_synchronised': list(BULK_KEYS)}
