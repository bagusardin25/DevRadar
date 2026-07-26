import { useEffect, useRef } from 'react';

/**
 * Selector for things a user can Tab to. `[tabindex="-1"]` is excluded because
 * those are focusable by script only and should not appear in the tab cycle.
 */
const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

/**
 * Wires up the keyboard and focus behaviour a modal dialog needs.
 *
 * Attach the returned ref to the dialog element (the panel, not the backdrop)
 * and give it `role="dialog"` and `aria-modal="true"`:
 *
 * ```tsx
 * const dialogRef = useModalA11y(true, onClose);
 * <div className="fixed inset-0 …">
 *   <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="my-title">…</div>
 * </div>
 * ```
 *
 * While open it:
 * - moves focus into the dialog, so the next Tab lands inside rather than on
 *   the page behind it;
 * - closes on Escape;
 * - cycles Tab and Shift+Tab within the dialog;
 * - locks background scroll;
 * - returns focus to whatever was focused before, on unmount or close.
 */
export function useModalA11y<T extends HTMLElement = HTMLDivElement>(
  isOpen: boolean,
  onClose: () => void,
) {
  const ref = useRef<T | null>(null);

  // Held in a ref so a caller passing a fresh arrow function each render does
  // not tear down and re-arm the whole effect (which would re-steal focus).
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const node = ref.current;
    if (!isOpen || !node) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;

    // Needed so the panel itself can take focus when it holds no controls yet.
    if (!node.hasAttribute('tabindex')) node.setAttribute('tabindex', '-1');
    (node.querySelector<HTMLElement>(FOCUSABLE) ?? node).focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation();
        onCloseRef.current();
        return;
      }
      if (event.key !== 'Tab') return;

      // Re-queried per keypress: modal contents change as tabs and disclosures
      // open, so a list captured at mount would go stale.
      const items = [...node.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
        (el) => el.offsetParent !== null,
      );
      if (items.length === 0) {
        event.preventDefault();
        return;
      }

      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;

      if (event.shiftKey && (active === first || active === node)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };

    // Capture phase so the dialog sees Escape before any inner handler can
    // stop it from bubbling.
    document.addEventListener('keydown', handleKeyDown, true);

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', handleKeyDown, true);
      document.body.style.overflow = previousOverflow;
      // Skip if the trigger was unmounted while the dialog was open.
      if (previouslyFocused?.isConnected) previouslyFocused.focus();
    };
  }, [isOpen]);

  return ref;
}
