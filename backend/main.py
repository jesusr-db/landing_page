import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import anyio
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


app = FastAPI()
_cache = AppCache(ttl=300)

DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "")
logger = logging.getLogger(__name__)


def _parse_category(description: str | None) -> str:
    if not description:
        return "General"
    match = re.match(r"^\[([^\]]+)\]", description)
    return match.group(1) if match else "General"


def _check_acl(entries: list, user_email: str, user_groups: list[str], levels: list[str]) -> bool:
    """Return True if any ACL entry grants one of `levels` to user or their groups."""
    for entry in entries:
        perm_levels = [p.permission_level for p in (entry.all_permissions or [])]
        if not any(lvl in levels for lvl in perm_levels):
            continue
        if entry.user_name == user_email:
            return True
        if entry.group_name == "users":
            return True
        if entry.group_name and entry.group_name in user_groups:
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
        perm_levels = [p.permission_level for p in (entry.all_permissions or [])]
        if "CAN_MANAGE" not in perm_levels:
            continue
        if entry.user_name == user_email:
            return True
        if entry.group_name and entry.group_name in user_groups:
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

    # Determine auth mode + init SDK
    w = WorkspaceClient(host=DATABRICKS_HOST, token=token if token else None)

    # Get user groups (OBO mode only)
    user_groups: list[str] = []
    if token:
        try:
            me = await anyio.to_thread.run_sync(w.current_user.me)
            user_groups = [g.display for g in (me.groups or []) if g.display]
        except Exception as exc:
            logger.warning("Failed to get user groups: %s", exc)

    # Fetch workspace-level raw data
    workspace_data = _cache.get_workspace()
    if workspace_data is None:
        all_apps = list(await anyio.to_thread.run_sync(lambda: list(w.apps.list())))

        raw_acls: dict[str, list] = {}
        raw_apps: list = []

        async def fetch_acl(app_obj):
            try:
                perms = await anyio.to_thread.run_sync(
                    lambda: w.apps.get_permissions(app_name=app_obj.name)
                )
                acl_entries = perms.access_control_list or []
                raw_apps.append(app_obj)
                raw_acls[app_obj.name] = acl_entries
            except Exception as exc:
                logger.warning("Failed to fetch permissions for %s: %s", app_obj.name, exc)

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
    _host = DATABRICKS_HOST.removeprefix("https://").removeprefix("http://").rstrip("/")
    filtered: list[dict] = []
    for app_obj in workspace_data["apps"]:
        if app_obj.name == portal_app_name:
            continue

        acl = workspace_data["acls"].get(app_obj.name, [])
        visible = _check_acl(acl, email, user_groups, ["CAN_USE", "CAN_MANAGE"])
        if not visible:
            continue

        manages = _check_can_manage(acl, email, user_groups)
        status = getattr(getattr(app_obj, "app_status", None), "state", "UNKNOWN")

        if status != "RUNNING" and not manages:
            continue

        filtered.append({
            "name": app_obj.name,
            "display_name": getattr(app_obj, "display_name", None) or app_obj.name.replace("-", " ").title(),
            "description": app_obj.description or "",
            "url": f"https://{_host}/apps/{app_obj.name}",
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
    token = request.headers.get("X-Forwarded-Access-Token")
    portal_title = os.environ.get("PORTAL_TITLE", "App Portal")

    groups: list[str] = []
    if token:
        try:
            w = WorkspaceClient(host=DATABRICKS_HOST, token=token)
            me = await anyio.to_thread.run_sync(w.current_user.me)
            groups = [g.display for g in (me.groups or []) if g.display]
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
