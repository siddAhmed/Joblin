# Multi-User Support via Authentik -- Design Spec

**Date:** 2026-06-14
**Status:** Approved

---

## 1. Overview

Add multi-user support to Joblin by integrating with the existing Authentik instance already running on the same VPS (`localhost:9000`). Each user gets fully isolated data (companies, jobs, applications). Auth is handled entirely by Authentik + Caddy forward-auth -- no auth code in FastAPI or React.

Actual Budget's existing Authentik configuration is untouched. The only shared resource is the Authentik server itself, which is read-only from Joblin's perspective.

---

## 2. Authentication Flow

```
Browser
  |
  | HTTPS (Tailscale Funnel :10000)
  v
Caddy :80
  |-- forward_auth --> Authentik Embedded Outpost (host.docker.internal:9000)
  |                    - No valid session? Redirect to Authentik login page
  |                    - Valid session? Return 200 + X-authentik-* headers
  |
  | HTTP + X-authentik-username, X-authentik-email, X-authentik-name headers
  v
FastAPI :8000
  |-- get_current_user dependency reads X-authentik-username
  |-- auto-provisions users table row on first request
  |-- all queries filter by user_id
  v
SQLite
```

Single sign-on benefit: users already logged in to Actual Budget via Authentik are automatically authenticated for Joblin with no second login.

Password management: handled entirely in the Authentik user portal (`https://vps.capybara-nessie.ts.net/if/user/`). No password logic in Joblin.

---

## 3. Data Isolation

### New `users` table

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| authentik_username | String UNIQUE | Value from `X-authentik-username` header |
| is_admin | Boolean | First auto-provisioned user gets True |
| created_at | DateTime | |

### FK additions (Alembic migration)

All user-owned tables get a `user_id` INTEGER FK referencing `users.id`:
- `companies.user_id` -- primary ownership anchor
- `jobs.user_id` -- denormalized from parent company for query simplicity (always equals `company.user_id`, set by the scraper at insert time)
- `applications.user_id`
- Any future user-owned tables follow the same pattern

### Auto-provisioning

FastAPI `get_current_user` dependency (injected into every route):
1. Read `X-authentik-username` header
2. Look up user in `users` table
3. If not found, insert a new row (first user ever inserted gets `is_admin=True`)
4. Return the User ORM object

### Existing data migration

The Alembic migration:
1. Creates the `users` table
2. Inserts one row: `id=1, authentik_username=<ADMIN_USERNAME env var>, is_admin=True`
3. Adds `user_id` FK columns to all data tables, defaulting existing rows to `user_id=1`

`ADMIN_USERNAME` is set in `.env` before deploying. On first login, auto-provisioning finds the pre-seeded row and returns it -- existing data is preserved under the admin account.

---

## 4. User Management

Users are created and managed entirely in the Authentik admin panel. Joblin has no user creation UI or CLI.

- **Grant access**: create an Authentik account, add to the Joblin application's policy
- **Revoke access**: remove from the Joblin application or disable in Authentik
- **Change password**: Authentik user portal at `/if/user/`

The `is_admin` flag in Joblin's `users` table is set only on the first auto-provisioned user. It is reserved for future admin-only routes (e.g., viewing all users' data) and is not exposed in the UI initially.

---

## 5. Configuration Changes

### Caddyfile

Replace the `basic_auth` block with `forward_auth`:

```
:80 {
    forward_auth host.docker.internal:9000 {
        uri /outpost.goauthentik.io/auth/caddy
        copy_headers X-authentik-username X-authentik-email X-authentik-name

        @goauthentik_proxy_response header X-Goauthentik-Auth-Redirect .
        handle_response @goauthentik_proxy_response {
            redir * {http.reverse_proxy.header.Location} 302
        }
    }
    reverse_proxy app:8000
}
```

### docker-compose.yml

Add to the `caddy` service:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

Remove from the `app` service environment:
- `BASIC_AUTH_PASSWORD`

Remove from `.env`:
- `BASIC_AUTH_PASSWORD`

Add to `.env`:
- `ADMIN_USERNAME=<your Authentik username>`

### FastAPI

- New `backend/app/models/user.py`: `User` ORM model
- New `backend/app/dependencies/auth.py`: `get_current_user` dependency
- New Alembic migration: `users` table + `user_id` FK columns
- All existing routers inject `get_current_user` and filter queries by `current_user.id`

### Authentik (one-time, in admin UI)

1. **Providers > Create**: Proxy Provider, forward auth (single application), external host = `https://vps.capybara-nessie.ts.net:10000`
2. **Applications > Create**: point at the new provider
3. **Outposts > Embedded Outpost > Edit**: add the new application
4. **Application policy**: add allowed users or groups

No changes to the Actual Budget application, its provider, or any other Authentik configuration.

---

## 6. Non-Goals

- No Joblin-side admin UI for user management (Authentik handles this)
- No email notifications or invites (Authentik handles this)
- No per-user roles beyond the `is_admin` seed flag
- No changes to Actual Budget or its Authentik configuration
