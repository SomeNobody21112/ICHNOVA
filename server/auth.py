"""Authentication, sessions and role-based access control (standard library only).

Design constraints (Constitution §9.1, §9.2, §25.8): no new dependencies, no cloud identity provider,
and the engine must still run air-gapped. What this module adds is real authentication in front of
the API instead of the client-side-only sign-in the prototype had.

- Passwords are stored as `scrypt$n$r$p$salt$hash` (hashlib.scrypt, RFC 7914). A plaintext password
  is never written anywhere, and comparisons use hmac.compare_digest.
- Sessions are HMAC-SHA256 tokens `payload.signature`, where payload carries the user, role and an
  absolute expiry. Nothing is stored server-side, so a restart invalidates every session; a logout
  additionally records the token id in a revocation set for the remainder of its lifetime.
- The signing key comes from ICHNOVA_SECRET_KEY. Without it the server generates a random key at
  start-up, which is safe (tokens simply do not survive a restart) and never a fixed default.
- Roles are only meaningful because endpoints check them (PERMISSIONS below).

Demo accounts exist because this is an SIH demonstration. They are created only when
ICHNOVA_DEMO_ACCOUNTS is not '0', they carry distinct non-admin roles, their passwords are random
unless given, and every one of them is marked demo=True so the console can label them.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

SESSION_TTL_S = int(os.environ.get('ICHNOVA_SESSION_TTL', 8 * 3600))
SCRYPT = {'n': 2 ** 14, 'r': 8, 'p': 1}

# Roles exist only where they change what the API allows.
ROLES = ('ADMIN', 'ANALYST', 'REVIEWER', 'VIEWER')
PERMISSIONS = {
    'analyse': ('ADMIN', 'ANALYST'),             # POST /api/analyze: run the engine on an upload
    'live': ('ADMIN', 'ANALYST'),                # start/stop a public-receiver session
    'review': ('ADMIN', 'ANALYST', 'REVIEWER'),  # record a review decision
    'read': ROLES,                               # read recordings, evidence, catalogue, health
    'admin': ('ADMIN',),                         # user list, source configuration
}


def hash_password(password, *, salt=None):
    if not isinstance(password, str) or len(password) < 8:
        raise ValueError('password must be at least 8 characters')
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **SCRYPT)
    return 'scrypt${n}${r}${p}${s}${h}'.format(s=base64.b64encode(salt).decode(),
                                               h=base64.b64encode(dk).decode(), **SCRYPT)


def verify_password(password, stored):
    """Constant-time check of a password against a stored scrypt record."""
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored.split('$')
        if scheme != 'scrypt':
            return False
        dk = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), dklen=32,
                            n=int(n), r=int(r), p=int(p))
    except Exception:
        return False
    return hmac.compare_digest(dk, base64.b64decode(hash_b64))


class Users:
    """User store. Backed by a JSON file when ICHNOVA_USERS_FILE is set, otherwise in memory."""

    def __init__(self, path=None):
        self.path = path or os.environ.get('ICHNOVA_USERS_FILE')
        self.users = {}
        if self.path and os.path.exists(self.path):
            with open(self.path, encoding='utf-8') as f:
                self.users = json.load(f)
        if not self.users and os.environ.get('ICHNOVA_DEMO_ACCOUNTS', '1') != '0':
            self._seed_demo_accounts()

    def _seed_demo_accounts(self):
        """Demo accounts for the SIH demonstration: distinct roles, never all-admin.

        Passwords come from the environment when provided, else are random per start-up. The console
        signs demo users in through /api/auth/demo, which never exposes a password."""
        demo = [('demo.analyst', 'Demo Analyst', 'ANALYST', 'MS-07'),
                ('demo.reviewer', 'Demo Reviewer', 'REVIEWER', 'MS-07'),
                ('demo.viewer', 'Demo Viewer', 'VIEWER', None)]
        for username, name, role, station in demo:
            env = os.environ.get(f'ICHNOVA_DEMO_PASSWORD_{role}')
            self.add(username, env or secrets.token_urlsafe(24), role=role, name=name,
                     station=station, demo=True, persist=False)

    def add(self, username, password, *, role='VIEWER', name=None, station=None, demo=False, persist=True):
        if role not in ROLES:
            raise ValueError(f'unknown role {role!r}')
        self.users[username] = {'username': username, 'name': name or username, 'role': role,
                                'station': station, 'demo': bool(demo),
                                'password': hash_password(password), 'created': int(time.time())}
        if persist:
            self.save()
        return self.users[username]

    def save(self):
        if not self.path:
            return
        tmp = self.path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self.users, f, indent=1)
        os.replace(tmp, self.path)

    def check(self, username, password):
        """Returns the user record, or None. Runs the KDF even for an unknown user so a wrong
        username and a wrong password take the same time."""
        rec = self.users.get(username)
        stored = rec['password'] if rec else hash_password('x' * 16)
        ok = verify_password(password or '', stored)
        return rec if (rec and ok) else None

    def public(self, rec):
        return {k: rec[k] for k in ('username', 'name', 'role', 'station', 'demo')}


class Sessions:
    """Stateless signed sessions with an absolute expiry and a revocation set for logout."""

    def __init__(self, secret=None, ttl=SESSION_TTL_S):
        env = secret or os.environ.get('ICHNOVA_SECRET_KEY')
        self.secret = (env.encode() if isinstance(env, str) else env) or secrets.token_bytes(32)
        self.ephemeral_key = env is None
        self.ttl = ttl
        self.revoked = {}

    def issue(self, user):
        now = int(time.time())
        payload = {'sub': user['username'], 'role': user['role'], 'name': user['name'],
                   'station': user.get('station'), 'demo': user.get('demo', False),
                   'iat': now, 'exp': now + self.ttl, 'jti': secrets.token_urlsafe(9)}
        raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(',', ':')).encode()).rstrip(b'=')
        sig = hmac.new(self.secret, raw, hashlib.sha256).digest()
        return raw.decode() + '.' + base64.urlsafe_b64encode(sig).rstrip(b'=').decode(), payload

    def verify(self, token):
        """Returns the payload, or None when the token is malformed, forged, expired or revoked."""
        if not token or token.count('.') != 1:
            return None
        raw, sig = token.split('.')
        try:
            raw_b = raw.encode()
            # Compare the encoded signature, not the decoded bytes: the last base64 character carries
            # four bits that decoding discards, so a token differing only in those would otherwise
            # verify. Only the exact encoding this server issues is accepted.
            want = base64.urlsafe_b64encode(hmac.new(self.secret, raw_b, hashlib.sha256).digest()).rstrip(b'=').decode()
            if not hmac.compare_digest(want, sig):
                return None
            payload = json.loads(base64.urlsafe_b64decode(raw_b + b'=' * (-len(raw_b) % 4)))
        except Exception:
            return None
        now = time.time()
        if payload.get('exp', 0) <= now:
            return None
        self._sweep(now)
        if payload.get('jti') in self.revoked:
            return None
        return payload

    def revoke(self, token):
        payload = self.verify(token)
        if payload:
            self.revoked[payload['jti']] = payload['exp']
        return bool(payload)

    def _sweep(self, now):
        for jti, exp in list(self.revoked.items()):
            if exp <= now:
                del self.revoked[jti]


def allowed(role, permission):
    return role in PERMISSIONS.get(permission, ())


class RateLimiter:
    """Fixed-window counter per client and bucket. Enough to stop a loop from exhausting the
    single-process analysis path; it is not a defence against a distributed flood."""

    def __init__(self, limits=None):
        self.limits = limits or {'auth': (10, 60), 'analyse': (12, 60), 'live': (6, 60), 'default': (240, 60)}
        self.hits = {}

    def check(self, client, bucket):
        limit, window = self.limits.get(bucket, self.limits['default'])
        now = time.time()
        key = (client, bucket)
        start, count = self.hits.get(key, (now, 0))
        if now - start >= window:
            start, count = now, 0
        count += 1
        self.hits[key] = (start, count)
        if len(self.hits) > 4096:                     # bound memory under scattered clients
            for k, (s, _) in list(self.hits.items()):
                if now - s >= window:
                    del self.hits[k]
        return (count <= limit, max(0, int(window - (now - start))))
