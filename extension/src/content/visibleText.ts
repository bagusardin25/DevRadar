export const MAX_VISIBLE_TEXT_LENGTH = 5_000;
export const MAX_TEXT_NODES = 5_000;
const MAX_NODE_TEXT_CHARS = 2_000;
const MAX_VISIBILITY_ANCESTORS = 128;
const SHOW_TEXT = 4;

const NOISE_SELECTOR =
  'nav, footer, header, script, style, noscript, iframe, ' +
  '[role="navigation"], [role="banner"], [aria-hidden="true"], ' +
  '.cookie-banner, .cookie-consent, #cookie-consent';

function isRendered(
  element: Element,
  view: Window | null,
  cache: WeakMap<Element, boolean>,
): boolean {
  let current: Element | null = element;
  const traversed: Element[] = [];
  let rendered = true;

  while (current) {
    const cached = cache.get(current);
    if (cached !== undefined) {
      rendered = cached;
      break;
    }
    if (traversed.length >= MAX_VISIBILITY_ANCESTORS) {
      rendered = false;
      break;
    }
    traversed.push(current);
    if (current.hasAttribute('hidden') || current.getAttribute('aria-hidden') === 'true') {
      rendered = false;
      break;
    }
    if (view) {
      const style = view.getComputedStyle(current);
      if (
        style.display === 'none' ||
        style.visibility === 'hidden' ||
        style.visibility === 'collapse' ||
        style.opacity === '0'
      ) {
        rendered = false;
        break;
      }
    }
    current = current.parentElement;
  }

  for (const visited of traversed) cache.set(visited, rendered);
  return rendered;
}

export function getVisibleText(doc: Document = document): string {
  if (!doc.body) return '';
  const parts: string[] = [];
  const visibilityCache = new WeakMap<Element, boolean>();
  let length = 0;
  let visited = 0;
  const walker = doc.createTreeWalker(doc.body, SHOW_TEXT);

  while (length < MAX_VISIBLE_TEXT_LENGTH && visited < MAX_TEXT_NODES) {
    const node = walker.nextNode();
    if (!node) break;
    visited += 1;

    // Slice before normalization so a single hostile multi-megabyte text node
    // cannot monopolize the content-script worker.
    const chunk = (node.textContent || '')
      .slice(0, MAX_NODE_TEXT_CHARS)
      .replace(/\s+/g, ' ')
      .trim();
    if (!chunk) continue;

    const parent = node.parentElement;
    if (
      !parent ||
      parent.closest(NOISE_SELECTOR) ||
      !isRendered(parent, doc.defaultView, visibilityCache)
    ) {
      continue;
    }

    const remaining = MAX_VISIBLE_TEXT_LENGTH - length;
    const value = chunk.slice(0, remaining);
    parts.push(value);
    length += value.length + 1;
  }
  return parts.join(' ').slice(0, MAX_VISIBLE_TEXT_LENGTH);
}
