"""Admin allowlist accepts immutable IDs only; the callback URL is configured, not guessed."""

from __future__ import annotations

import pytest

from app.auth.github import HttpGitHubOAuthClient, assert_allowlisted
from app.config import Settings
from app.errors import ForbiddenError, ValidationError

ADMIN_ID = "12345678"
ADMIN_LOGIN = "some-admin"


def make_settings(**overrides: object) -> Settings:
    """Settings that ignore the developer's own .env.

    Every field these tests read is pinned, so a populated local ADMIN_GITHUB_IDS
    or OAUTH_REDIRECT_BASE_URL cannot mask a regression.
    """
    base: dict[str, object] = {
        "app_env": "test",
        "api_base_path": "/api/v1",
        "frontend_url": "http://localhost:5173",
        "github_client_id": "test-client",
        "github_client_secret": "test-secret",
        "admin_github_ids": [],
        "oauth_redirect_base_url": "",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


class TestAllowlistIsNumericOnly:
    def test_numeric_id_is_admitted(self) -> None:
        settings = make_settings(admin_github_ids=[ADMIN_ID])
        assert_allowlisted(ADMIN_ID, ADMIN_LOGIN, settings)

    def test_login_entry_does_not_grant_access(self) -> None:
        """A renamed account frees its handle, so logins must never authorise."""
        settings = make_settings(admin_github_ids=[ADMIN_LOGIN])
        assert settings.admin_github_ids == []
        with pytest.raises(ForbiddenError):
            assert_allowlisted(ADMIN_ID, ADMIN_LOGIN, settings)

    def test_login_is_dropped_but_numeric_sibling_survives(self) -> None:
        settings = make_settings(admin_github_ids=[ADMIN_ID, ADMIN_LOGIN])
        assert settings.admin_github_ids == [ADMIN_ID]
        assert_allowlisted(ADMIN_ID, ADMIN_LOGIN, settings)

    def test_dropped_login_is_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("WARNING", logger="app.config"):
            make_settings(admin_github_ids=[ADMIN_LOGIN])
        assert ADMIN_LOGIN in caplog.text

    @pytest.mark.parametrize("value", ["12345678,some-admin", '["12345678", "some-admin"]'])
    def test_filtering_applies_to_env_string_forms(self, value: str) -> None:
        assert make_settings(admin_github_ids=value).admin_github_ids == [ADMIN_ID]

    def test_non_ascii_digits_are_rejected(self) -> None:
        assert make_settings(admin_github_ids=["١٢٣"]).admin_github_ids == []

    def test_outsider_is_rejected(self) -> None:
        settings = make_settings(admin_github_ids=[ADMIN_ID])
        with pytest.raises(ForbiddenError):
            assert_allowlisted("999", "intruder", settings)

    def test_empty_allowlist_is_rejected(self) -> None:
        with pytest.raises(ForbiddenError):
            assert_allowlisted(ADMIN_ID, ADMIN_LOGIN, make_settings())


class TestRedirectUri:
    def test_defaults_to_local_api_in_development(self) -> None:
        client = HttpGitHubOAuthClient(make_settings(app_env="development"))
        assert client._redirect_uri() == "http://127.0.0.1:8000/api/v1/admin/auth/github/callback"

    @pytest.mark.parametrize(
        "configured",
        ["https://api.example.com", "https://api.example.com/", " https://api.example.com "],
    )
    def test_configured_origin_wins(self, configured: str) -> None:
        client = HttpGitHubOAuthClient(
            make_settings(app_env="production", oauth_redirect_base_url=configured)
        )
        assert client._redirect_uri() == "https://api.example.com/api/v1/admin/auth/github/callback"

    def test_frontend_origin_is_not_used_as_a_stand_in(self) -> None:
        """The old derivation rewrote FRONTEND_URL; a different API host broke it."""
        client = HttpGitHubOAuthClient(
            make_settings(
                app_env="production",
                frontend_url="https://devradar.app",
                oauth_redirect_base_url="https://api.devradar.app",
            )
        )
        assert client._redirect_uri().startswith("https://api.devradar.app/")

    def test_custom_api_base_path_is_honoured(self) -> None:
        client = HttpGitHubOAuthClient(
            make_settings(
                api_base_path="/api/v2/",
                oauth_redirect_base_url="https://api.example.com",
            )
        )
        assert client._redirect_uri() == "https://api.example.com/api/v2/admin/auth/github/callback"

    def test_production_without_base_url_is_rejected(self) -> None:
        client = HttpGitHubOAuthClient(make_settings(app_env="production"))
        with pytest.raises(ValidationError):
            client._redirect_uri()

    def test_origin_without_scheme_is_rejected(self) -> None:
        client = HttpGitHubOAuthClient(make_settings(oauth_redirect_base_url="api.example.com"))
        with pytest.raises(ValidationError):
            client._redirect_uri()


class TestAuthorizeUrl:
    async def test_authorize_url_carries_configured_callback(self) -> None:
        client = HttpGitHubOAuthClient(
            make_settings(oauth_redirect_base_url="https://api.example.com")
        )
        url = await client.build_authorize_url("st4te", "ch4llenge")
        assert "redirect_uri=https%3A%2F%2Fapi.example.com%2Fapi%2Fv1" in url
        assert "code_challenge_method=S256" in url

    async def test_missing_client_id_is_rejected(self) -> None:
        client = HttpGitHubOAuthClient(make_settings(github_client_id=""))
        with pytest.raises(ValidationError):
            await client.build_authorize_url("st4te", "ch4llenge")
