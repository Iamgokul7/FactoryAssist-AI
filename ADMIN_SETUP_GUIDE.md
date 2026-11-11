# Administrator setup guide

Initial administrator configuration, account management and the security
settings that protect document management in FactoryAssist AI.

---

## 1. What is stored where

| Data | Location | Notes |
| --- | --- | --- |
| Accounts, password hashes, sessions, audit log | `data/managed/app.db` (SQLite) | Created on first start; ignored by Git |
| Document records and revisions | `data/managed/documents.json` | Ignored by Git |
| Uploaded PDFs | `Documents/uploads/` | Ignored by Git |
| Secrets (Gemini key, admin bootstrap password) | `.env` | Ignored by Git; never commit |
| Public configuration defaults | `.env.example` | Template only, no secrets |

Accounts are never created from code. There is no default username or password.

## 2. First start

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

On start the application creates `data/managed/` and the database schema, and
writes this to the log:

```text
No accounts exist yet - document management is locked until an administrator is created.
```

Until an administrator exists, `POST /api/auth/login` answers **503** with
`Document management setup is incomplete: no administrator account exists.`
The chatbot and status endpoints keep working normally.

## 3. Create the first administrator

### Option A — environment variables (recommended for a fresh install)

1. Open `.env` and set:

   ```dotenv
   INITIAL_ADMIN_USERNAME=plant.admin
   INITIAL_ADMIN_PASSWORD=<a long random password>
   ```

   Generate one, for example:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(24))"
   ```

2. Start (or restart) the application. The account is created once:

   ```text
   Bootstrap administrator 'plant.admin' created.
   ```

3. **Delete `INITIAL_ADMIN_PASSWORD` from `.env`.** The account already exists, so
   the value is no longer used; keeping it only leaves a password on disk.

4. Sign in once, then change the password from the account panel
   (`POST /api/auth/change-password`) so the only copy is the hash in the database.

Bootstrap is skipped when the password is weaker than the validation rule
(at least 12 characters, mixed case, a digit and a symbol) or when a user with
that name already exists. Both cases are logged without printing the password.

### Option B — command line

```bash
python -m backend.services.auth_store create-admin --username plant.admin
```

You are prompted for the password twice; it is never passed as an argument and
never appears in shell history or the audit log.

### Option C — add an administrator later, from an existing admin session

`POST /api/users`

```json
{
  "username": "second.admin",
  "password": "<at least 12 characters, mixed case, digit, symbol>",
  "role": "ADMIN",
  "full_name": "Second Administrator"
}
```

`GET /api/users` lists accounts with id, role, status and last sign-in. Note the
id in that listing: the update route is keyed by numeric id, not username.

## 4. Accounts and roles

| Capability | ADMIN | SOP_MANAGER | EMPLOYEE |
| --- | --- | --- | --- |
| Chat with the SOP copilot | Yes | Yes | Yes |
| View the document register and details | Yes | Yes | No |
| Upload a revision | Yes | Yes | No |
| Activate, reject, archive, retry | Yes | Yes | No |
| Edit document metadata | Yes | No | No |
| Read the audit trail | Yes | No | No |
| Create/disable accounts, change roles | Yes | No | No |
| Unarchive / restore a document | Yes | No | No |

Every rule above is enforced in `backend/api/deps.py` and the route handlers, on
the server. Hiding the sidebar item is a convenience, never the control.

Unauthenticated requests to any `/api/documents*`, `/api/audit` or
`/api/users*` endpoint return **401**. An authenticated user without the
required role receives **403**, and the attempt is written to the audit trail.

## 5. Day-to-day account tasks

| Task | How |
| --- | --- |
| List accounts | `GET /api/users`, or `python -m backend.services.auth_store list-users` |
| Change your own password | `POST /api/auth/change-password` with `current_password` and `new_password` |
| Promote an employee to SOP manager | `PATCH /api/users/<id>` with `{"role": "sop_manager"}` |
| Disable an account | `PATCH /api/users/<id>` with `{"is_active": false}` |
| Reset a forgotten password | `python -m backend.services.auth_store reset-password --username <name>` |

Disabling an account, changing its role and resetting its password all delete
that account's sessions immediately, so a stolen cookie stops working at once.

You cannot disable or demote the last remaining active administrator; the server
refuses with **409** so nobody locks the plant out of its own system.

## 6. Security settings in `.env`

| Variable | Default | Meaning |
| --- | --- | --- |
| `SESSION_TTL_HOURS` | `8` | Session lifetime; also refreshes the cookie on activity |
| `SESSION_COOKIE_SECURE` | `auto` | `auto` = Secure flag only on HTTPS; `true` when behind a proxy |
| `LOGIN_RATE_LIMIT_ATTEMPTS` | `5` | Failed logins allowed per account per window |
| `LOGIN_IP_MAX_ATTEMPTS` | `20` | Failed logins allowed from one client address per window, across all accounts |
| `LOGIN_RATE_LIMIT_WINDOW_MINUTES` | `15` | Window length; the limiter counts failed-login audit rows |
| `MAX_UPLOAD_SIZE_MB` | `25` | Largest accepted PDF |
| `MANAGED_DATA_DIR` | `data/managed` | Records and database |
| `UPLOAD_DIR` | `Documents/uploads` | Stored PDFs |

There is no secrets key to rotate for sessions: only a SHA-256 fingerprint of the
session token is stored, and no signing key exists that an operator could
accidentally share.

### Put the site behind HTTPS

The `Secure` cookie flag requires HTTPS. On `http://127.0.0.1:8000` the flag is
omitted so local development works. In production terminate TLS at your reverse
proxy and set:

```dotenv
SESSION_COOKIE_SECURE=true
```

Also make sure the proxy forwards `Host` unchanged, because CSRF protection
compares the `Origin` header with the request `Host`.

### CSRF

Every state-changing management call needs `X-CSRF-Token`, whose value comes from
`GET /api/auth/me` (`csrf_token`). The server also rejects a request whose
`Origin` does not match `Host`, so a browser cannot replay a cookie from a
foreign page. The frontend obtains both automatically; you only need this when
calling the API from scripts.

## 7. Verifying a fresh installation

```bash
# health and corpus (public)
curl -s http://127.0.0.1:8000/api/status

# management API must refuse anonymous callers
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/documents   # 401

# sign in (replace values, keep the cookie jar)
curl -s -c cookies.txt -H "Content-Type: application/json" \
  -d '{"username":"plant.admin","password":"<password>"}' \
  http://127.0.0.1:8000/api/auth/login
```

A successful login returns the user, role, a CSRF token and `expires_at`.

## 8. Backups

Back up these together, in this order:

1. `data/managed/app.db` — accounts and audit log.
2. `data/managed/documents.json` — document records.
3. `Documents/uploads/` — the stored PDFs referenced by the records.

Stop the server first, or copy the database with SQLite's online backup, so the
copy is consistent. The Chroma index can be rebuilt by reprocessing the uploads;
the audit trail cannot be rebuilt at all.

Restoring: put the three items back in place and restart. No migration step is
needed.

## 9. Audit trail

`GET /api/audit?limit=100` returns the newest events: sign-in success and
failure, sign-out, upload attempts and validation failures, processing results,
review actions, activation, archival, metadata edits, account and role changes,
and rejected management calls.

Each event records timestamp, user, action, document code, revision, result and a
short detail. Passwords, session tokens and API keys are never written.

## 10. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Login returns 503 with a setup message | No administrator exists | Use section 3 |
| Login returns 401 with a generic invalid-credentials message | Wrong username or password, or a disabled account | Reset the password with the CLI |
| Login returns 429 | Rate limit reached: five failures for that account, or twenty from that address, inside the window | Wait for the window, or raise `LOGIN_RATE_LIMIT_ATTEMPTS` / `LOGIN_IP_MAX_ATTEMPTS` deliberately |
| Every management call returns 403 `The request could not be verified` | Missing/stale CSRF token, or an `Origin` mismatch | Reload the page; check the proxy forwards `Host` |
| Cookie is not sent after login | `SESSION_COOKIE_SECURE=true` on plain HTTP, or a cross-site frontend | Match the setting to the scheme; serve the frontend from the same origin |
| `409` when disabling a user | Last active administrator | Create or promote another administrator first |
| Upload fails with `The PDF contains no extractable text` | Scanned PDF | Add a text layer; OCR is out of scope |
