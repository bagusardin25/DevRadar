"""Admin allowlist admits verified emails only; the callback URL is configured."""

from __future__ import annotations

import pytest

from app.auth.google import HttpGoogleOAuthClient, assert_allowlisted
from app.config import Settings
from app.errors import ForbiddenError, ValidationError

ADMIN_SUB = "108234"
ADMIN_EMAIL = "admin@example.com"


def make_settings(**overrides: object) -> Settings:
    """Settings that ignore the developer's own .env.

    Every field these tests read is pinned, so a populated local
    ADMIN_GOOGLE_EMAILS or OAUTH_REDIRECT_BASE_URL cannot mask a regression.
    """
    base: dict[str, object] = {
        "app_env": "test",
        "api_base_path": "/api/v1",
        "frontend_url": "http://localhost:5173",
        "google_client_id": "test-client",
        "google_client_secret": "test-secret",
        "admin_google_emails": [],
        "oauth_redirect_base_url": "",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


class TestAllowlistEmailOnly:
    def test_verified_allowlisted_email_is_admitted(self) -> None:
        settings = make_settings(admin_google_emails=[ADMIN_EMAIL])
        assert_allowlisted(ADMIN_EMAIL, True, settings)

    def test_match_is_case_insensitive(self) -> None:
        settings = make_settings(admin_google_emails=["Admin@Example.com"])
        assert settings.admin_google_emails == [ADMIN_EMAIL]
        assert_allowlisted("ADMIN@example.com", True, settings)

    def test_unverified_email_is_rejected(self) -> None:
        settings = make_settings(admin_google_emails=[ADMIN_EMAIL])
        with pytest.raises(ForbiddenError):
            assert_allowlisted(ADMIN_EMAIL, False, settings)

    def test_outsider_is_rejected(self) -> None:
        settings = make_settings(admin_google_emails=[ADMIN_EMAIL])
        with pytest.raises(ForbiddenError):
            assert_allowlisted("intruder@example.com", True, settings)

    def test_empty_allowlist_is_rejected(self) -> None:
        with pytest.raises(ForbiddenError):
            assert_allowlisted(ADMIN_EMAIL, True, make_settings())

    def test_malformed_entry_is_dropped(self) -> None:
        settings = make_settings(admin_google_emails=["not-an-email", ADMIN_EMAIL])
        assert settings.admin_google_emails == [ADMIN_EMAIL]

    def test_dropped_entry_is_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("WARNING", logger="app.config"):
            make_settings(admin_google_emails=["not-an-email"])
        assert "not-an-email" in caplog.text

    @pytest.mark.parametrize(
        "value",
        ["admin@example.com,other@team.com", '["admin@example.com", "other@team.com"]'],
    )
    def test_env_string_forms_parse(self, value: str) -> None:
        assert make_settings(admin_google_emails=value).admin_google_emails == [
            ADMIN_EMAIL,
            "other@team.com",
        ]


class TestRedirectUri:
    def test_defaults_to_local_api_in_development(self) -> None:
        client = HttpGoogleOAuthClient(make_settings(app_env="development"))
        assert (
            client._redirect_uri()
            == "http://localhost:8000/api/v1/admin/auth/google/callback"
        )

    @pytest.mark.parametrize(
        "configured",
        ["https://api.example.com", "https://api.example.com/", " https://api.example.com "],
    )
    def test_configured_origin_wins(self, configured: str) -> None:
        client = HttpGoogleOAuthClient(
            make_settings(app_env="production", oauth_redirect_base_url=configured)
        )
        assert (
            client._redirect_uri()
            == "https://api.example.com/api/v1/admin/auth/google/callback"
        )

    def test_production_without_base_url_is_rejected(self) -> None:
        client = HttpGoogleOAuthClient(make_settings(app_env="production"))
        with pytest.raises(ValidationError):
            client._redirect_uri()

    def test_origin_without_scheme_is_rejected(self) -> None:
        client = HttpGoogleOAuthClient(make_settings(oauth_redirect_base_url="api.example.com"))
        with pytest.raises(ValidationError):
            client._redirect_uri()

    def test_custom_api_base_path_is_honoured(self) -> None:
        client = HttpGoogleOAuthClient(
            make_settings(
                api_base_path="/api/v2/",
                oauth_redirect_base_url="https://api.example.com",
            )
        )
        assert (
            client._redirect_uri()
            == "https://api.example.com/api/v2/admin/auth/google/callback"
        )


class TestAuthorizeUrl:
    async def test_authorize_url_carries_configured_callback(self) -> None:
        client = HttpGoogleOAuthClient(
            make_settings(oauth_redirect_base_url="https://api.example.com")
        )
        url = await client.build_authorize_url("st4te", "ch4llenge")
        assert "redirect_uri=https%3A%2F%2Fapi.example.com%2Fapi%2Fv1" in url
        assert "code_challenge_method=S256" in url
        assert "response_type=code" in url
        assert "scope=openid" in url

    async def test_missing_client_id_is_rejected(self) -> None:
        client = HttpGoogleOAuthClient(make_settings(google_client_id=""))
        with pytest.raises(ValidationError):
            await client.build_authorize_url("st4te", "ch4llenge")
