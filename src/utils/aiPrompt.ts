import type { AIDeal, Hackathon } from '../types';
import { formatPrizePool } from './formatPrize';
import { getDeadlineInfo } from './countdown';

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
 * Opening block that carries DevRadar's own caveats into the exported prompt.
 *
 * The modal footer already tells the reader the catalogue is an index rather
 * than the source, and that details may be stale. Without repeating it here
 * that warning is lost the moment the prompt is copied, and the assistant plans
 * against unverified dates and prizes as if they were confirmed.
 *
 * `sourceNoun` names who actually published the listing — a hackathon has an
 * organiser, an AI offer has a provider. It is a parameter rather than a
 * hard-coded "organiser" because this block is shared by both builders, and
 * calling a provider an organiser is the kind of wrong-domain wording that
 * makes an exported deal prompt read like a hackathon brief.
 */
function reliabilityBlock(
  item: Hackathon | AIDeal,
  sourceNoun: string,
  unknownFacts: string,
): string {
  const status = item.verificationStatus.replace(/_/g, ' ').toUpperCase();
  const confidence = Math.round((item.confidenceScore ?? 0) * 100);

  return `==============================================================
0. DATA RELIABILITY — READ FIRST
==============================================================
The details below were indexed by DevRadar, a third-party catalogue. They were
NOT published to you by the ${sourceNoun} and may be out of date.

- Verification status: ${status}
- Confidence: ${confidence}/100 (deterministic completeness score, not a guarantee)
- Last checked by DevRadar: ${fmtDate(item.lastCheckedAt)}

Rules for your answer:
- Treat every date, figure and rule below as unconfirmed. Remind me to verify
  them at the official URL before I commit time or money.
- ${unknownFacts}
- If you rely on a fact that is not stated below, say so explicitly instead of
  presenting it as given.`;
}

/**
 * Anchors the assistant in real time; LLMs cannot reliably infer "now" and will
 * otherwise silently assume how much runway a deadline leaves.
 *
 * `deadlineNoun` must be a noun phrase ("the submission deadline"), since it is
 * read both as "until <noun>" and "<noun> has already passed".
 */
function timeAnchor(
  deadlineIso: string | null | undefined,
  deadlineNoun: string,
): string {
  const today = `- Today: ${fmtDate(new Date().toISOString())}`;
  const info = getDeadlineInfo(deadlineIso);
  if (!info) {
    return `${today}\n- Time remaining: no date on record — confirm on the official page`;
  }
  if (info.urgency === 'closed') {
    return `${today}\n- Time remaining: NONE — ${deadlineNoun} has already passed. Say so before planning anything.`;
  }
  const days = info.daysLeft <= 0 ? 'less than 1 day' : `${info.daysLeft} days`;
  return `${today}\n- Time remaining: ${days} until ${deadlineNoun}`;
}

/** Shared answer shape for section A, so ideas can be compared side by side. */
const IDEA_FORMAT = `Format each one exactly like this:

### Idea N — <short name>
- Pitch: <one sentence>
- Target user: <who specifically>
- Why it fits: <one sentence>
- Risk: low | med | high — <the single biggest risk>`;

/**
 * How the detail modal frames the generated prompt.
 *
 * This lives beside the builders rather than in the component so the tab label
 * and the section chips cannot drift from the sections the prompt actually
 * contains. They had drifted: the deals tab advertised an "MVP timeline" and
 * "demo/pitch tips" — hackathon vocabulary — for an offer whose prompt is about
 * integrating an API and not burning the quota.
 */
/** Icon slot for a section chip; the modal maps these to lucide components. */
export type PromptSectionIcon = 'brief' | 'ideas' | 'build' | 'timeline' | 'cost';

export interface PromptSection {
  label: string;
  icon: PromptSectionIcon;
}

export interface PromptMeta {
  /** Tab label in the detail modal. */
  tabLabel: string;
  /** Heading above the copy button. */
  title: string;
  /** One-line description of what the prompt asks the assistant to produce. */
  blurb: string;
  /** Chips; each names a real section of the corresponding prompt. */
  sections: [PromptSection, PromptSection, PromptSection, PromptSection];
}

const PASTE_TARGETS = 'Paste into Cursor, Claude, ChatGPT, or Antigravity.';

const HACKATHON_PROMPT_META: PromptMeta = {
  tabLabel: 'AI Agent Prompt',
  title: 'AI brainstorm & execution prompt',
  blurb:
    'Auto-generated plan prompt: brief details, 3 project ideas, architecture, MVP ' +
    `timeline, and demo/pitch tips. ${PASTE_TARGETS}`,
  sections: [
    { label: 'Brief details', icon: 'brief' },
    { label: '3 project ideas', icon: 'ideas' },
    { label: 'Architecture', icon: 'build' },
    { label: 'MVP timeline', icon: 'timeline' },
  ],
};

const AI_DEAL_PROMPT_META: PromptMeta = {
  // Not "AI Agent Prompt": inside the AI Deals module every listing is already
  // an AI product, so that label said nothing about what the tab contains.
  tabLabel: 'Integration Prompt',
  title: 'Integration & build prompt',
  blurb:
    'Auto-generated build plan for this offer: what you get, a fit check for what ' +
    `you're building, secure API integration, and cost controls. ${PASTE_TARGETS}`,
  sections: [
    { label: 'Offer details', icon: 'brief' },
    { label: 'Fit check', icon: 'ideas' },
    { label: 'Integration', icon: 'build' },
    { label: 'Cost & quota', icon: 'cost' },
  ],
};

/** Framing for the prompt `generateAIPrompt` returns for the same item. */
export function getPromptMeta(item: Hackathon | AIDeal): PromptMeta {
  return isHackathonItem(item) ? HACKATHON_PROMPT_META : AI_DEAL_PROMPT_META;
}

/**
 * Ready-to-paste execution & brainstorming prompt for AI coding assistants
 * (Cursor, Claude, ChatGPT, Antigravity, etc.).
 */
export function generateAIPrompt(item: Hackathon | AIDeal): string {
  return isHackathonItem(item)
    ? buildHackathonPrompt(item)
    : buildAIDealPrompt(item);
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
  const effort = h.effortEstimate || 'not estimated';
  const mode = (h.mode || 'online').replace(/_/g, ' ').toUpperCase();
  const submissionInfo = getDeadlineInfo(h.submissionDeadline);
  const isOpen = submissionInfo != null && submissionInfo.urgency !== 'closed';
  const daysLeft = Math.max(0, submissionInfo?.daysLeft ?? 0);
  // Two phrasings because the same window is read as "within X" and "using X".
  const scopeWindow = isOpen ? `${daysLeft} days` : 'the time remaining';
  const timelineWindow = isOpen ? `the ${daysLeft} days` : 'the time';

  return `You are an expert software architect and hackathon strategy mentor.
I am building a submission for the hackathon below. Help me brainstorm, architect, and ship a winning MVP.

${reliabilityBlock(
  h,
  'organiser',
  'Judging criteria are NOT included below. If you infer them, label them as your inference, not as the organiser\'s rules.',
)}

==============================================================
1. BRIEF DETAILS (from DevRadar)
==============================================================
${timeAnchor(h.submissionDeadline, 'the submission deadline')}

- Title: ${h.title}
- Organizer: ${h.organizer}
- Prize pool: ${prize}
- Mode: ${mode}${h.location ? ` · ${h.location}` : ''}
- Registration deadline: ${regDate}
- Submission deadline: ${subDate}
- Team size: ${h.teamMin}–${h.teamMax}
- DevRadar effort estimate: ${effort}
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
- Align with the prize framing (${prizeCompact})
- Are feasible for a team of ${h.teamMin}–${h.teamMax} within ${scopeWindow}

${IDEA_FORMAT}

B. Architecture recommendation
Wait for me to pick an idea before answering this section. Then give:
- Recommended monorepo / app folder structure
- Frontend + backend choices that match the stack
- External APIs / SDKs to integrate
- Database schema (tables or document models) for the MVP
- Auth, secrets, and deploy target (Vercel/Railway/etc.) if relevant

C. MVP execution timeline
Work backwards from the submission deadline ${subDate}, using ${timelineWindow}
actually left from today (registration closes ${regDate}).
DevRadar sizes this build at "${effort}". Compare that against the time really
remaining and tell me plainly if the scope is unrealistic before planning.
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
  const indexedAt = fmtDate(d.startsAt);
  const offerType = (d.offerType || '').replace(/_/g, ' ').toUpperCase();
  const requirements = bulletList(d.requirements, 'Standard developer offer terms');
  const highlights = bulletList(d.suitableReasons, 'Active AI product / credits offer');

  // Most catalogue offers are open-ended free tiers. Interpolating the "no
  // expiry" wording straight into a sentence produced "hard stop before No
  // fixed expiry listed", so the two cases get their own phrasing.
  const expiryLine = d.expiresAt
    ? `- Expires / use-by: ${fmtDate(d.expiresAt)}`
    : '- Expires / use-by: no fixed expiry listed';
  const hardStop = d.expiresAt
    ? `with a hard stop before ${fmtDate(d.expiresAt)}`
    : 'with no fixed expiry — plan a normal build window rather than a deadline sprint';
  const exhaustionCase = d.expiresAt
    ? `the allowance runs out or the offer expires on ${fmtDate(d.expiresAt)}`
    : 'the allowance runs out';

  return `You are an AI developer and cloud architecture consultant.
I am claiming the AI offer below and want a concrete plan for integrating it
into a project without burning the allowance before the build is finished.

${reliabilityBlock(
  d,
  'provider',
  'Quotas, pricing and free-tier limits change often and are NOT authoritative below. Flag any limit you are unsure of instead of assuming it.',
)}

==============================================================
1. OFFER DETAILS (from DevRadar)
==============================================================
${timeAnchor(d.expiresAt, "the offer's expiry date")}

- Product: ${d.productName}
- Provider: ${d.provider}
- Offer type: ${offerType}
- Offer value: ${d.offerValue}
- Target users: ${targets}
- Supported regions: ${regions}
${expiryLine}
- First indexed by DevRadar: ${indexedAt}
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

A. Fit check
Before anything else, ask me one question: what am I planning to build (or what
problem am I trying to solve)? Then in 3–5 sentences tell me:
- Whether ${d.provider} / ${d.productName} is actually the right tool for it
- Which single capability of the offer I would lean on hardest
- One realistic alternative if the fit is weak — do not force a match

If I say I have no project yet, propose ONE concrete integration idea that fits
the offer and stops there. Do not brainstorm a list; a shortlist is what wastes
the credits.

B. Secure integration (the core section)
Wait for me to confirm the direction from A. Then produce a working integration
plan:
- Where the API key lives (server-side only, env vars, rotation) and what to
  do the moment it leaks
- Minimum viable request/response shape against ${d.provider}, with the exact
  auth header / SDK call
- Rate-limit and timeout handling; what to retry, what to fail fast
- Fallback path when the provider is down or the quota is spent
- Repo / file layout in the language I say I use — no boilerplate for
  frameworks I did not mention

C. Cost & quota control (the other core section)
The usual way an offer like this is wasted is burning the allowance before the
build is finished. Give me:
- Burn-rate estimate: what one request/call costs, what drives the cost, and
  roughly how far ${d.offerValue} goes. State plainly which numbers you are
  unsure of rather than presenting estimates as facts.
- Hard limits to set before the first real run — spend caps, rate limits, max
  tokens/requests, timeouts — and where each one is configured
- What to log so I can see spend per feature instead of only a running total
- Exit plan: what breaks when ${exhaustionCase}, and the cheapest equivalent
  to fall back to

D. Timeline (short)
Not a hackathon plan — just the order things should happen in, ${hardStop}:
1. Claim + API key + smoke test
2. Cost caps and logging (before writing feature code, not after)
3. Core integration behind a thin interface I can swap
4. Real usage against the caps, then adjust

Let's start with A — ask me what I am building.`;
}

/** True when item looks like a catalogue hackathon row. */
export function isHackathonItem(item: Hackathon | AIDeal): item is Hackathon {
  return 'prizeValue' in item;
}
