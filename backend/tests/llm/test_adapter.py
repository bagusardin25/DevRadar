"""OpenAI-compatible adapter: request shaping and response normalisation."""

from __future__ import annotations

import httpx
import pytest

from app.llm.adapter import ChatRequest, build_headers, build_payload, complete
from app.llm.errors import ProviderHTTPError, ProviderResponseError
from tests.llm.conftest import RecordingTransport, error_response, make_spec, ok_response

REQUEST = ChatRequest(operation="extraction", system="be terse", user="page text")
TIMEOUT = httpx.Timeout(30.0, connect=5.0)


class TestPayloadShaping:
    def test_carries_model_messages_and_output_cap(self) -> None:
        payload = build_payload(make_spec("groq"), REQUEST, json_mode="json_object")
        assert payload["model"] == "test-model"
        assert [m["role"] for m in payload["messages"]] == ["system", "user"]
        assert payload["max_tokens"] > 0

    def test_json_object_mode(self) -> None:
        payload = build_payload(make_spec("mistral"), REQUEST, json_mode="json_object")
        assert payload["response_format"] == {"type": "json_object"}

    def test_json_schema_mode_sends_a_strict_schema(self) -> None:
        request = ChatRequest(
            operation="extraction",
            system="s",
            user="u",
            schema_name="devradar_extraction",
            json_schema={"type": "object", "properties": {}},
        )
        payload = build_payload(make_spec("groq"), request, json_mode="json_schema")
        assert payload["response_format"]["type"] == "json_schema"
        assert payload["response_format"]["json_schema"]["strict"] is True
        assert payload["response_format"]["json_schema"]["name"] == "devradar_extraction"

    def test_json_schema_mode_without_a_schema_degrades_to_json_object(self) -> None:
        # DevRadar's extraction fields are all optional, which strict schema
        # mode cannot express, so no schema is supplied.
        payload = build_payload(make_spec("groq"), REQUEST, json_mode="json_schema")
        assert payload["response_format"] == {"type": "json_object"}

    def test_prompt_mode_sends_no_response_format(self) -> None:
        payload = build_payload(make_spec("cloudflare"), REQUEST, json_mode="prompt")
        assert "response_format" not in payload

    def test_temperature_is_omitted_where_unsupported(self) -> None:
        # The gpt-oss models Groq and Cerebras serve reject temperature.
        assert "temperature" not in build_payload(
            make_spec("groq"), REQUEST, json_mode="json_object"
        )
        assert build_payload(make_spec("openai"), REQUEST, json_mode="json_object")[
            "temperature"
        ] == 0


class TestHeaders:
    def test_bearer_auth(self) -> None:
        headers = build_headers(make_spec("groq"))
        assert headers["Authorization"] == "Bearer key-groq"

    def test_provider_specific_headers_are_added(self) -> None:
        headers = build_headers(make_spec("openrouter"))
        assert headers["X-Title"] == "DevRadar"


class TestResponseHandling:
    async def test_successful_completion(self) -> None:
        transport = RecordingTransport({"groq": ok_response('{"title": "Hi"}')})
        async with transport.client() as client:
            result = await complete(
                client, make_spec("groq"), REQUEST, json_mode="json_object", timeout=TIMEOUT
            )
        assert result.content == '{"title": "Hi"}'
        assert result.raw["usage"]["total_tokens"] == 120

    async def test_truncated_completion_is_a_failure(self) -> None:
        # Truncated JSON can still parse while silently losing fields.
        truncated = httpx.Response(
            200,
            json={
                "model": "test-model",
                "choices": [
                    {"finish_reason": "length", "message": {"content": '{"title": "Hi'}}
                ],
            },
        )
        transport = RecordingTransport({"groq": truncated})
        async with transport.client() as client:
            with pytest.raises(ProviderResponseError, match="truncated"):
                await complete(
                    client, make_spec("groq"), REQUEST, json_mode="json_object", timeout=TIMEOUT
                )

    async def test_empty_content_is_a_failure(self) -> None:
        empty = httpx.Response(
            200,
            json={"choices": [{"finish_reason": "stop", "message": {"content": "  "}}]},
        )
        transport = RecordingTransport({"groq": empty})
        async with transport.client() as client:
            with pytest.raises(ProviderResponseError, match="empty completion"):
                await complete(
                    client, make_spec("groq"), REQUEST, json_mode="json_object", timeout=TIMEOUT
                )

    async def test_missing_choices_is_a_failure(self) -> None:
        transport = RecordingTransport({"groq": httpx.Response(200, json={"choices": []})})
        async with transport.client() as client:
            with pytest.raises(ProviderResponseError, match="no choices"):
                await complete(
                    client, make_spec("groq"), REQUEST, json_mode="json_object", timeout=TIMEOUT
                )


class TestErrorExtraction:
    async def test_code_message_and_retry_after_are_surfaced(self) -> None:
        transport = RecordingTransport(
            {
                "openai": error_response(
                    429, code="insufficient_quota", message="no budget", retry_after=42
                )
            }
        )
        async with transport.client() as client:
            with pytest.raises(ProviderHTTPError) as excinfo:
                await complete(
                    client,
                    make_spec("openai"),
                    REQUEST,
                    json_mode="json_object",
                    timeout=TIMEOUT,
                )

        error = excinfo.value
        assert error.status == 429
        assert error.code == "insufficient_quota"
        assert error.message == "no budget"
        assert error.retry_after == 42

    async def test_gemini_style_status_field_is_read_as_the_code(self) -> None:
        response = httpx.Response(
            429, json={"error": {"status": "RESOURCE_EXHAUSTED", "message": "slow down"}}
        )
        transport = RecordingTransport({"gemini": response})
        async with transport.client() as client:
            with pytest.raises(ProviderHTTPError) as excinfo:
                await complete(
                    client,
                    make_spec("gemini"),
                    REQUEST,
                    json_mode="json_object",
                    timeout=TIMEOUT,
                )
        assert excinfo.value.code == "RESOURCE_EXHAUSTED"

    async def test_non_json_error_body_still_classifies(self) -> None:
        transport = RecordingTransport({"groq": httpx.Response(502, text="bad gateway")})
        async with transport.client() as client:
            with pytest.raises(ProviderHTTPError) as excinfo:
                await complete(
                    client, make_spec("groq"), REQUEST, json_mode="json_object", timeout=TIMEOUT
                )
        assert excinfo.value.status == 502

    async def test_http_date_retry_after_is_ignored_not_guessed(self) -> None:
        response = httpx.Response(
            429,
            json={"error": {"code": "rate_limit_exceeded"}},
            headers={"Retry-After": "Wed, 29 Jul 2026 12:00:00 GMT"},
        )
        transport = RecordingTransport({"groq": response})
        async with transport.client() as client:
            with pytest.raises(ProviderHTTPError) as excinfo:
                await complete(
                    client, make_spec("groq"), REQUEST, json_mode="json_object", timeout=TIMEOUT
                )
        assert excinfo.value.retry_after is None
