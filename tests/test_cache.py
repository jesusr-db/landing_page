import time
import pytest
from backend.main import AppCache


def test_workspace_cache_miss_initially():
    cache = AppCache(ttl=300)
    assert cache.get_workspace() is None


def test_workspace_cache_hit_after_set():
    cache = AppCache(ttl=300)
    data = {"apps": ["app1"], "acls": {}}
    cache.set_workspace(data)
    assert cache.get_workspace() == data


def test_workspace_cache_expires_after_ttl():
    cache = AppCache(ttl=0.01)  # 10ms TTL
    cache.set_workspace({"apps": [], "acls": {}})
    assert cache.get_workspace() is not None
    time.sleep(0.15)
    assert cache.get_workspace() is None


def test_user_cache_miss_initially():
    cache = AppCache(ttl=300)
    assert cache.get_user("user@test.com") is None


def test_user_cache_hit_after_set():
    cache = AppCache(ttl=300)
    cache.set_workspace({"apps": [], "acls": {}})
    apps = [{"name": "app1"}]
    cache.set_user("user@test.com", apps)
    assert cache.get_user("user@test.com") == apps


def test_user_cache_cleared_when_workspace_refreshes():
    cache = AppCache(ttl=300)
    cache.set_workspace({"apps": [], "acls": {}})
    cache.set_user("user@test.com", [{"name": "app1"}])
    assert cache.get_user("user@test.com") is not None

    # Refresh workspace — must clear all user entries
    cache.set_workspace({"apps": [], "acls": {}})
    assert cache.get_user("user@test.com") is None


def test_user_cache_returns_none_after_workspace_expires():
    cache = AppCache(ttl=0.01)
    cache.set_workspace({"apps": [], "acls": {}})
    cache.set_user("user@test.com", [{"name": "app1"}])
    time.sleep(0.15)
    # Workspace expired, so user cache is stale too
    assert cache.get_user("user@test.com") is None


def test_workspace_valid_after_set():
    cache = AppCache(ttl=300)
    cache.set_workspace({"apps": [], "acls": {}})
    assert cache.workspace_valid() is True


def test_workspace_not_valid_initially():
    cache = AppCache(ttl=300)
    assert cache.workspace_valid() is False


def test_user_cache_miss_while_workspace_valid():
    """get_user returns None for unknown email when workspace is live — distinguishable from expiry via workspace_valid()."""
    cache = AppCache(ttl=300)
    cache.set_workspace({"apps": [], "acls": {}})
    assert cache.workspace_valid() is True
    assert cache.get_user("never-seen@test.com") is None


def test_set_user_ignored_after_workspace_expires():
    """set_user is a no-op when workspace has expired."""
    cache = AppCache(ttl=0.05)
    cache.set_workspace({"apps": [], "acls": {}})
    time.sleep(0.15)
    cache.set_user("user@test.com", [{"name": "app1"}])
    # Even after re-validating workspace, user entry should not persist
    cache.set_workspace({"apps": [], "acls": {}})
    assert cache.get_user("user@test.com") is None  # cleared by set_workspace


def test_set_workspace_twice_clears_users_and_returns_new_data():
    """Second set_workspace clears user entries AND the new workspace data is returned."""
    cache = AppCache(ttl=300)
    cache.set_workspace({"apps": ["app1"], "acls": {}})
    cache.set_user("user@test.com", [{"name": "app1"}])

    new_data = {"apps": ["app2"], "acls": {}}
    cache.set_workspace(new_data)

    assert cache.get_workspace() == new_data
    assert cache.get_user("user@test.com") is None
