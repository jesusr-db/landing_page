import logging
import os
import re
import time
import types
from pathlib import Path
from typing import Any

import anyio
import httpx
from databricks.sdk import WorkspaceClient
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


class AppCache:
    """Two-tier cache: workspace-level raw data + user-level filtered results.

    User entries share the workspace expiry timestamp. When the workspace
    cache refreshes, all user entries are cleared so users never see data
    older than one workspace TTL window.
    """

    def __init__(self, ttl: int = 300):
        self._ttl = ttl
        self._workspace_data: dict[str, Any] | None = None
        self._workspace_expires: float = 0.0
        self._users: dict[str, list[dict]] = {}

    def get_workspace(self) -> dict[str, Any] | None:
        if time.monotonic() < self._workspace_expires and self._workspace_data is not None:
            return self._workspace_data
        return None

    def set_workspace(self, data: dict[str, Any]) -> None:
        self._workspace_expires = time.monotonic() + self._ttl
        self._workspace_data = data
        self._users.clear()  # Invalidate all user entries on workspace refresh

    def get_user(self, email: str) -> list[dict] | None:
        if time.monotonic() < self._workspace_expires:
            return self._users.get(email)
        return None

    def workspace_valid(self) -> bool:
        """Return True if workspace cache is currently live (not expired)."""
        return time.monotonic() < self._workspace_expires and self._workspace_data is not None

    def set_user(self, email: str, apps: list[dict]) -> None:
        if self.workspace_valid():  # Only store if workspace is still live
            self._users[email] = apps


logging.basicConfig(level=logging.INFO)
app = FastAPI()
_cache = AppCache(ttl=300)

DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "")
logger = logging.getLogger(__name__)


def _dict_to_ns(d: dict) -> types.SimpleNamespace:
    """Recursively convert a dict to a SimpleNamespace for attribute-style access."""
    return types.SimpleNamespace(**{
        k: [_dict_to_ns(i) if isinstance(i, dict) else i for i in v]
        if isinstance(v, list) else (_dict_to_ns(v) if isinstance(v, dict) else v)
        for k, v in d.items()
    })


async def _fetch_acl_obo(app_name: str, token: str, host: str) -> list:
    """Fetch app ACL using the user's OBO token via REST (avoids SP permission requirement)."""
    url = f"{host.rstrip('/')}/api/2.0/permissions/apps/{app_name}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()
        return [_dict_to_ns(e) for e in resp.json().get("access_control_list", [])]


def _parse_category(description: str | None) -> str:
    if not description:
        return "General"
    match = re.match(r"^\[([^\]]+)\]", description)
    return match.group(1) if match else "General"


def _check_acl(entries: list, user_email: str, user_groups: list[str], levels: list[str]) -> bool:
    """Return True if any ACL entry grants one of `levels` to user or their groups."""
    for entry in entries:
        perm_levels = [p.permission_level for p in (getattr(entry, "all_permissions", None) or [])]
        if not any(lvl in levels for lvl in perm_levels):
            continue
        if getattr(entry, "user_name", None) == user_email:
            return True
        if getattr(entry, "group_name", None) == "users":
            return True
        if getattr(entry, "group_name", None) and entry.group_name in user_groups:
            return True
    return False


def _check_can_manage(entries: list, user_email: str, user_groups: list[str]) -> bool:
    """Return True if user or any of their groups has CAN_MANAGE on this app.

    Intentionally does NOT short-circuit on the built-in "users" group — the all-users
    group grants CAN_USE visibility only, not CAN_MANAGE. This asymmetry with _check_acl
    is by design: any workspace user seeing an app is fine, but admin-level access
    (viewing non-RUNNING apps) requires an explicit CAN_MANAGE grant.
    """
    for entry in entries:
        perm_levels = [p.permission_level for p in (getattr(entry, "all_permissions", None) or [])]
        if "CAN_MANAGE" not in perm_levels:
            continue
        if getattr(entry, "user_name", None) == user_email:
            return True
        if getattr(entry, "group_name", None) and entry.group_name in user_groups:
            return True
    return False


@app.get("/api/apps")
async def get_apps(request: Request) -> list[dict]:
    email = request.headers.get("X-Forwarded-Email", "unknown@unknown.com")
    token = request.headers.get("X-Forwarded-Access-Token")
    portal_app_name = os.environ.get("PORTAL_APP_NAME", "app-portal")

    # Check user-level cache
    if _cache.workspace_valid():
        cached = _cache.get_user(email)
        if cached is not None:
            return cached

    # Use M2M auth (DATABRICKS_CLIENT_ID/SECRET from env in Apps runtime)
    # w.config.host resolves the actual host even when DATABRICKS_HOST env var is empty
    w = WorkspaceClient(host=DATABRICKS_HOST)
    resolved_host = w.config.host

    # Get user groups via SCIM lookup
    user_groups: list[str] = []
    try:
        users = list(await anyio.to_thread.run_sync(
            lambda: list(w.users.list(filter=f'userName eq "{email}"', attributes="groups"))
        ))
        if users:
            user_groups = [g.display for g in (users[0].groups or []) if g.display]
    except Exception as exc:
        logger.warning("Failed to get user groups: %s", exc)

    # Fetch workspace-level raw data
    workspace_data = _cache.get_workspace()
    if workspace_data is None:
        all_apps = list(await anyio.to_thread.run_sync(lambda: list(w.apps.list())))

        raw_acls: dict[str, list] = {}
        raw_apps: list = []

        # Synthetic ACL used when we can't read real permissions:
        # grants all workspace users CAN_USE so running apps are visible to everyone.
        _fallback_acl = [_dict_to_ns({
            "group_name": "users",
            "all_permissions": [{"permission_level": "CAN_USE"}],
        })]

        async def fetch_acl(app_obj):
            try:
                if token:
                    acl_entries = await _fetch_acl_obo(app_obj.name, token, resolved_host)
                else:
                    perms = await anyio.to_thread.run_sync(
                        lambda: w.apps.get_permissions(app_name=app_obj.name)
                    )
                    acl_entries = perms.access_control_list or []
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 403:
                    # Token lacks permissions scope — fall back to "users: CAN_USE"
                    acl_entries = _fallback_acl
                else:
                    logger.warning("Failed to fetch permissions for %s: %s", app_obj.name, exc)
                    return
            except Exception as exc:
                logger.warning("Failed to fetch permissions for %s: %s", app_obj.name, exc)
                return
            raw_apps.append(app_obj)
            raw_acls[app_obj.name] = acl_entries

        # Uses anyio task group instead of asyncio.gather(return_exceptions=True).
        # Per-app exception isolation is achieved by wrapping each fetch_acl call in
        # try/except internally, so failures never escape the task group scope.
        # Behavior is equivalent to asyncio.gather with return_exceptions=True,
        # and this approach works correctly on both asyncio and trio backends.
        async with anyio.create_task_group() as tg:
            for a in all_apps:
                tg.start_soon(fetch_acl, a)

        workspace_data = {"apps": raw_apps, "acls": raw_acls}
        _cache.set_workspace(workspace_data)

    # Build per-user filtered list
    _host = resolved_host.removeprefix("https://").removeprefix("http://").rstrip("/")
    filtered: list[dict] = []
    for app_obj in workspace_data["apps"]:
        if app_obj.name == portal_app_name:
            continue

        acl = workspace_data["acls"].get(app_obj.name, [])
        visible = _check_acl(acl, email, user_groups, ["CAN_USE", "CAN_MANAGE"])
        if not visible:
            continue

        manages = _check_can_manage(acl, email, user_groups)
        compute = getattr(app_obj, "compute_status", None)
        compute_state = getattr(compute, "state", None)
        _compute_state_str = compute_state.value if compute_state is not None else None
        _STATUS_MAP = {"ACTIVE": "RUNNING", "PENDING": "DEPLOYING", "ERROR": "CRASHED"}
        status = _STATUS_MAP.get(_compute_state_str, _compute_state_str or "UNKNOWN")


        filtered.append({
            "name": app_obj.name,
            "display_name": getattr(app_obj, "display_name", None) or app_obj.name.replace("-", " ").title(),
            "description": app_obj.description or "",
            "url": getattr(app_obj, "url", None) or f"https://{_host}/apps/{app_obj.name}",
            "status": status,
            "category": _parse_category(app_obj.description),
            "can_manage": manages,
        })

    _cache.set_user(email, filtered)
    return filtered


@app.get("/api/me")
async def get_me(request: Request) -> dict:
    email = request.headers.get("X-Forwarded-Email", "unknown@unknown.com")
    username = request.headers.get("X-Forwarded-Preferred-Username", email.split("@")[0])
    portal_title = os.environ.get("PORTAL_TITLE", "App Portal")

    groups: list[str] = []
    try:
        w = WorkspaceClient(host=DATABRICKS_HOST)
        users = list(await anyio.to_thread.run_sync(
            lambda: list(w.users.list(filter=f'userName eq "{email}"', attributes="groups"))
        ))
        if users:
            groups = [g.display for g in (users[0].groups or []) if g.display]
    except Exception as exc:
        logger.warning("Failed to get user groups: %s", exc)

    return {
        "email": email,
        "username": username,
        "groups": groups,
        "portal_title": portal_title,
    }


# ── Static file serving (production only) ──────────────────────────────────
# The Vite build output lives at frontend/dist/ relative to the project root.
# This block is only active when the dist directory exists (i.e., after `npm run build`).
# In local development, Vite serves the frontend separately.

_dist = Path(__file__).parent.parent / "frontend" / "dist"

if _dist.exists():
    _assets = _dist / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        return FileResponse(str(_dist / "index.html"))
