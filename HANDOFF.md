# App Portal — Agent Handoff Document

**Repo:** https://github.com/jesusr-db/landing_page.git
**App URL (dev):** https://app-portal-dev-1351565862180944.aws.databricksapps.com
**Workspace:** https://fe-vm-vdm-classic-rikfy0.cloud.databricks.com
**Databricks profile:** `DEFAULT`

---

## Current State

The app is deployed and functional. It is a FastAPI + Vite/React Databricks App that lists all Databricks Apps in the workspace with role-based filtering.

**What works:**
- Frontend loads, shows apps, status badges render correctly
- "Available" tab (default) filters to RUNNING apps; "All" tab shows everything
- Category tabs parse `[Category]` prefix from app descriptions
- "Go to App" links use `app_obj.url` (direct app URL)
- Deployed via Databricks Asset Bundle (`databricks bundle deploy/run -t dev -p DEFAULT`)

**Current auth architecture (M2M — to be replaced):**
- `WorkspaceClient(host=DATABRICKS_HOST)` uses M2M OAuth (SP `ac182ff1-d9b4-49d6-bb33-8b9f91a47735`, auto-injected `DATABRICKS_CLIENT_ID/SECRET` by Apps runtime)
- Lists all workspace apps via `w.apps.list()` — returns all 10 apps regardless of user
- Tries to read ACLs per app using OBO token at `GET /api/2.0/permissions/apps/{name}` — **always 403** (requires `apps.ruleSets/get`, which the SP and user token both lack)
- Falls back to synthetic `users: CAN_USE` ACL → **all apps visible to all users** (not permission-filtered)

---

## Next Task: Refactor to OBO/U2M Authentication

### Why

The current M2M approach shows every app to every user. The correct behavior is per-user filtering where each user only sees apps they have CAN_USE or higher on. This is natively enforced by the Databricks API when called with a user token.

### Confirmed Working

This was tested and confirmed before writing this document:

```bash
# GET /api/2.0/apps with a user OAuth token returns only apps that user can see
curl -H "Authorization: Bearer <user_token>" \
  https://fe-vm-vdm-classic-rikfy0.cloud.databricks.com/api/2.0/apps
# Returns 10 apps (this user is workspace admin — regular users will see fewer)
```

The **list apps endpoint works with user tokens**. The previous OBO failures were only on the separate permissions endpoint (`/api/2.0/permissions/apps/{name}`) which requires elevated scopes.

### The OBO Token

In the Databricks Apps runtime, every request includes:
- `X-Forwarded-Email` — user's email
- `X-Forwarded-Access-Token` — user's live OAuth token (short-lived, ~1hr)
- `X-Forwarded-Preferred-Username` — username

The `X-Forwarded-Access-Token` is what to use for all OBO calls. It is already being read in `get_apps()` as `token = request.headers.get("X-Forwarded-Access-Token")`.

### The M2M Conflict Problem

**Do NOT do:** `WorkspaceClient(host=host, token=obo_token)`

This throws `ValueError: more than one authorization method configured: oauth and pat` because `DATABRICKS_CLIENT_ID` and `DATABRICKS_CLIENT_SECRET` are auto-injected as env vars by the Apps runtime and the SDK detects both PAT (token=) and OAuth (env vars) simultaneously.

**Solution:** Use `httpx` directly for all OBO calls. Do not involve the SDK for user-token operations.

### What the Refactored `GET /api/apps` Should Do

1. Get `token` from `X-Forwarded-Access-Token` header
2. Get `resolved_host` — still needs M2M `WorkspaceClient` briefly to resolve `w.config.host` (since `DATABRICKS_HOST` env var is empty in Apps runtime). This is a one-liner and fine to keep.
3. Call `GET /api/2.0/apps` via httpx with the user token — returns only apps that user can see
4. For each app, map `compute_status.state` to frontend status string (see mapping below)
5. Parse category from description
6. Return filtered list — **no ACL checking needed**, the API already enforced it

### Cache Architecture Change

The current `AppCache` is a two-tier workspace+user cache. With OBO, there is no shared workspace-level data — each user's list is different. **Replace with a simple per-user TTL cache:**

```python
class UserCache:
    def __init__(self, ttl: int = 300):
        self._ttl = ttl
        self._entries: dict[str, tuple[list[dict], float]] = {}  # email -> (data, expires)

    def get(self, email: str) -> list[dict] | None:
        entry = self._entries.get(email)
        if entry and time.monotonic() < entry[1]:
            return entry[0]
        return None

    def set(self, email: str, data: list[dict]) -> None:
        self._entries[email] = (data, time.monotonic() + self._ttl)
```

### Status Mapping

`w.apps.list()` (and the REST equivalent) returns `compute_status.state` as a `ComputeState` enum. `app_status` is always `None` from the list endpoint. Map as follows:

| compute_status.state | Frontend status string |
|---|---|
| `ACTIVE` | `RUNNING` |
| `PENDING` | `DEPLOYING` |
| `ERROR` | `CRASHED` |
| `STOPPED` | `STOPPED` |
| None / unknown | `UNKNOWN` |

The frontend `StatusBadge` component in `frontend/src/components/StatusBadge.tsx` expects exactly: `RUNNING`, `DEPLOYING`, `CRASHED`, `STOPPED`, or falls back to "Unknown".

### `can_manage` Field

Currently `can_manage` is derived from ACL (`_check_can_manage`). With OBO, we no longer have ACL data. Options:

1. **Drop it** — set `can_manage: False` for all apps. The field currently has no visible effect in the UI (no conditional UI exists for it).
2. **Keep M2M for that field only** — call `w.apps.get_permissions()` via M2M SP. This still 403s because the SP also lacks `apps.ruleSets/get`.
3. **Infer from what the API returns** — if the user is workspace admin, all apps are returned including stopped ones. Not reliable as a signal.

**Recommended: drop it (option 1).** Check `frontend/src/components/AppCard.tsx` — confirm `can_manage` has no visible UI effect before removing.

### Code to Delete After Refactor

These are no longer needed with OBO:
- `_dict_to_ns()` — only used to convert ACL dicts to SimpleNamespace
- `_fetch_acl_obo()` — the permissions endpoint approach
- `_check_acl()` — ACL checking logic
- `_check_can_manage()` — ACL manage check
- `AppCache` class (two-tier) — replace with `UserCache`
- `_fallback_acl` — synthetic ACL workaround
- `fetch_acl()` inner function and `anyio` task group for ACL fetching
- SCIM group lookup (`w.users.list(...)`) — only needed for group-based ACL matching, which is gone
- `anyio` import (if no longer used)

### Code to Keep

- `WorkspaceClient` — still needed briefly to resolve `w.config.host`
- `_parse_category()` — still needed
- `logging.basicConfig(level=logging.INFO)` — keep but can downgrade to WARNING in prod
- `httpx` import — still needed for OBO calls
- `DATABRICKS_HOST` env var read — still needed as hint to SDK host resolution

### Rough Shape of Refactored `get_apps`

```python
@app.get("/api/apps")
async def get_apps(request: Request) -> list[dict]:
    email = request.headers.get("X-Forwarded-Email", "unknown@unknown.com")
    token = request.headers.get("X-Forwarded-Access-Token")
    portal_app_name = os.environ.get("PORTAL_APP_NAME", "app-portal")

    cached = _cache.get(email)
    if cached is not None:
        return cached

    # Resolve host via M2M SDK (DATABRICKS_HOST is empty in Apps runtime)
    w = WorkspaceClient(host=DATABRICKS_HOST)
    resolved_host = w.config.host

    # Fetch apps the user can see via their OBO token
    url = f"{resolved_host.rstrip('/')}/api/2.0/apps"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()
        raw_apps = resp.json().get("apps", [])

    _STATUS_MAP = {"ACTIVE": "RUNNING", "PENDING": "DEPLOYING", "ERROR": "CRASHED"}

    result: list[dict] = []
    for a in raw_apps:
        if a.get("name") == portal_app_name:
            continue
        compute_state = a.get("compute_status", {}).get("state")
        status = _STATUS_MAP.get(compute_state, compute_state or "UNKNOWN")
        result.append({
            "name": a["name"],
            "display_name": a.get("display_name") or a["name"].replace("-", " ").title(),
            "description": a.get("description", ""),
            "url": a.get("url", ""),
            "status": status,
            "category": _parse_category(a.get("description")),
            "can_manage": False,
        })

    _cache.set(email, result)
    return result
```

Note: the REST response is plain JSON (dicts), not SDK objects — no need for `_dict_to_ns` or `getattr` gymnastics.

---

## Deployment

After any backend change:
```bash
databricks bundle deploy -t dev -p DEFAULT && databricks bundle run app-portal -t dev -p DEFAULT
```

After any frontend change, rebuild first:
```bash
cd frontend && npm run build && cd ..
databricks bundle deploy -t dev -p DEFAULT && databricks bundle run app-portal -t dev -p DEFAULT
```

View logs:
```bash
databricks apps logs app-portal-dev -p DEFAULT
```

---

## Key Files

| File | Purpose |
|---|---|
| `backend/main.py` | FastAPI backend — the only file needing changes |
| `app.yaml` | Databricks Apps runtime config (command, user_api_scopes) |
| `databricks.yml` | Asset Bundle config (targets, env vars) |
| `frontend/src/components/StatusBadge.tsx` | Status string → badge label mapping |
| `frontend/src/components/CategoryTabs.tsx` | Available/All/category tab logic |
| `frontend/src/components/AppGrid.tsx` | Filter logic (Available = status RUNNING) |
| `frontend/src/components/AppCard.tsx` | Check if `can_manage` has any UI effect |
| `frontend/dist/` | Built frontend (must be committed, not gitignored) |

---

## Known Issues / Watch-Outs

1. **`DATABRICKS_HOST` is empty** in the Apps runtime env — always use `w.config.host` after constructing `WorkspaceClient`. Do not use `DATABRICKS_HOST` directly in URLs.

2. **`app_status` is always None** from `apps.list()` — use `compute_status.state` instead.

3. **`frontend/dist/` must be committed** — it was removed from `.gitignore` in this session because Databricks bundle respects gitignore and was skipping the built assets. Do not add it back.

4. **Token fallback** — if `X-Forwarded-Access-Token` is None (local dev), the httpx call will fail. Add a guard: if no token, return empty list or raise 401.

5. **`logging.basicConfig(level=logging.INFO)`** was added for debugging — consider setting to WARNING for production.
