"""Wave B seed quality: better official URLs, AI deal tags, honest status."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "manual-collection" / "seed_listings.json"

# Prefer official/event pages over social or bare hubs.
URL_FIXES: dict[str, str] = {
    # Keep social only if no better known; prefer organizer sites when available.
    "victoria-vr-ai-builder-hackathon-2026": "https://www.victoriavr.com/",
    "signoz-ai-agent-observability-hackathon": "https://signoz.io/blog/",
    "casper-agentic-buildathon-2026": "https://dorahacks.io/hackathon",
    "encode-commit-to-change-ai-agents-2026": "https://www.encode.club/hackathons",
    "future-caribbean-agentic-ai-buildathon-2026": "https://www.futurecaribbean.ai/",
    "fortyguard-hackathon-2026": "https://www.fortyguard.com/",
    "ai-builders-hackathon-osc-2026": "https://www.osc.community/",
    "elevate-women-global-hackathon-2026": "https://www.elevatewomen.co/",
    # Prava: still on Devfolio ecosystem — use hackathons search rather than bare root
    "prava-openai-visa-agentic-commerce-2026": "https://devfolio.co/hackathons",
}

# Status hints when we know events ended (relative to seed era July 2026).
STATUS_FIXES: dict[str, str] = {
    "openai-codex-namastedev-hackathon-2026": "registration_closed",
    "future-caribbean-agentic-ai-buildathon-2026": "registration_closed",
    "videodb-global-online-hackathon-jul-2026": "registration_closed",
    "cruzhacks-google-gemma-summer-2026": "registration_closed",
}

# Richer AI offer copy + tags for OSS usefulness.
OFFER_PATCHES: dict[str, dict] = {
    "google-ai-studio-free": {
        "offer_value": "Free Gemini access in AI Studio (rate limits apply; no paid plan required to start)",
        "tags": ["free", "gemini", "google", "ai-studio", "no-card"],
        "requirements": ["Google account"],
        "suitable_reasons": [
            "No paid plan required to start",
            "Official Google developer surface",
            "Good for prototypes & demos",
        ],
        "description": "Google AI Studio free tier for Gemini models — image/video/app experiments with daily/monthly rate limits. Always check current quotas on the official site.",
    },
    "huggingface-spaces-free": {
        "offer_value": "Free CPU Spaces + public model demos (GPU tiers paid)",
        "tags": ["free", "open-source", "spaces", "models", "hosting"],
        "requirements": ["Hugging Face account for deploy"],
        "suitable_reasons": [
            "Free public demos",
            "Strong open-source ecosystem",
            "Shareable Gradio/Streamlit apps",
        ],
    },
    "perplexity-ai-free-research": {
        "offer_value": "Free research queries; Pro features limited on free plan",
        "tags": ["free", "research", "search", "no-card"],
        "requirements": ["Email or Google signup"],
    },
    "deepseek-free-chat": {
        "offer_value": "Free chat + open-weight models (API limits change — verify)",
        "tags": ["free", "llm", "open-weights", "api"],
        "requirements": ["Account signup"],
    },
    "chatgpt-free-tier": {
        "offer_value": "Free ChatGPT plan with usage limits (Plus is paid)",
        "tags": ["free", "writing", "openai", "chat"],
        "requirements": ["Email or phone signup"],
    },
    "claude-ai-free-tier": {
        "offer_value": "Free Claude plan with daily message limits",
        "tags": ["free", "claude", "anthropic", "coding"],
        "requirements": ["Email signup", "Supported region"],
        "supported_regions": ["Supported Anthropic regions"],
    },
    "kivora-free-ai-suite": {
        "offer_value": "Claims free suite without card — verify on visit (third-party)",
        "tags": ["free", "chat", "image-gen", "study", "unverified-tier"],
        "confidence_score": 0.55,
        "status": "likely_active",
        "requirements": ["Browser access"],
        "suitable_reasons": [
            "Multi-tool free surface claimed",
            "Verify terms before relying on it",
        ],
    },
}

# Additional high-signal free AI offers for OSS demo catalogue.
EXTRA_OFFERS: list[dict] = [
    {
        "slug": "github-student-developer-pack",
        "title": "GitHub Student Developer Pack",
        "product_name": "GitHub Student Developer Pack",
        "provider": "GitHub",
        "description": "Free access to developer tools and cloud credits for verified students (Copilot Pro offer, Azure, DigitalOcean, and partner tools vary by year). Requires student verification.",
        "offer_type": "student_program",
        "offer_value": "Student tools + partner credits (varies; verify pack page)",
        "official_terms_url": "https://education.github.com/pack",
        "claim_url": "https://education.github.com/pack",
        "target_users": ["Student"],
        "requirements": ["Verified student status", "GitHub account"],
        "supported_regions": ["Worldwide (eligibility varies)"],
        "tags": ["student", "free", "github", "credits", "education"],
        "suitable_reasons": [
            "Best free stack for students",
            "Official GitHub Education program",
            "Often includes Copilot + cloud credits",
        ],
        "confidence_score": 0.94,
        "status": "verified_active",
        "expires_at": None,
        "x_posts": [],
    },
    {
        "slug": "vercel-ai-gateway-hobby",
        "title": "Vercel Hobby — AI / hosting free tier",
        "product_name": "Vercel Hobby",
        "provider": "Vercel",
        "description": "Hobby plan for deploying frontends and experimenting with AI SDK / edge functions within free quotas. Limits change — check pricing page.",
        "offer_type": "free_tier",
        "offer_value": "Hobby free tier (bandwidth & function limits apply)",
        "official_terms_url": "https://vercel.com/pricing",
        "claim_url": "https://vercel.com/signup",
        "target_users": ["Developer", "Student", "Indie hacker"],
        "requirements": ["GitHub/GitLab/Bitbucket or email"],
        "supported_regions": ["Worldwide"],
        "tags": ["free", "hosting", "vercel", "ai-sdk", "no-card"],
        "suitable_reasons": [
            "Ship demos without a card for hobby tier",
            "Common base for AI app prototypes",
        ],
        "confidence_score": 0.9,
        "status": "verified_active",
        "expires_at": None,
        "x_posts": [],
    },
    {
        "slug": "groq-free-developer-tier",
        "title": "GroqCloud free developer rate limits",
        "product_name": "GroqCloud",
        "provider": "Groq",
        "description": "Fast inference API with a free developer tier and rate limits. Ideal for low-latency LLM prototypes. Confirm current RPM/TPM on the console.",
        "offer_type": "free_tier",
        "offer_value": "Free tier rate limits (check console for current caps)",
        "official_terms_url": "https://console.groq.com/",
        "claim_url": "https://console.groq.com/",
        "target_users": ["Developer"],
        "requirements": ["Account signup"],
        "supported_regions": ["Worldwide (service availability may vary)"],
        "tags": ["free", "llm", "inference", "api", "speed"],
        "suitable_reasons": [
            "Fast free inference for demos",
            "Official developer console",
        ],
        "confidence_score": 0.88,
        "status": "verified_active",
        "expires_at": None,
        "x_posts": [],
    },
]


def main() -> None:
    data = json.loads(SEED.read_text(encoding="utf-8"))
    now = datetime.now(UTC)
    data.setdefault("meta", {})["wave_b_at"] = now.isoformat()
    data["meta"]["description"] = (
        data["meta"].get("description", "")
        + " Wave B: stronger official URLs, completeness-oriented AI offers, honest closed statuses."
    )

    for h in data.get("hackathons") or []:
        slug = h["slug"]
        if slug in URL_FIXES:
            h["official_url"] = URL_FIXES[slug]
        if slug in STATUS_FIXES:
            h["status"] = STATUS_FIXES[slug]
        # Ensure prize_label always present
        if not (h.get("prize_label") or "").strip():
            pv = float(h.get("prize_value") or 0)
            cur = h.get("prize_currency") or "USD"
            h["prize_label"] = (
                f"${pv:,.0f} {cur}" if pv > 0 and cur == "USD" else ("Prize TBA" if pv <= 0 else f"{pv:,.0f} {cur}")
            )

    existing_offer_slugs = {o["slug"] for o in data.get("ai_offers") or []}
    for o in data.get("ai_offers") or []:
        patch = OFFER_PATCHES.get(o["slug"])
        if patch:
            o.update(patch)

    for extra in EXTRA_OFFERS:
        if extra["slug"] not in existing_offer_slugs:
            data.setdefault("ai_offers", []).append(extra)
            existing_offer_slugs.add(extra["slug"])

    SEED.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wave B seed updated: {len(data.get('hackathons') or [])} hackathons, "
        f"{len(data.get('ai_offers') or [])} AI offers"
    )


if __name__ == "__main__":
    main()
