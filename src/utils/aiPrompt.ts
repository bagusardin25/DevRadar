import type { Hackathon, AIDeal } from '../types';
import { formatPrizePool } from './formatPrize';

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return 'TBA';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'TBA';
  return d.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function bulletList(items: string[], fallback: string): string {
  if (!items.length) return `- ${fallback}`;
  return items.map((r) => `- ${r}`).join('\n');
}

/**
 * Ready-to-paste execution & brainstorming prompt for AI coding assistants
 * (Cursor, Claude, ChatGPT, Antigravity, etc.).
 */
export function generateAIPrompt(item: Hackathon | AIDeal): string {
  const isHackathon = 'prizeValue' in item;
  return isHackathon
    ? buildHackathonPrompt(item as Hackathon)
    : buildAIDealPrompt(item as AIDeal);
}

function buildHackathonPrompt(h: Hackathon): string {
  const regDate = fmtDate(h.registrationDeadline);
  const subDate = fmtDate(h.submissionDeadline);
  const stackStr =
    h.technologies.length > 0 ? h.technologies.join(', ') : 'Open stack (web / AI / general)';
  const prize = formatPrizePool(h);
  const prizeCompact = formatPrizePool(h, { compact: true });
  const highlights = bulletList(h.suitableReasons, 'Verified hackathon opportunity');
  const eligibility =
    h.eligibility.length > 0 ? h.eligibility.join(', ') : 'See official rules';
  const regions =
    h.eligibleCountries.length > 0 ? h.eligibleCountries.join(', ') : 'See official rules';
  const effort = h.effortEstimate || 'TBA';
  const mode = (h.mode || 'online').replace(/_/g, ' ').toUpperCase();

  return `You are an expert software architect and hackathon strategy mentor.
I am building a submission for the hackathon below. Help me brainstorm, architect, and ship a winning MVP.

==============================================================
1. BRIEF DETAILS (from DevRadar)
==============================================================
- Title: ${h.title}
- Organizer: ${h.organizer}
- Prize pool: ${prize}
- Mode: ${mode}${h.location ? ` · ${h.location}` : ''}
- Registration deadline: ${regDate}
- Submission deadline: ${subDate}
- Team size: ${h.teamMin}–${h.teamMax}
- Effort estimate: ${effort}
- Eligibility: ${eligibility}
- Regions: ${regions}
- Tech stack / themes: ${stackStr}
- Official URL: ${h.officialUrl}

Description:
${(h.description || '').trim() || '(No description provided — infer from title, stack, and official URL.)'}

Key highlights & judging-oriented signals:
${highlights}

==============================================================
2. YOUR TASKS (answer in order)
==============================================================

A. Three high-impact project ideas
Propose exactly 3 creative but shippable project concepts that:
- Fit the stack/themes: ${stackStr}
- Align with likely judge criteria and the prize framing (${prizeCompact})
- Are feasible for a team of ${h.teamMin}–${h.teamMax} before ${subDate}
For each idea include: one-line pitch, target user, why judges care, and risk level (low/med/high).

B. Architecture recommendation
For the best of the 3 ideas (or the one I pick next):
- Recommended monorepo / app folder structure
- Frontend + backend choices that match the stack
- External APIs / SDKs to integrate
- Database schema (tables or document models) for the MVP
- Auth, secrets, and deploy target (Vercel/Railway/etc.) if relevant

C. MVP execution timeline
Work backwards from submission deadline ${subDate} (registration closes ${regDate}).
Break work into day-by-day or phase milestones:
1. Scope freeze & repo bootstrap
2. Core happy-path feature
3. Data / API integration
4. Polish, edge cases, tests
5. Buffer for demo recording
Call out what to cut if behind schedule.

D. Demo & pitch strategy
- README structure (problem → solution → architecture diagram → setup → demo)
- 60–90s demo video script (scenes + voiceover beats)
- Live-demo fail-safes (seeded data, offline fallback)
- What to emphasize for judges vs. what to hide as incomplete

Let's begin with section A (3 project ideas).`;
}

function buildAIDealPrompt(d: AIDeal): string {
  const tagsStr = d.tags.length > 0 ? d.tags.join(', ') : 'AI / API';
  const targets =
    d.targetUsers.length > 0 ? d.targetUsers.join(', ') : 'Developers / builders';
  const regions =
    d.supportedRegions.length > 0 ? d.supportedRegions.join(', ') : 'See terms';
  const expires = d.expiresAt ? fmtDate(d.expiresAt) : 'No fixed expiry listed';
  const starts = fmtDate(d.startsAt);
  const offerType = (d.offerType || '').replace(/_/g, ' ').toUpperCase();
  const requirements = bulletList(d.requirements, 'Standard developer offer terms');
  const highlights = bulletList(d.suitableReasons, 'Active AI product / credits offer');

  return `You are an AI developer and cloud architecture consultant.
I am claiming the AI deal / grant below and want a concrete build plan that maximizes its value.

==============================================================
1. BRIEF DETAILS (from DevRadar)
==============================================================
- Product: ${d.productName}
- Provider: ${d.provider}
- Offer type: ${offerType}
- Offer value: ${d.offerValue}
- Target users: ${targets}
- Supported regions: ${regions}
- Starts: ${starts}
- Expires / use-by: ${expires}
- Tags / stack cues: ${tagsStr}
- Claim URL: ${d.claimUrl}
- Official terms: ${d.officialTermsUrl}

Description:
${(d.description || '').trim() || '(No description provided — use product name, provider, and terms URL.)'}

Requirements:
${requirements}

Key highlights:
${highlights}

==============================================================
2. YOUR TASKS (answer in order)
==============================================================

A. Three high-impact project ideas
Propose exactly 3 practical apps or integrations that:
- Use ${d.provider} / ${d.productName} as a core capability
- Fit tags: ${tagsStr}
- Deliver clear demo value within a short build window
- Stay inside typical free-tier / credit limits when possible (${d.offerValue})
For each idea: pitch, who it's for, why this offer is a good fit, and estimated credits burn.

B. Architecture & integration
For the strongest idea:
- Suggested repo / file structure (prefer TypeScript)
- How to integrate the provider API securely (env vars, server-side only keys)
- Minimal data model / DB schema if persistence is needed
- Error handling, rate limits, and fallbacks
- Local dev + production deploy notes

C. Execution timeline (MVP)
Plan phases from claim → first demo, with a hard stop before ${expires}:
1. Account / API key setup & smoke test
2. Scaffold app + auth (if needed)
3. Core feature using the offer
4. Cost controls & observability
5. Demo polish
Include a "if credits run low" contingency.

D. Demo & pitch strategy
- README: setup, what the offer unlocks, architecture, cost notes
- Short demo script showing the AI capability clearly
- How to present ROI of the free credits / free tier to a technical audience

Let's begin with section A (3 project ideas).`;
}

/** True when item looks like a catalogue hackathon row. */
export function isHackathonItem(item: Hackathon | AIDeal): item is Hackathon {
  return 'prizeValue' in item;
}
