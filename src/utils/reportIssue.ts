import type { Hackathon, AIDeal } from '../types';

/**
 * Reporting a bad listing goes to the project's GitHub issue tracker rather than
 * a DevRadar endpoint: it needs no account system, no moderation table, and no
 * extra anonymous write path to defend.
 */
const DEFAULT_REPO_URL = 'https://github.com/bagusardin25/DevRadar';

/** Strip `.git`, trailing slashes, and any `/issues...` a self-hoster pasted in. */
function normalizeRepoUrl(raw: string): string {
  return raw
    .trim()
    .replace(/\.git$/, '')
    .replace(/\/issues(\/new)?\/?$/, '')
    .replace(/\/+$/, '');
}

const configured = import.meta.env.VITE_REPO_URL as string | undefined;

/** Empty string disables reporting — a fork without a public tracker can opt out. */
export const REPORT_REPO_URL =
  configured === undefined ? DEFAULT_REPO_URL : normalizeRepoUrl(configured);

function isHackathon(item: Hackathon | AIDeal): item is Hackathon {
  return 'title' in item;
}

function formatChecked(iso: string | undefined): string {
  if (!iso) return 'unknown';
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? 'unknown' : date.toISOString();
}

/**
 * Prefilled "this listing is wrong" issue. Returns null when reporting is
 * disabled, so callers can hide the control entirely.
 */
export function buildReportIssueUrl(item: Hackathon | AIDeal): string | null {
  if (!REPORT_REPO_URL) return null;

  const name = isHackathon(item) ? item.title : `${item.provider} — ${item.productName}`;
  const url = isHackathon(item) ? item.officialUrl : item.officialTermsUrl;
  const origin = typeof window === 'undefined' ? 'unknown' : window.location.origin;

  const body = [
    '<!-- Thanks for flagging this. Please do not include personal information. -->',
    '',
    '**What is wrong?**',
    '',
    '- [ ] Link is dead or returns 404',
    '- [ ] Dates or deadline are wrong',
    '- [ ] Already closed / expired',
    '- [ ] Prize, terms, or eligibility are wrong',
    '- [ ] Not a real opportunity (spam or scam)',
    '- [ ] Something else',
    '',
    '**Details**',
    '',
    '',
    '---',
    '',
    '_Listing reference — please keep this block so we can find the record._',
    '',
    '| Field | Value |',
    '| --- | --- |',
    `| Name | ${name} |`,
    `| Id | \`${item.id}\` |`,
    `| Official URL | ${url} |`,
    `| Status | ${item.verificationStatus} |`,
    `| Confidence | ${Math.round((item.confidenceScore ?? 0) * 100)}% |`,
    `| Last checked | ${formatChecked(item.lastCheckedAt)} |`,
    `| Reported from | ${origin} |`,
  ].join('\n');

  const params = new URLSearchParams({
    title: `[Listing report] ${name}`,
    body,
    labels: 'listing-report',
  });
  return `${REPORT_REPO_URL}/issues/new?${params.toString()}`;
}
