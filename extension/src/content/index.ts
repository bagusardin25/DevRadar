import type { PageData } from '../shared/types';
import {
  ISO_DATE_RE, US_DATE_RE, MONEY_RE, TECH_KEYWORDS,
  REGISTRATION_LINK_KEYWORDS,
} from '../shared/constants';
import { getVisibleText } from './visibleText';

const MAX_TITLE_LENGTH = 300;
const MAX_META_LENGTH = 1000;
const MAX_OG_TAGS = 30;
const MAX_JSON_LD_SCRIPTS = 10;
const MAX_JSON_LD_CHARS = 20_000;
const MAX_EXTRACTED_VALUES = 50;
const MAX_LINKS = 200;
const MAX_URL_LENGTH = 2048;

function clampText(value: string | null | undefined, maxLength: number): string | null {
  const text = value?.trim();
  return text ? text.slice(0, maxLength) : null;
}

function getMetaContent(name: string): string | null {
  const el = document.querySelector(`meta[name="${name}"], meta[property="${name}"]`);
  return clampText(el?.getAttribute('content'), MAX_META_LENGTH);
}

function getOgTags(): Record<string, string> {
  const tags: Record<string, string> = {};
  for (const el of Array.from(document.querySelectorAll('meta[property^="og:"]')).slice(0, MAX_OG_TAGS)) {
    const prop = el.getAttribute('property');
    const content = clampText(el.getAttribute('content'), MAX_META_LENGTH);
    if (prop && prop.length <= 100 && content) tags[prop] = content;
  }
  return tags;
}

function getJsonLd(): unknown[] {
  const results: unknown[] = [];
  const scripts = Array.from(
    document.querySelectorAll('script[type="application/ld+json"]'),
  ).slice(0, MAX_JSON_LD_SCRIPTS);
  for (const el of scripts) {
    const raw = (el.textContent || '').trim();
    if (!raw) continue;
    if (raw.length > MAX_JSON_LD_CHARS) {
      // The extractor only uses structured-data presence for confidence. Do
      // not clone or message multi-megabyte blobs from hostile pages.
      if (raw.startsWith('{') || raw.startsWith('[')) results.push({ truncated: true });
      continue;
    }
    try {
      JSON.parse(raw);
      results.push({ valid: true });
    } catch { /* skip malformed */ }
  }
  return results;
}

function findDates(text: string): string[] {
  const dates = new Set<string>();
  for (const m of text.matchAll(new RegExp(ISO_DATE_RE.source, 'g'))) {
    dates.add(m[1]);
    if (dates.size >= MAX_EXTRACTED_VALUES) break;
  }
  for (const m of text.matchAll(new RegExp(US_DATE_RE.source, 'gi'))) {
    dates.add(m[1]);
    if (dates.size >= MAX_EXTRACTED_VALUES) break;
  }
  return [...dates];
}

function findMoneyAmounts(text: string): string[] {
  const amounts = new Set<string>();
  for (const m of text.matchAll(new RegExp(MONEY_RE.source, 'g'))) {
    const raw = m[0].trim();
    if (raw) amounts.add(raw);
    if (amounts.size >= MAX_EXTRACTED_VALUES) break;
  }
  return [...amounts];
}

function findTechKeywords(text: string): string[] {
  const lower = text.toLowerCase();
  return TECH_KEYWORDS.filter((tech) => lower.includes(tech.toLowerCase()));
}

function getLinks(): Array<{ href: string; text: string }> {
  const links: Array<{ href: string; text: string }> = [];
  const seen = new Set<string>();
  for (const el of document.querySelectorAll('a[href]')) {
    const href = (el as HTMLAnchorElement).href;
    const text = (el.textContent || '').trim().slice(0, 100);
    if (href && href.length <= MAX_URL_LENGTH && !seen.has(href) && href.startsWith('http')) {
      seen.add(href);
      links.push({ href, text });
      if (links.length >= MAX_LINKS) break;
    }
  }
  return links;
}

function findRegistrationLinks(links: Array<{ href: string; text: string }>): string[] {
  return links
    .filter((link) => {
      const combined = `${link.href} ${link.text}`.toLowerCase();
      return REGISTRATION_LINK_KEYWORDS.some((kw) => combined.includes(kw));
    })
    .map((link) => link.href)
    .slice(0, 10);
}

function scrape(): PageData {
  const text = getVisibleText();
  const links = getLinks();

  return {
    url: window.location.href.slice(0, MAX_URL_LENGTH),
    title: clampText(document.title, MAX_TITLE_LENGTH),
    metaDescription: getMetaContent('description'),
    ogTags: getOgTags(),
    jsonLd: getJsonLd(),
    visibleText: text,
    dates: findDates(text),
    moneyAmounts: findMoneyAmounts(text),
    techKeywords: findTechKeywords(text),
    links,
    registrationLinks: findRegistrationLinks(links),
    scrapedAt: new Date().toISOString(),
  };
}

const data = scrape();
chrome.runtime.sendMessage({ type: 'PAGE_DATA', data });
