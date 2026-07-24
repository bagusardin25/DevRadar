"""Patch seed_listings.json with complete prize labels for all hackathons."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "manual-collection" / "seed_listings.json"

# Explicit human-readable prize copy (shown in UI). Numeric prize_value still used for filters/totals.
LABELS: dict[str, dict] = {
    "ai-factory-nativebuilder-2026": {
        "prize_value": 0,
        "prize_currency": "USD",
        "prize_label": "TBA · free entry + platform credits",
    },
    "knotic-amd-ai-hackathon-2026": {
        "prize_value": 30000,
        "prize_currency": "USD",
        "prize_label": "$30,000 + free AMD GPU access",
    },
    "victoria-vr-ai-builder-hackathon-2026": {
        "prize_value": 20000,
        "prize_currency": "EUR",
        "prize_label": "€20,000 prize pool",
    },
    "ai-builders-hackathon-osc-2026": {
        "prize_value": 4000,
        "prize_currency": "USD",
        "prize_label": "$4,000 Best SaaS product",
    },
    "future-caribbean-agentic-ai-buildathon-2026": {
        "prize_value": 70000,
        "prize_currency": "USD",
        "prize_label": "$70,000+ · top 40 get H200 GPU",
    },
    "elevate-women-global-hackathon-2026": {
        "prize_value": 0,
        "prize_currency": "USD",
        "prize_label": "Free · workshops + demo day",
    },
    "signoz-ai-agent-observability-hackathon": {
        "prize_value": 20000,
        "prize_currency": "USD",
        "prize_label": "$20,000+ · devices + interviews",
    },
    "openai-codex-namastedev-hackathon-2026": {
        "prize_value": 12000,
        "prize_currency": "USD",
        "prize_label": "₹10,00,000+ (~$12k USD)",
    },
    "techex-amsterdam-hackathon-2026": {
        "prize_value": 0,
        "prize_currency": "USD",
        "prize_label": "Prize TBA · hybrid expo event",
    },
    "ai-infra-summit-hackathon-2026": {
        "prize_value": 0,
        "prize_currency": "USD",
        "prize_label": "Prize TBA · hybrid summit",
    },
    "hackyard-virtual-ai-hackathon": {
        "prize_value": 0,
        "prize_currency": "USD",
        "prize_label": "Upcoming · prize TBA",
    },
    "prava-openai-visa-agentic-commerce-2026": {
        "prize_value": 70000,
        "prize_currency": "USD",
        "prize_label": "~$70,000 cash + OpenAI credits",
    },
    "videodb-global-online-hackathon-jul-2026": {
        "prize_value": 0,
        "prize_currency": "USD",
        "prize_label": "Prize TBA · see hackday.videodb.io",
    },
    "cruzhacks-google-gemma-summer-2026": {
        "prize_value": 0,
        "prize_currency": "USD",
        "prize_label": "Prize TBA · 1-day Gemma build",
    },
    "datahub-agent-hackathon-2026": {
        "prize_value": 20500,
        "prize_currency": "USD",
        "prize_label": "$20,500 across 4 tracks",
    },
    "gemini-xprize-build-2026": {
        "prize_value": 2000000,
        "prize_currency": "USD",
        "prize_label": "$2,000,000 prize pool",
    },
    "solana-summer-camp-2026": {
        "prize_value": 5000000,
        "prize_currency": "USD",
        "prize_label": "Up to $5M prizes + seed funding",
    },
    "sui-overflow-2026": {
        "prize_value": 500000,
        "prize_currency": "USD",
        "prize_label": "$500,000+ prize pool",
    },
    "fortyguard-hackathon-2026": {
        "prize_value": 6000,
        "prize_currency": "USD",
        "prize_label": "$6,000 prize pool",
    },
    "browserstack-ai-testing-bootcamp-hackathon-2026": {
        "prize_value": 1500,
        "prize_currency": "USD",
        "prize_label": "$1,500 prize pool",
    },
    "impact-forge-hs-virtual-2026": {
        "prize_value": 6000,
        "prize_currency": "USD",
        "prize_label": "$6,000 + research scholarships",
    },
    "indonesia-web3-hackathon-2026": {
        "prize_value": 5000,
        "prize_currency": "USD",
        "prize_label": "$5,000 · free & online",
    },
    "ibm-bob-devday-hackathon-2026": {
        "prize_value": 0,
        "prize_currency": "USD",
        "prize_label": "Free Dev Day · hack prize TBA",
    },
    "casper-agentic-buildathon-2026": {
        "prize_value": 150000,
        "prize_currency": "USD",
        "prize_label": "$150,000 prize pool",
    },
    "encode-commit-to-change-ai-agents-2026": {
        "prize_value": 30000,
        "prize_currency": "USD",
        "prize_label": "$30,000 + cloud credits",
    },
    "inco-network-hackathon-interest-2026": {
        "prize_value": 0,
        "prize_currency": "USD",
        "prize_label": "Prize TBA · interest registration",
    },
}


def main() -> None:
    data = json.loads(SEED.read_text(encoding="utf-8"))
    missing: list[str] = []
    for h in data.get("hackathons") or []:
        slug = h["slug"]
        patch = LABELS.get(slug)
        if not patch:
            missing.append(slug)
            # default label from numeric if present
            pv = float(h.get("prize_value") or 0)
            cur = h.get("prize_currency") or "USD"
            if pv > 0:
                h["prize_label"] = f"${pv:,.0f} {cur}" if cur == "USD" else f"{pv:,.0f} {cur}"
            else:
                h["prize_label"] = "Prize TBA"
            continue
        h.update(patch)
    SEED.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Patched {len(data.get('hackathons') or [])} hackathons")
    if missing:
        print("No explicit label map (auto-filled):", ", ".join(missing))


if __name__ == "__main__":
    main()
