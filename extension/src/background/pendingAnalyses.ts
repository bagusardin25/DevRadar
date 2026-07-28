type Pending<T> = {
  resolve: (value: T) => void;
  reject: (error: Error) => void;
  timeout: ReturnType<typeof setTimeout>;
};

/** Tab-keyed resolver registry; prevents cross-tab and double-click races. */
export class PendingAnalysisRegistry<T> {
  private readonly pending = new Map<number, Pending<T>>();

  has(tabId: number): boolean {
    return this.pending.has(tabId);
  }

  start(tabId: number, timeoutMs: number, timeoutMessage: string): Promise<T> {
    if (this.pending.has(tabId)) {
      throw new Error('Analysis is already in progress for this tab');
    }
    return new Promise<T>((resolve, reject) => {
      const timeout = setTimeout(() => {
        const current = this.pending.get(tabId);
        if (!current) return;
        this.pending.delete(tabId);
        reject(new Error(timeoutMessage));
      }, timeoutMs);
      this.pending.set(tabId, { resolve, reject, timeout });
    });
  }

  resolve(tabId: number, value: T): boolean {
    const current = this.take(tabId);
    if (!current) return false;
    current.resolve(value);
    return true;
  }

  reject(tabId: number, error: Error): boolean {
    const current = this.take(tabId);
    if (!current) return false;
    current.reject(error);
    return true;
  }

  private take(tabId: number): Pending<T> | null {
    const current = this.pending.get(tabId);
    if (!current) return null;
    this.pending.delete(tabId);
    clearTimeout(current.timeout);
    return current;
  }
}
