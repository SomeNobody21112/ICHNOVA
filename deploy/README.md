# Deploying ICHNOVA behind HTTPS

**Status: IMPLEMENTED / CONFIGURED.** The configuration in this directory is complete and
self-consistent, and the application changes it depends on are covered by tests. It has **not** been
operated in production: no certificate has been issued for a real host, no traffic has been served,
and nothing here may be described as LIVE or DEPLOYED.

```
   client
     │  HTTPS (TLS 1.2 / 1.3, certificate from your CA)
     ▼
   nginx  ── deploy/nginx.conf
     │  HTTP on a private network address, never published to the host
     ▼
   ICHNOVA  ── server/app.py, authenticated API + built console
```

The Python server does not terminate TLS. That is deliberate: `server/app.py` is a standard-library
`ThreadingHTTPServer`, and putting certificate handling, ALPN, OCSP stapling and renewal inside it
would be worse in every respect than letting a proxy that already does all four do it. What the
application owns is authentication, authorisation, rate limiting and the security headers; what the
proxy owns is transport.

---

## 1. Before you start

| You need | Why |
|---|---|
| A DNS name pointing at the host | Certificates are issued to names, not addresses |
| Ports 80 and 443 reachable | 80 for the ACME challenge and the redirect, 443 for the service |
| A signing key | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| A user store | Demo accounts are off in this deployment; create real accounts first |

Create the user store before the first start. It is mounted read-only into the container:

```bash
mkdir -p deploy/config
python - <<'EOF'
import sys
sys.path.insert(0, 'server')
import auth
users = auth.Users(path='deploy/config/users.json')
users.add('your.name', 'a-password-of-at-least-8-characters', role='ADMIN', name='Your Name')
EOF
```

Roles are `ADMIN`, `ANALYST`, `REVIEWER`, `VIEWER`, enforced per endpoint on the server
(`server/auth.py`, `PERMISSIONS`). Give out the smallest one that works: only `ADMIN` may list
users, only `ADMIN` and `ANALYST` may run the engine or start a receiver session.

---

## 2. Certificates

Nothing in this repository contains or generates a real certificate, and none may ever be committed.
`deploy/certs/` and `deploy/acme/` are ignored by git for that reason.

**Let's Encrypt.** Issue once, on the host, then renew on a schedule:

```bash
mkdir -p deploy/certs deploy/acme
docker run --rm \
  -v "$PWD/deploy/certs:/etc/letsencrypt" \
  -v "$PWD/deploy/acme:/var/www/certbot" \
  -p 80:80 certbot/certbot certonly --standalone \
  -d ichnova.example.org --agree-tos -m you@example.org --no-eff-email
```

Then replace `ichnova.example.org` throughout `deploy/nginx.conf` with your own name.

**An internal CA.** Put `fullchain.pem`, `privkey.pem` and `chain.pem` in
`deploy/certs/live/<your-host>/` and point `ssl_certificate*` at them. For a monitoring station on a
closed network this is usually the right answer, not Let's Encrypt.

**Renewal.** Run certbot renew on a schedule and reload nginx afterwards
(`docker compose -f deploy/docker-compose.yml exec proxy nginx -s reload`). Do not enable HSTS until
you have watched one renewal succeed: a browser that has seen the header refuses plain HTTP to that
host for the whole `max-age`, so a failed renewal takes the service down for everyone who has ever
visited it.

---

## 3. Start it

```bash
export ICHNOVA_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
export ICHNOVA_TRUSTED_PROXIES=172.18.0.3      # see below
docker compose -f deploy/docker-compose.yml up --build -d
```

`ICHNOVA_TRUSTED_PROXIES` must be the proxy's address **on the compose network**, which you can read
once the stack is up:

```bash
docker compose -f deploy/docker-compose.yml exec ichnova getent hosts proxy
```

This matters. `X-Forwarded-For` is a request header, so anybody can send one. The application
believes it only when the peer is in this list, and then reads the **rightmost** entry, because that
is the address the proxy itself observed. Leave the variable empty and the header is ignored
entirely, which is the correct behaviour for a server exposed directly. Set it too permissively and
the rate limiter is gone: a client sending a new value per request gets a new bucket per request,
and the login limiter stops existing.
(`server/app.py`, `Handler._client`; `tests/test_security_hardening.py`.)

---

## 4. Check it

```bash
# 1. HTTP redirects, and serves nothing else
curl -sSI http://ichnova.example.org/ | head -2            # 308, Location: https://...

# 2. TLS is real and the chain is complete
curl -sSI https://ichnova.example.org/api/health | head -1 # 200

# 3. The application's own headers survive the proxy
curl -sSI https://ichnova.example.org/api/health | grep -iE 'content-security-policy|x-frame|nosniff'

# 4. No cross-origin access is offered
curl -sSI -H 'Origin: https://evil.example' https://ichnova.example.org/api/health \
  | grep -i access-control-allow-origin || echo 'no CORS header: correct'

# 5. The API is closed
curl -sS https://ichnova.example.org/api/live/stations                     # 401
curl -sS https://ichnova.example.org/api/ledger                            # 401

# 6. The upload cap is enforced at the edge as well as in the application
head -c 70000000 /dev/zero | curl -sS -X POST --data-binary @- \
  "https://ichnova.example.org/api/analyze?format=iq" -o /dev/null -w '%{http_code}\n'   # 413
```

---

## 5. What this deployment does and does not give you

| | |
|---|---|
| Transport encryption | **CONFIGURED** — TLS 1.2/1.3, HTTP redirected, HSTS available |
| Certificate management | **CONFIGURED** — ACME or an internal CA; nothing committed |
| Forwarded-header handling | **IMPLEMENTED and tested** — trusted proxies only, rightmost hop |
| CORS | **IMPLEMENTED** — none offered; the API is same-origin |
| CSRF | **NOT APPLICABLE** — the console authenticates with a bearer token held in `sessionStorage`, never a cookie, so there is no ambient credential for another origin to ride. Secure and SameSite cookie flags do not apply here for the same reason. |
| Security headers | **IMPLEMENTED** — set by the application, not duplicated in the proxy |
| Rate limiting | **IMPLEMENTED** — per client in the application, per connection at the edge |
| Container hardening | **IMPLEMENTED** — non-root, read-only root filesystem, capabilities dropped, no new privileges, results on a named volume |
| Secrets | **IMPLEMENTED** — environment only; no credential, key or certificate is tracked |
| Operated in production | **NOT ESTABLISHED** — never run at a monitoring station, no operator feedback, no incident history |

The last row is the honest one. Everything above it is configuration that works; none of it is
evidence that this system has been run in anger.

---

## 6. If you are not using containers

The same shape applies. Run the application as an unprivileged service bound to loopback:

```bash
ICHNOVA_SECRET_KEY=... ICHNOVA_TRUSTED_PROXIES=127.0.0.1 ICHNOVA_DEMO_ACCOUNTS=0 \
ICHNOVA_USERS_FILE=/etc/ichnova/users.json \
HOST=127.0.0.1 PORT=8765 python server/app.py
```

and point `upstream ichnova` in `deploy/nginx.conf` at `127.0.0.1:8765`. Binding the application to
`0.0.0.0` with no proxy in front publishes an HTTP service that carries bearer tokens in clear,
which is the one configuration this directory exists to prevent.
