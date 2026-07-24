"""Refresh AI free-tier / promo catalogue from curated official sources (2026-07).

Sources used (verify on re-run):
- https://ai.google.dev/pricing — Gemini free tier (Flash models free of charge, rate-limited)
- https://console.groq.com/docs/rate-limits — free RPM/TPM on open models
- https://developers.cloudflare.com/workers-ai/platform/pricing/ — 10k Neurons/day free
- https://education.github.com/pack — Student pack (DigitalOcean $200 thru 7/31/26, Azure $100, etc.)
- https://huggingface.co/spaces — free CPU Spaces
- ChatGPT / Claude free consumer tiers (limits change; no fixed $ credits)

Does NOT include untrusted "claim free courses" spam or random API gateways.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "manual-collection" / "seed_listings.json"
CANDIDATES = ROOT / "data" / "manual-collection" / "candidates.jsonl"

# Full replacement set for AI offers — quality over quantity.
AI_OFFERS: list[dict] = [
    {
        "slug": "google-gemini-api-free-tier",
        "title": "Google Gemini API — Free tier (AI Studio)",
        "product_name": "Gemini API (Google AI Studio)",
        "provider": "Google",
        "description": (
            "Official free tier for the Gemini Developer API: free input/output tokens with "
            "rate limits. Flash-class models (e.g. Gemini 2.5/3.x Flash, Flash-Lite) are free "
            "of charge on the Free plan; some Pro/image models are paid-only. Free-tier content "
            "may be used to improve Google products — check terms. No credit card required to start."
        ),
        "offer_type": "free_tier",
        "offer_value": "Free tokens on Flash models · rate-limited (see AI Studio rate limits)",
        "official_terms_url": "https://ai.google.dev/gemini-api/terms",
        "claim_url": "https://aistudio.google.com/apikey",
        "target_users": ["Developer", "Student", "Researcher"],
        "requirements": ["Google account", "AI Studio / API key project"],
        "supported_regions": ["Supported Google AI regions"],
        "tags": ["free", "gemini", "google", "api", "no-card", "rate-limited"],
        "suitable_reasons": [
            "Best no-card developer API free tier among frontier providers",
            "Official pricing lists Free of charge for many Flash models",
            "AI Studio for quick experiments + API key for apps",
        ],
        "confidence_score": 0.95,
        "status": "verified_active",
        "expires_at": None,
        "x_posts": [
            {
                "post_id": "2080720988229206223",
                "post_url": "https://x.com/MadaoFCM/status/2080720988229206223",
                "author": "MadaoFCM",
            }
        ],
    },
    {
        "slug": "groqcloud-free-developer-limits",
        "title": "GroqCloud — Free developer rate limits",
        "product_name": "GroqCloud API",
        "provider": "Groq",
        "description": (
            "Fast inference API with free-tier rate limits at the organization level "
            "(RPM/RPD/TPM vary by model, e.g. llama-3.1-8b-instant and gpt-oss models). "
            "View exact limits in console settings. Free plan is suitable for prototypes; "
            "upgrade to Developer for higher limits / Batch / Flex."
        ),
        "offer_type": "free_tier",
        "offer_value": "Free RPM/TPM per model (e.g. 30 RPM class models) · check console Limits page",
        "official_terms_url": "https://console.groq.com/docs/rate-limits",
        "claim_url": "https://console.groq.com/",
        "target_users": ["Developer"],
        "requirements": ["GroqCloud account"],
        "supported_regions": ["Worldwide (service availability may vary)"],
        "tags": ["free", "llm", "inference", "api", "speed", "openai-compatible"],
        "suitable_reasons": [
            "Very low latency free inference for demos",
            "OpenAI-compatible API surface",
            "Official rate-limit docs (not marketing guesswork)",
        ],
        "confidence_score": 0.93,
        "status": "verified_active",
        "expires_at": None,
        "x_posts": [],
    },
    {
        "slug": "cloudflare-workers-ai-free",
        "title": "Cloudflare Workers AI — Free Neurons/day",
        "product_name": "Workers AI",
        "provider": "Cloudflare",
        "description": (
            "Workers AI is available on the Free plan with a daily free allocation of "
            "10,000 Neurons at no charge. Usage above that requires Workers Paid "
            "($0.011 per 1,000 Neurons beyond free allocation). Good for edge AI demos "
            "without a separate LLM vendor bill."
        ),
        "offer_type": "free_tier",
        "offer_value": "10,000 Neurons/day free on Workers Free plan",
        "official_terms_url": "https://developers.cloudflare.com/workers-ai/platform/pricing/",
        "claim_url": "https://dash.cloudflare.com/",
        "target_users": ["Developer"],
        "requirements": ["Cloudflare account"],
        "supported_regions": ["Worldwide"],
        "tags": ["free", "edge", "workers", "inference", "cloudflare"],
        "suitable_reasons": [
            "Documented free daily Neurons on official pricing page",
            "Pairs with free Workers request limits",
            "No separate AI vendor signup if you already use CF",
        ],
        "confidence_score": 0.94,
        "status": "verified_active",
        "expires_at": None,
        "x_posts": [],
    },
    {
        "slug": "github-student-developer-pack",
        "title": "GitHub Student Developer Pack",
        "product_name": "GitHub Student Developer Pack",
        "provider": "GitHub Education",
        "description": (
            "Verified students get free tools and partner credits via the Student Developer Pack. "
            "Notable AI-related pieces: GitHub Copilot Student plan (free for verified students; "
            "model picker simplified to Auto mode as of 2026), plus partner credits such as "
            "DigitalOcean $200 platform credit (GitHub pack promo ending 2026-07-31), "
            "Microsoft Azure free services + ~$100 credit, MongoDB Atlas credits, and more. "
            "Always re-check education.github.com/pack — partner offers rotate."
        ),
        "offer_type": "student_program",
        "offer_value": "Copilot Student + partner credits (DO $200 thru 2026-07-31 · Azure ~$100 · others)",
        "official_terms_url": "https://education.github.com/pack",
        "claim_url": "https://education.github.com/pack",
        "target_users": ["Student"],
        "requirements": ["Verified student status", "GitHub account"],
        "supported_regions": ["Worldwide (eligibility varies by school)"],
        "tags": ["student", "free", "github", "copilot", "credits", "education"],
        "suitable_reasons": [
            "Largest bundled free stack for students",
            "Official GitHub Education page is source of truth",
            "Includes AI coding assistant + cloud credits",
        ],
        "confidence_score": 0.94,
        "status": "verified_active",
        "expires_at": "2026-07-31T23:59:59+00:00",
        "x_posts": [
            {
                "post_id": "2032170602392666462",
                "post_url": "https://x.com/Sarthak4Alpha/status/2032170602392666462",
                "author": "Sarthak4Alpha",
            }
        ],
    },
    {
        "slug": "github-copilot-free",
        "title": "GitHub Copilot Free (non-student)",
        "product_name": "GitHub Copilot Free",
        "provider": "GitHub",
        "description": (
            "Copilot Free gives limited monthly AI completions for personal use without a paid plan. "
            "Students should prefer Copilot Student via the Student Pack. Limits and model routing "
            "change (Auto mode default). Not a replacement for full Pro."
        ),
        "offer_type": "free_tier",
        "offer_value": "Limited free monthly completions (see GitHub Copilot Free docs)",
        "official_terms_url": "https://docs.github.com/en/copilot/about-github-copilot/subscription-plans-for-github-copilot",
        "claim_url": "https://github.com/features/copilot",
        "target_users": ["Developer"],
        "requirements": ["GitHub account"],
        "supported_regions": ["Supported GitHub Copilot regions"],
        "tags": ["free", "copilot", "github", "coding", "ide"],
        "suitable_reasons": [
            "No-cost IDE AI for light use",
            "Official GitHub product",
        ],
        "confidence_score": 0.88,
        "status": "verified_active",
        "expires_at": None,
        "x_posts": [],
    },
    {
        "slug": "huggingface-spaces-free",
        "title": "Hugging Face Spaces — Free hosting for demos",
        "product_name": "Hugging Face Spaces",
        "provider": "Hugging Face",
        "description": (
            "Free CPU Spaces for public Gradio/Streamlit/Docker demos and access to free "
            "Inference API tiers / open models. GPU Spaces are paid. Ideal for portfolio demos "
            "and open-source model showcases."
        ),
        "offer_type": "free_tier",
        "offer_value": "Free CPU Spaces + free-tier inference (GPU paid)",
        "official_terms_url": "https://huggingface.co/docs/hub/spaces-overview",
        "claim_url": "https://huggingface.co/spaces",
        "target_users": ["Developer", "Researcher", "Student"],
        "requirements": ["Hugging Face account for deploy"],
        "supported_regions": ["Worldwide"],
        "tags": ["free", "open-source", "spaces", "hosting", "models"],
        "suitable_reasons": [
            "Ship public AI demos for free",
            "Huge open-model ecosystem",
        ],
        "confidence_score": 0.94,
        "status": "verified_active",
        "expires_at": None,
        "x_posts": [],
    },
    {
        "slug": "vercel-hobby-free",
        "title": "Vercel Hobby — Free deploy tier",
        "product_name": "Vercel Hobby",
        "provider": "Vercel",
        "description": (
            "Hobby plan for personal projects: free hosting with bandwidth/function limits. "
            "Common base for AI SDK / Next.js demos. Not unlimited — check current pricing. "
            "Students may get enhanced benefits via GitHub Student Pack (verify pack page)."
        ),
        "offer_type": "free_tier",
        "offer_value": "Hobby free tier (limits on bandwidth, serverless duration, etc.)",
        "official_terms_url": "https://vercel.com/pricing",
        "claim_url": "https://vercel.com/signup",
        "target_users": ["Developer", "Student", "Indie hacker"],
        "requirements": ["Git provider or email signup"],
        "supported_regions": ["Worldwide"],
        "tags": ["free", "hosting", "vercel", "ai-sdk", "no-card"],
        "suitable_reasons": [
            "Deploy frontends/AI apps without a card on Hobby",
            "Official pricing page is source of truth",
        ],
        "confidence_score": 0.91,
        "status": "verified_active",
        "expires_at": None,
        "x_posts": [],
    },
    {
        "slug": "chatgpt-free-tier",
        "title": "ChatGPT — Free consumer plan",
        "product_name": "ChatGPT Free",
        "provider": "OpenAI",
        "description": (
            "Consumer ChatGPT free plan remains available (limits and model access change). "
            "This is NOT free OpenAI Platform API credits for most new accounts — API usage "
            "typically requires prepaid billing. Free chat is for interactive use, not production APIs."
        ),
        "offer_type": "free_tier",
        "offer_value": "Free ChatGPT with usage/model limits (not Platform API free credits)",
        "official_terms_url": "https://openai.com/chatgpt/pricing/",
        "claim_url": "https://chatgpt.com/",
        "target_users": ["Everyone", "Student", "Creator"],
        "requirements": ["Email or phone signup"],
        "supported_regions": ["Supported OpenAI consumer regions"],
        "tags": ["free", "chat", "openai", "consumer"],
        "suitable_reasons": [
            "Zero-cost interactive AI",
            "Do not confuse with paid API platform",
        ],
        "confidence_score": 0.9,
        "status": "verified_active",
        "expires_at": None,
        "x_posts": [],
    },
    {
        "slug": "claude-ai-free-tier",
        "title": "Claude.ai — Free plan",
        "product_name": "Claude Free",
        "provider": "Anthropic",
        "description": (
            "Claude free plan for chat with daily message limits. Claude Pro/Team are paid. "
            "Anthropic API is billed separately (no ongoing free API tier for most developers). "
            "Check claude.com/pricing for current free vs paid differences."
        ),
        "offer_type": "free_tier",
        "offer_value": "Free Claude chat with daily limits (API is paid separately)",
        "official_terms_url": "https://claude.com/pricing",
        "claim_url": "https://claude.ai/",
        "target_users": ["Developer", "Student", "Writer"],
        "requirements": ["Email signup", "Supported region"],
        "supported_regions": ["Supported Anthropic regions"],
        "tags": ["free", "claude", "anthropic", "chat", "coding"],
        "suitable_reasons": [
            "Strong free coding/writing assistant",
            "Official consumer free plan",
        ],
        "confidence_score": 0.9,
        "status": "verified_active",
        "expires_at": None,
        "x_posts": [],
    },
    {
        "slug": "deepseek-free-chat-api",
        "title": "DeepSeek — Free chat & low-cost API",
        "product_name": "DeepSeek",
        "provider": "DeepSeek",
        "description": (
            "DeepSeek offers free web chat and a developer API with aggressive pricing "
            "(historically free credits or very low rates — always re-check platform.deepseek.com). "
            "Open-weight models also available for self-host. Treat limits as dynamic."
        ),
        "offer_type": "free_model",
        "offer_value": "Free chat · API pricing/limits verify on platform.deepseek.com",
        "official_terms_url": "https://platform.deepseek.com/",
        "claim_url": "https://www.deepseek.com/",
        "target_users": ["Developer", "Student"],
        "requirements": ["Account signup for API"],
        "supported_regions": ["Check DeepSeek availability"],
        "tags": ["free", "llm", "open-weights", "api", "low-cost"],
        "suitable_reasons": [
            "Popular free/cheap builder stack option",
            "Open weights for self-host alternative",
        ],
        "confidence_score": 0.82,
        "status": "likely_active",
        "expires_at": None,
        "x_posts": [],
    },
    {
        "slug": "perplexity-ai-free",
        "title": "Perplexity — Free research tier",
        "product_name": "Perplexity Free",
        "provider": "Perplexity AI",
        "description": (
            "Free AI research assistant with limited Pro features. Students sometimes get "
            "Perplexity Pro via education promos (verify independently). Free tier is suitable "
            "for search/research, not bulk API workloads."
        ),
        "offer_type": "free_tier",
        "offer_value": "Free research queries · Pro features limited",
        "official_terms_url": "https://www.perplexity.ai/",
        "claim_url": "https://www.perplexity.ai/",
        "target_users": ["Developer", "Student", "Researcher"],
        "requirements": ["Email or Google signup"],
        "supported_regions": ["Worldwide"],
        "tags": ["free", "research", "search", "no-card"],
        "suitable_reasons": [
            "Fast free research UX",
            "No install required",
        ],
        "confidence_score": 0.88,
        "status": "verified_active",
        "expires_at": None,
        "x_posts": [],
    },
    {
        "slug": "openai-researcher-access-credits",
        "title": "OpenAI Researcher Access Program (up to $1,000 API credits)",
        "product_name": "OpenAI API Researcher Access",
        "provider": "OpenAI",
        "description": (
            "Application-based program: researchers can apply for up to $1,000 OpenAI API credits "
            "valid 12 months for responsible AI / societal impact research. Not a general free tier "
            "for all developers — approval required. Platform API for others generally needs billing."
        ),
        "offer_type": "free_credits",
        "offer_value": "Up to $1,000 API credits (12 months) if approved",
        "official_terms_url": "https://openai.com/form/researcher-access-program/",
        "claim_url": "https://openai.smapply.org/prog/openai_researcher_access_program/",
        "target_users": ["Researcher"],
        "requirements": ["Research proposal", "Supported country for API"],
        "supported_regions": ["OpenAI API supported countries"],
        "tags": ["credits", "research", "openai", "api", "application"],
        "suitable_reasons": [
            "Documented official credit program",
            "Only path to meaningful free OpenAI API for research",
        ],
        "confidence_score": 0.92,
        "status": "verified_active",
        "expires_at": None,
        "x_posts": [],
    },
    {
        "slug": "oracle-cloud-free-tier",
        "title": "Oracle Cloud Free Tier (Always Free + trial)",
        "product_name": "Oracle Cloud Free Tier",
        "provider": "Oracle",
        "description": (
            "Always Free cloud resources plus a time-limited free trial with credits for new accounts "
            "(amounts change — check oracle.com/cloud/free). Useful for self-hosting open models "
            "and backends without immediate cost."
        ),
        "offer_type": "free_tier",
        "offer_value": "Always Free resources + trial credits (verify current amounts)",
        "official_terms_url": "https://www.oracle.com/cloud/free/",
        "claim_url": "https://www.oracle.com/cloud/free/",
        "target_users": ["Developer", "Student"],
        "requirements": ["Account + payment method often required for trial verification"],
        "supported_regions": ["Oracle Cloud regions"],
        "tags": ["free", "cloud", "self-host", "compute", "vm"],
        "suitable_reasons": [
            "Always Free compute for self-hosted LLMs",
            "Listed in common student/builder free stacks",
        ],
        "confidence_score": 0.86,
        "status": "verified_active",
        "expires_at": None,
        "x_posts": [],
    },
    {
        "slug": "kaggle-free-compute",
        "title": "Kaggle — Free notebooks & datasets",
        "product_name": "Kaggle Notebooks",
        "provider": "Google (Kaggle)",
        "description": (
            "Free hosted notebooks with weekly GPU/TPU quotas (limits reset weekly), free datasets, "
            "and Kaggle Learn micro-courses. Strong free path for ML experimentation without local GPUs."
        ),
        "offer_type": "free_tier",
        "offer_value": "Free notebooks + weekly accelerator quota (see Kaggle docs)",
        "official_terms_url": "https://www.kaggle.com/docs/notebooks",
        "claim_url": "https://www.kaggle.com/",
        "target_users": ["Student", "Researcher", "Developer"],
        "requirements": ["Kaggle / Google account", "Phone verification often required for GPU"],
        "supported_regions": ["Worldwide"],
        "tags": ["free", "gpu", "notebooks", "ml", "datasets", "education"],
        "suitable_reasons": [
            "Free GPU time for learning ML",
            "Huge public dataset library",
        ],
        "confidence_score": 0.91,
        "status": "verified_active",
        "expires_at": None,
        "x_posts": [],
    },
]


def main() -> None:
    data = json.loads(SEED.read_text(encoding="utf-8"))
    now = datetime.now(UTC)
    data.setdefault("meta", {})
    data["meta"]["ai_offers_refreshed_at"] = now.isoformat()
    data["meta"]["ai_offers_notes"] = (
        "Refreshed 2026-07-25 from official pricing/docs + curated X signals. "
        "Removed unverified third-party free sites. Prefer official URLs."
    )

    # Drop weak/untrusted prior offers (replaced by accurate set).
    removed = {"kivora-free-ai-suite", "google-ai-studio-free", "vercel-ai-gateway-hobby", "groq-free-developer-tier"}
    # Keep structure: replace entire ai_offers list
    old_slugs = {o["slug"] for o in data.get("ai_offers") or []}
    data["ai_offers"] = AI_OFFERS

    SEED.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Append discovery leads for provenance (no spam gateways).
    lines = [
        {
            "collected_at": now.isoformat(),
            "listing_kind": "ai_offer",
            "source": "official_docs+x_mcp",
            "post_url": "https://ai.google.dev/pricing",
            "post_id": "docs-gemini-pricing",
            "author": "google_ai",
            "official_url": "https://aistudio.google.com/apikey",
            "notes": "Gemini Free tier documented free of charge for Flash models",
            "status": "fetched",
        },
        {
            "collected_at": now.isoformat(),
            "listing_kind": "ai_offer",
            "source": "official_docs",
            "post_url": "https://developers.cloudflare.com/workers-ai/platform/pricing/",
            "post_id": "docs-cf-workers-ai",
            "author": "cloudflare",
            "official_url": "https://developers.cloudflare.com/workers-ai/platform/pricing/",
            "notes": "10,000 Neurons/day free",
            "status": "fetched",
        },
        {
            "collected_at": now.isoformat(),
            "listing_kind": "ai_offer",
            "source": "x_mcp",
            "post_url": "https://x.com/Sarthak4Alpha/status/2032170602392666462",
            "post_id": "2032170602392666462",
            "author": "Sarthak4Alpha",
            "official_url": "https://education.github.com/pack",
            "notes": "Student benefits 2026 list — verify each partner on GitHub pack page",
            "status": "pending_fetch",
        },
    ]
    with CANDIDATES.open("a", encoding="utf-8") as f:
        for row in lines:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Replaced AI offers: {len(old_slugs)} → {len(AI_OFFERS)}")
    print(f"Removed weak slugs (if present): {sorted(removed & old_slugs)}")
    for o in AI_OFFERS:
        print(f"  + {o['slug']} [{o['offer_type']}] {o['offer_value'][:60]}")


if __name__ == "__main__":
    main()
