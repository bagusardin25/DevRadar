import type { PageData } from '../shared/types';
import {
  ISO_DATE_RE, US_DATE_RE, MONEY_RE, TECH_KEYWORDS,
  REGISTRATION_LINK_KEYWORDS,
} from '../shared/constants';

const MAX_TEXT_LENGTH = 5000;

function getMetaContent(name: string): string | null {
  const el = document.querySelector(`meta[name="${name}"], meta[property="${name}"]`);
  return el?.getAttribute('content') || null;
}

function getOgTags(): Record<string, string> {
  const tags: Record<string, string> = {};
  document.querySelectorAll('meta[property^="og:"]').forEach((el) => {
    const prop = el.getAttribute('property');
    const content = el.getAttribute('content');
    if (prop && content) tags[prop] = content;
  });
  return tags;
}

function getJsonLd(): unknown[] {
  const results: unknown[] = [];
  document.querySelectorAll('script[type="application/ld+json"]').forEach((el) => {
    try {
      results.push(JSON.parse(el.textContent || ''));
    } catch { /* skip malformed */ }
  });
  return results;
}

function getVisibleText(): string {
  const clone = document.body.cloneNode(true) as HTMLElement;
  clone.querySelectorAll(
    'nav, footer, header, script, style, noscript, iframe, ' +
    '[role="navigation"], [role="banner"], [aria-hidden="true"], ' +
    '.cookie-banner, .cookie-consent, #cookie-consent'
  ).forEach((el) => el.remove());

  const text = clone.innerText || clone.textContent || '';
  const cleaned = text.replace(/\s+/g, ' ').trim();
  return cleaned.slice(0, MAX_TEXT_LENGTH);
}

function findDates(text: string): string[] {
  const dates = new Set<string>();
  for (const m of text.matchAll(new RegExp(ISO_DATE_RE.source, 'g'))) {
    dates.add(m[1]);
  }
  for (const m of text.matchAll(new RegExp(US_DATE_RE.source, 'gi'))) {
    dates.add(m[1]);
  }
  return [...dates];
}

function findMoneyAmounts(text: string): string[] {
  const amounts = new Set<string>();
  for (const m of text.matchAll(new RegExp(MONEY_RE.source, 'g'))) {
    const raw = m[0].trim();
    if (raw) amounts.add(raw);
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
  document.querySelectorAll('a[href]').forEach((el) => {
    const href = (el as HTMLAnchorElement).href;
    const text = (el.textContent || '').trim().slice(0, 100);
    if (href && !seen.has(href) && href.startsWith('http')) {
      seen.add(href);
      links.push({ href, text });
    }
  });
  return links.slice(0, 200);
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
    url: window.location.href,
    title: document.title || null,
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
