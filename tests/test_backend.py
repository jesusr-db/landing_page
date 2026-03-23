import pytest
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport
from backend.main import app

pytest_plugins = ('anyio',)

BASE_HEADERS = {
    "X-Forwarded-Email": "j.rodriguez@dominos.com",
    "X-Forwarded-Preferred-Username": "j.rodriguez",
}
TOKEN_HEADERS = {**BASE_HEADERS, "X-Forwarded-Access-Token": "fake-token"}


def _make_me(groups: list[str]):
    me = MagicMock()
    me.user_name = "j.rodriguez"
    me.groups = [MagicMock(display=g) for g in groups]
    return me


@pytest.mark.anyio
async def test_me_with_token_returns_groups():
    mock_me = _make_me(["data-platform", "admins"])
    with patch("backend.main.WorkspaceClient") as MockClient:
        MockClient.return_value.current_user.me.return_value = mock_me
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/me", headers=TOKEN_HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "j.rodriguez@dominos.com"
    assert data["username"] == "j.rodriguez"
    assert "data-platform" in data["groups"]
    assert "admins" in data["groups"]


@pytest.mark.anyio
async def test_me_without_token_returns_empty_groups():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/me", headers=BASE_HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "j.rodriguez@dominos.com"
    assert data["groups"] == []


@pytest.mark.anyio
async def test_me_includes_portal_title(monkeypatch):
    monkeypatch.setenv("PORTAL_TITLE", "Domino's App Portal")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/me", headers=BASE_HEADERS)

    assert resp.json()["portal_title"] == "Domino's App Portal"


@pytest.mark.anyio
async def test_me_portal_title_defaults_to_app_portal():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/me", headers=BASE_HEADERS)

    assert "portal_title" in resp.json()


@pytest.mark.anyio
async def test_me_sdk_error_returns_empty_groups():
    """If SDK call fails, degrade gracefully — return empty groups instead of 500."""
    with patch("backend.main.WorkspaceClient") as MockClient:
        MockClient.return_value.current_user.me.side_effect = Exception("SDK error")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/me", headers=TOKEN_HEADERS)

    assert resp.status_code == 200
    assert resp.json()["groups"] == []


from backend.main import _cache


def _make_app(name: str, status: str = "RUNNING", description: str = "") -> MagicMock:
    a = MagicMock()
    a.name = name
    a.description = description
    a.app_status = MagicMock()
    a.app_status.state = status
    return a


def _make_acl(user_name=None, group_name=None, level: str = "CAN_USE") -> MagicMock:
    entry = MagicMock()
    entry.user_name = user_name
    entry.group_name = group_name
    entry.all_permissions = [MagicMock(permission_level=level)]
    return entry


def _make_perms(entries: list) -> MagicMock:
    perms = MagicMock()
    perms.access_control_list = entries
    return perms


@pytest.fixture(autouse=True)
def clear_cache():
    _cache._workspace_data = None
    _cache._workspace_expires = 0.0
    _cache._users.clear()
    yield


@pytest.mark.anyio
async def test_apps_returns_only_permitted_apps():
    app1 = _make_app("sales-analytics")
    app2 = _make_app("ml-monitor")
    perms1 = _make_perms([_make_acl(user_name="j.rodriguez@dominos.com", level="CAN_USE")])
    perms2 = _make_perms([_make_acl(group_name="admins", level="CAN_USE")])

    with patch("backend.main.WorkspaceClient") as MockClient:
        instance = MockClient.return_value
        instance.apps.list.return_value = iter([app1, app2])
        instance.apps.get_permissions.side_effect = lambda app_name: (
            perms1 if app_name == "sales-analytics" else perms2
        )
        instance.current_user.me.return_value = _make_me([])

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/apps", headers=TOKEN_HEADERS)

    assert resp.status_code == 200
    names = [a["name"] for a in resp.json()]
    assert "sales-analytics" in names
    assert "ml-monitor" not in names  # user not in admins group


@pytest.mark.anyio
async def test_apps_excludes_portal_itself(monkeypatch):
    monkeypatch.setenv("PORTAL_APP_NAME", "app-portal")
    portal = _make_app("app-portal")
    other = _make_app("other-app")
    perms = _make_perms([_make_acl(group_name="users", level="CAN_USE")])

    with patch("backend.main.WorkspaceClient") as MockClient:
        instance = MockClient.return_value
        instance.apps.list.return_value = iter([portal, other])
        instance.apps.get_permissions.return_value = perms
        instance.current_user.me.return_value = _make_me([])

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/apps", headers=TOKEN_HEADERS)

    names = [a["name"] for a in resp.json()]
    assert "app-portal" not in names
    assert "other-app" in names


@pytest.mark.anyio
async def test_apps_all_users_group_shows_app():
    target = _make_app("public-app")
    perms = _make_perms([_make_acl(group_name="users", level="CAN_USE")])

    with patch("backend.main.WorkspaceClient") as MockClient:
        instance = MockClient.return_value
        instance.apps.list.return_value = iter([target])
        instance.apps.get_permissions.return_value = perms
        instance.current_user.me.return_value = _make_me([])

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/apps", headers=TOKEN_HEADERS)

    assert any(a["name"] == "public-app" for a in resp.json())


@pytest.mark.anyio
async def test_apps_non_running_hidden_from_can_use_user():
    deploying = _make_app("slow-app", status="DEPLOYING")
    perms = _make_perms([_make_acl(user_name="j.rodriguez@dominos.com", level="CAN_USE")])

    with patch("backend.main.WorkspaceClient") as MockClient:
        instance = MockClient.return_value
        instance.apps.list.return_value = iter([deploying])
        instance.apps.get_permissions.return_value = perms
        instance.current_user.me.return_value = _make_me([])

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/apps", headers=TOKEN_HEADERS)

    assert resp.json() == []


@pytest.mark.anyio
async def test_apps_non_running_visible_to_can_manage_user():
    deploying = _make_app("slow-app", status="DEPLOYING")
    perms = _make_perms([_make_acl(user_name="j.rodriguez@dominos.com", level="CAN_MANAGE")])

    with patch("backend.main.WorkspaceClient") as MockClient:
        instance = MockClient.return_value
        instance.apps.list.return_value = iter([deploying])
        instance.apps.get_permissions.return_value = perms
        instance.current_user.me.return_value = _make_me([])

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/apps", headers=TOKEN_HEADERS)

    assert len(resp.json()) == 1
    assert resp.json()[0]["status"] == "DEPLOYING"
    assert resp.json()[0]["can_manage"] is True


@pytest.mark.anyio
async def test_apps_category_parsed_from_description():
    a = _make_app("ops-app", description="[Operations] Real-time tracking")
    perms = _make_perms([_make_acl(group_name="users", level="CAN_USE")])

    with patch("backend.main.WorkspaceClient") as MockClient:
        instance = MockClient.return_value
        instance.apps.list.return_value = iter([a])
        instance.apps.get_permissions.return_value = perms
        instance.current_user.me.return_value = _make_me([])

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/apps", headers=TOKEN_HEADERS)

    assert resp.json()[0]["category"] == "Operations"


@pytest.mark.anyio
async def test_apps_failed_permission_check_excludes_app():
    good = _make_app("good-app")
    bad = _make_app("bad-app")
    good_perms = _make_perms([_make_acl(group_name="users", level="CAN_USE")])

    def side_effect(app_name):
        if app_name == "bad-app":
            raise RuntimeError("API error")
        return good_perms

    with patch("backend.main.WorkspaceClient") as MockClient:
        instance = MockClient.return_value
        instance.apps.list.return_value = iter([good, bad])
        instance.apps.get_permissions.side_effect = side_effect
        instance.current_user.me.return_value = _make_me([])

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/apps", headers=TOKEN_HEADERS)

    names = [a["name"] for a in resp.json()]
    assert "good-app" in names
    assert "bad-app" not in names


@pytest.mark.anyio
async def test_apps_sp_fallback_without_token():
    a = _make_app("public-app")
    perms = _make_perms([_make_acl(group_name="users", level="CAN_USE")])

    with patch("backend.main.WorkspaceClient") as MockClient:
        instance = MockClient.return_value
        instance.apps.list.return_value = iter([a])
        instance.apps.get_permissions.return_value = perms

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/apps", headers=BASE_HEADERS)  # No token

    assert any(a["name"] == "public-app" for a in resp.json())
    # SP fallback: current_user.me() should NOT have been called
    MockClient.return_value.current_user.me.assert_not_called()


@pytest.mark.anyio
async def test_apps_cache_hit_skips_sdk():
    """Second call with warm cache should not hit the SDK at all."""
    a = _make_app("cached-app")
    perms = _make_perms([_make_acl(group_name="users", level="CAN_USE")])

    with patch("backend.main.WorkspaceClient") as MockClient:
        instance = MockClient.return_value
        instance.apps.list.return_value = iter([a])
        instance.apps.get_permissions.return_value = perms
        instance.current_user.me.return_value = _make_me([])

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # First call — populates cache
            resp1 = await client.get("/api/apps", headers=TOKEN_HEADERS)
            # Second call — should hit user cache
            resp2 = await client.get("/api/apps", headers=TOKEN_HEADERS)

    assert resp1.json() == resp2.json()
    # SDK list should only have been called once
    assert MockClient.return_value.apps.list.call_count == 1


@pytest.mark.anyio
async def test_apps_can_manage_false_for_can_use_user():
    """User with only CAN_USE should have can_manage: false in response."""
    a = _make_app("viewer-app")
    perms = _make_perms([_make_acl(user_name="j.rodriguez@dominos.com", level="CAN_USE")])

    with patch("backend.main.WorkspaceClient") as MockClient:
        instance = MockClient.return_value
        instance.apps.list.return_value = iter([a])
        instance.apps.get_permissions.return_value = perms
        instance.current_user.me.return_value = _make_me([])

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/apps", headers=TOKEN_HEADERS)

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["can_manage"] is False


@pytest.mark.anyio
async def test_apps_sp_fallback_user_email_match():
    """SP fallback: user_name == email ACL entry grants visibility."""
    a = _make_app("direct-app")
    perms = _make_perms([_make_acl(user_name="j.rodriguez@dominos.com", level="CAN_USE")])

    with patch("backend.main.WorkspaceClient") as MockClient:
        instance = MockClient.return_value
        instance.apps.list.return_value = iter([a])
        instance.apps.get_permissions.return_value = perms

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/apps", headers=BASE_HEADERS)  # No token

    assert any(a["name"] == "direct-app" for a in resp.json())


@pytest.mark.anyio
async def test_spa_catchall_does_not_crash_without_dist():
    """When frontend/dist doesn't exist, non-API routes should not crash the server."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/some/spa/route")
    # Without dist dir, there's no catch-all route — 404 is fine, 500 is not
    assert resp.status_code != 500
