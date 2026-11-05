# TalentForge DevOps and integration

## Status (6 November 2026)

The claim fix and complete backend API workflow are verified against local
PostgreSQL 17. Production backend/database deployment is **not verified**. The
reported Cloudflare Pages frontend deployment was not independently verified.
This checkout's employer assessment/invitation screens and candidate submission
screens still use browser-local demo data. The backend-generated URL
`/candidate/invitation/:token` has no frontend route yet. API success does not
mean the deployed browser workflow works.

Verified locally after these changes: **99 backend tests passed** (including three
real PostgreSQL integration tests), frontend build/lint and six auth tests passed,
both Compose files validated, and the rebuilt backend reports healthy with HTTP
200 from `/health`, `/db-test`, and local CORS preflight. The container runs as
non-root. Existing invitation 2 remains unclaimed, public submissions remain empty,
and no temporary test schemas remain. Hosted CI, public HTTPS integration, TLS
against a production database, and a backup restore were not run. Only the backend
container was recreated; new loopback bindings for DB/frontend take effect when
those services are next recreated.

## Local setup and commands

Prerequisites: Git and Docker Desktop running Linux containers. For direct local
checks: Python 3.12 and Node 22. From the repository root in PowerShell:

```powershell
Copy-Item .env.example .env  # Only if .env does not already exist
```

Replace the DB password and JWT placeholders. Generate each independently with
`python -c "import secrets; print(secrets.token_urlsafe(48))"`. Never commit them.
For an existing volume, retain its DB password: changing `POSTGRES_PASSWORD` does
not rotate an initialized database's password.

```powershell
docker compose up -d --build
docker compose ps
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/db-test
docker compose logs --tail 100 backend
docker compose up -d --build --no-deps backend  # Backend rebuild only
docker compose stop                          # Preserve containers and data
docker compose down                          # Preserve named database volume
```

Frontend: http://localhost:5173; API docs: http://localhost:8000/docs. Local ports
bind to loopback. The frontend container runs Vite's development server; deploy
production frontend assets to Cloudflare Pages.

Never remove the database volume. Do not change the Compose project name without
locating and backing up its named volume.

## Environment

| Variable | Use |
| --- | --- |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Direct Python connections; local Compose supplies host `db` and DB identity |
| `DATABASE_URL` | Optional backend connection URL; overrides separate DB fields; URL-encode credentials |
| `DB_CONNECT_TIMEOUT` | Connection timeout in seconds; default 10 |
| `DB_SSLMODE`, `DB_SSLROOTCERT` | External PostgreSQL TLS mode and trusted CA file |
| `JWT_SECRET_KEY` | Required backend secret; independent random value per environment |
| `CORS_ORIGINS` | Comma-separated exact frontend origins without paths; defaults to local Vite origins |
| `FRONTEND_BASE_URL` | Base URL in invitation links; defaults to local Vite URL |
| `VITE_API_URL` | Public API URL; set at Cloudflare build time, then rebuild |
| `TEST_DATABASE_URL` | Enables real SQL tests; database user needs CREATE SCHEMA permission |

Never put secrets in `VITE_` variables: Vite embeds them in the browser bundle
([Vite documentation](https://vite.dev/guide/env-and-mode)).

## Database initialization and backup

Fresh volumes run `Backend/database/schema.sql`, then `seed.sql`. The seed skips
sample assessments when no employer exists. Existing volumes do not rerun these
files. Back up first, review the additive schema, and apply it explicitly:

```powershell
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d talentforge -f /docker-entrypoint-initdb.d/schema.sql
# Optional demo tasks, after an employer registers:
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d talentforge -f /docker-entrypoint-initdb.d/seed.sql
```

Use container `pg_dump` and `docker compose cp` to avoid PowerShell binary
redirection corrupting a backup. Choose unique dated filenames, keep backups
outside Git, restrict access, and copy them to encrypted storage:

```powershell
New-Item -ItemType Directory -Force backups
docker compose exec -T db pg_dump -U postgres -d talentforge -Fc -f /tmp/talentforge-backup.dump
docker compose cp db:/tmp/talentforge-backup.dump ./backups/talentforge-backup.dump
docker compose exec -T db pg_restore --list /tmp/talentforge-backup.dump
```

Verify restoration into a **new database**, never over the current one:

```powershell
docker compose exec -T db createdb -U postgres talentforge_restore_check
docker compose exec -T db pg_restore --exit-on-error --no-owner -U postgres -d talentforge_restore_check /tmp/talentforge-backup.dump
```

Check restored tables/counts. Remove only that disposable database according to
retention policy. A `pg_restore --list` check alone does not verify restoration.
Set a backup schedule and retention policy before production.

## Integration contract and tests

Workflow: register each role with `POST /register` -> `POST /auth/login` -> employer
`POST /assessments` -> `POST /assessments/{id}/publish` ->
`POST /assessments/{id}/invitations` -> candidate login ->
`POST /candidates/me` if no profile exists -> `POST /invitations/validate` ->
`POST /invitations/claim` -> `PATCH /submissions/{id}/answers` ->
`POST /submissions/{id}/submit`. Use the submission ID returned by claim.

Validation and claim accept `{ "token": "<token from link>" }` with the candidate
bearer JWT. Identity comes from the JWT. Claim locks the invitation and commits
acceptance and submission creation atomically. Repeated/simultaneous claims reuse
the same in-progress attempt; completed attempts return 409. Unknown, expired,
revoked, and mismatched links return a generic 404. No authentication returns 401;
wrong roles return 403. Answer PATCH merges keys; final submission blocks editing.
Invitation expiry controls claim/resume; owner-authenticated save/submit remains
available for an already-started attempt.

Real database tests execute the API handlers, password hashing, JWTs, SQL, commits,
and rollbacks. Every test creates and removes only its own random isolated schema;
public tables and existing records are untouched. Prefer a dedicated test database.

```powershell
Set-Location Backend
python -m venv .venv  # Only when needed
.venv/Scripts/python.exe -m pip install -r requirements.txt pytest
$env:JWT_SECRET_KEY = 'local-tests-only-secret-at-least-32-bytes'
# Set TEST_DATABASE_URL securely to your dedicated test database.
.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider
Set-Location ../Frontend
npm.cmd ci
npm.cmd run build
npm.cmd run lint
node --test tests/*.test.js
Set-Location ..
```

Without `TEST_DATABASE_URL`, PostgreSQL tests are explicitly skipped. They must
pass before treating an integration change as verified.

## CI

`.github/workflows/ci.yml` runs on main, development, and feature branch pushes,
and PRs to main/development. It builds/lints the frontend, runs frontend auth
tests, compiles Python, runs backend tests against disposable PostgreSQL 17, and
validates local/production Compose configuration. CI passwords are disposable
examples. There is no automatic deployment.

## Production deployment (pending approval and provisioning)

1. Provision PostgreSQL 17 with private networking where possible, TLS, and
   automated backups. Apply the reviewed schema with a migration/admin account;
   omit demo seeds. Create a runtime role with CONNECT, schema USAGE, table
   SELECT/INSERT/UPDATE/DELETE, and sequence USAGE/SELECT. Keep DDL privileges out
   of the runtime account; set equivalent default privileges for future tables.
2. Put `DATABASE_URL`, a new `JWT_SECRET_KEY`, exact HTTPS `CORS_ORIGINS`, and
   `FRONTEND_BASE_URL` in the host's secret store. The standalone
   `compose.production.yaml` runs only the backend and requires these values.
   It uses TLS `verify-full` to check the certificate and hostname
   ([PostgreSQL documentation](https://www.postgresql.org/docs/17/libpq-ssl.html)).
   The default CA path trusts public CAs. For a private CA, mount its certificate
   read-only and set `DB_SSLROOTCERT` to its container path. Keep verification on.
3. After approval, run `docker compose -f compose.production.yaml up -d --build`.
   Place an HTTPS reverse proxy on the same host in front of loopback port 8000;
   configure DNS, certificates, forwarding headers, and request limits for that
   host. On a container platform use `Backend/Dockerfile`, internal port 8000,
   and the platform's TLS/routing settings. The image runs as a non-root user.
4. Use `/health` for liveness and `/db-test` for readiness. Configure platform
   readiness to stop routing on DB failures. Monitor 5xx errors, availability,
   disk/storage pressure, and backup failures.
5. Cloudflare Pages: root `Frontend`, build `npm run build`, output `dist`, and
   `VITE_API_URL=https://<backend-host>`. Rebuild after URL changes. Verify browser
   CORS preflights from the exact deployed origin.
6. Coordinate frontend wiring with its owner: add `/candidate/invitation/:token`,
   preserve links through login/signup, create/load the profile, validate/claim,
   load assessment tasks, and save/finalize using the returned submission ID.
   Employer create/publish/invite screens also require API wiring in this checkout.
7. Before release, verify the full public HTTPS workflow with separate employer
   and candidate sessions, negative cases, persistence after restart, backup
   restoration, and secret-free logs. Record URLs/results before declaring
   deployment complete. Retain the previous image for code rollback; do not
   restore old data as a routine code rollback.

No production resources were provisioned or deployed by this change.

## Troubleshooting

- Claim 500: the INSERT used `RETURNING s.id, ...` without declaring `s`.
  `INSERT INTO submissions AS s` fixes `missing FROM-clause entry for table "s"`.
  Mock cursors did not execute SQL; real PostgreSQL tests now cover this path.
  Rebuild the backend after Python edits. Failure logs include only exception
  class and SQLSTATE, avoiding tokens and secret-bearing DB row/error contents.
- DB unhealthy: check service logs, host/port/password, and volume credentials.
  Never erase a volume to resolve an authentication failure.
- Browser cannot connect: verify HTTPS API URL and CORS origins. On Cloudflare,
  localhost means the visitor's machine; an HTTPS frontend needs an HTTPS API.
- Invitation link shows home: the missing frontend route is an integration gap,
  not evidence of an invalid backend token.
- Claim 404: sign in as the invited email and check expiry/revocation. Never
  publish invitation URLs, JWTs, environment output, dumps, or raw DB errors.
- PowerShell blocks npm.ps1: use `npm.cmd` without changing execution policy.
- Docker named-pipe access denied: ensure Docker Desktop is running and commands
  have local Docker access; do not delete or recreate the DB volume.
