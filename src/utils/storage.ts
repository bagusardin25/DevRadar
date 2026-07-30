/**
 * Failure-tolerant browser storage access.
 *
 * localStorage can throw in hardened/privacy contexts, and writes can fail
 * when a quota is exhausted. Preferences should degrade to in-memory state
 * instead of taking down the catalogue.
 */
export function readLocalStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writeLocalStorage(key: string, value: string): boolean {
  try {
    window.localStorage.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}
