# 🛰️ DevRadar — Developer Opportunity Intelligence Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg)](LICENSE)
[![React](https://img.shields.io/badge/React-19-sky.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-blue.svg)](https://www.typescriptlang.org/)
[![Tailwind CSS v4](https://img.shields.io/badge/Tailwind_CSS-v4-purple.svg)](https://tailwindcss.com/)
[![No Login Required](https://img.shields.io/badge/Auth-No_Login_Required-emerald.svg)](#-key-principles)
[![No API Key Needed](https://img.shields.io/badge/API-No_User_API_Key-sky.svg)](#-key-principles)

**DevRadar** is an **100% Open-Source, Friction-Free Opportunity Intelligence Platform** for developers, hackathon champions, and AI builders. It aggregate and strictly verifies developer bounties, online hackathons, free AI API credits, student programs, and open model price drops.

---

## ⚡ Key Principles

- 🔓 **100% Open Source (MIT License)**: Zero paywalls, community-driven database schema and ingestion rules.
- 🚀 **No Login Required**: Zero friction. Open the website, search, filter, audit, compare, and claim opportunities immediately. All bookmarks and preferences are saved locally in your browser (`localStorage`).
- 🔑 **No User API Key Needed**: Users do not need to provide OpenAI, Anthropic, or X API keys to use the web application. All data is publicly indexed and served through multi-tier verification pipelines.

---

## 🚀 Modules & Features

1. 🛰️ **Hackathon Radar**: Search & discover online hackathons, developer bounties, and global coding competitions.
2. ⚡ **AI Deal Radar**: Discover free API credits (e.g. $100 Anthropic Claude), permanent free tiers (Vercel AI SDK 1M tokens), student developer packs (GitHub Student Pack), and LLM price drops (DeepSeek-R1 -80%).
3. 🛡️ **Provenance & Verification Audit**: Multi-tier trust scoring (Tier 1 Official Site, Tier 2 Aggregator, Tier 3 X Signal) with weighted confidence scorecards (35% status/deadline, 25% keywords, 20% tier, 15% freshness, 5% completeness).
4. ⚙️ **Pipeline Atlas**: Interactive visualizer for the 9-step data ingestion flow (*Scheduler → Fetcher → Storage → Parser → LLM → Normalizer → Deduplicator → Verifier → PostgreSQL*).
5. 📋 **Admin & Review Queue**: Human-in-the-loop dashboard to review raw X signals and candidate URLs.
6. 🧩 **Chrome Extension Side Panel Simulator**: Chrome Side Panel API helper preview for analyzing active browser tabs, extracting DOM deadlines, and exporting to Google Calendar / iCal.
7. 📊 **Side-by-Side Comparison Tool**: Compare up to 3 hackathons side-by-side on prize pools, effort estimates, and deadlines.

---

## 🛠️ Quickstart / Local Setup

Clone the repository and run the development server locally:

```bash
# 1. Clone the repository
git clone https://github.com/your-username/DevRadar.git
cd DevRadar

# 2. Install dependencies
npm install

# 3. Start the Vite dev server
npm run dev

# 4. Open in browser
# http://localhost:5173/
```

### Production Build

```bash
npm run build
```

---

## 🤝 Contributing & Submitting Opportunities

DevRadar is open for community contributions! You can submit missing hackathons or AI deals in two ways:

1. **In-App Submission**: Use the **"Submit"** button on the web app to submit candidate URLs directly to the verification review queue.
2. **Pull Request**: Add your opportunity directly to `src/data/mockData.ts` and send a PR.

---

## 📜 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.
