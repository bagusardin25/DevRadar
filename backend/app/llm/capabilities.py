"""Per-provider quirks in the otherwise shared OpenAI chat-completions shape.

All six supported providers speak ``POST /chat/completions``. What differs is
small enough to express as flags instead of separate client classes: which
response_format they accept, whether temperature is allowed, and what extra
headers they want. Verified 2026-07-29 — see docs/LLM_MULTIPROVIDER_PLAN.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

JsonMode = Literal["json_schema", "json_object", "prompt"]

# Ordered strongest to weakest. A provider that rejects the mode it advertised
# is retried one step down rather than failed over: a 400 for an unsupported
# response_format is our request being wrong, not the provider being unhealthy.
_DOWNGRADE: dict[JsonMode, JsonMode | None] = {
    "json_schema": "json_object",
    "json_object": "prompt",
    "prompt": None,
}


@dataclass(frozen=True, slots=True)
class Capabilities:
    """What a provider's chat-completions endpoint accepts."""

    json_mode: JsonMode = "json_object"
    supports_temperature: bool = True
    extra_headers: dict[str, str] = field(default_factory=dict)


def downgrade(mode: JsonMode) -> JsonMode | None:
    """Next weaker JSON mode, or None when already at the weakest."""
    return _DOWNGRADE[mode]


# Defaults by provider name. A provider not listed here gets the conservative
# baseline (json_object + temperature), which every OpenAI-compatible endpoint
# in the plan supports.
_DEFAULTS: dict[str, Capabilities] = {
    "openai": Capabilities(json_mode="json_object"),
    # JSON Schema is supported on all actively served Gemini models. The
    # OpenAI-compatibility layer is still beta and silently drops unknown
    # parameters, so we send only the essentials.
    "gemini": Capabilities(json_mode="json_schema"),
    # Structured Outputs with strict schemas; the gpt-oss models reject
    # temperature, so leave it off for the whole provider rather than
    # tracking it per model.
    "groq": Capabilities(json_mode="json_schema", supports_temperature=False),
    "cerebras": Capabilities(json_mode="json_schema", supports_temperature=False),
    # Free models rotate and their schema support varies by upstream, so start
    # at json_object and let the downgrade path handle the rest. The headers
    # are optional attribution used by OpenRouter's ranking.
    "openrouter": Capabilities(
        json_mode="json_object",
        extra_headers={
            "HTTP-Referer": "https://github.com/bagusardin25/DevRadar",
            "X-Title": "DevRadar",
        },
    ),
    "mistral": Capabilities(json_mode="json_object"),
    # JSON mode is not documented on the Workers AI compatibility endpoint;
    # prompt-only keeps it usable until that is verified against a live key.
    "cloudflare": Capabilities(json_mode="prompt"),
}


def defaults_for(provider: str) -> Capabilities:
    """Known quirks for a provider name, or the conservative baseline."""
    return _DEFAULTS.get(provider.strip().lower(), Capabilities())
