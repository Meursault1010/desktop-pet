type Job<T> = {
  key: string;
  coalesce: boolean;
  run: () => Promise<T>;
  resolve: (value: T) => void;
  reject: (reason: unknown) => void;
  promise: Promise<T>;
};

/** Keep IPC ordered. Only unsent preferences may be replaced by newer values. */
export class CommandQueue<T> {
  private jobs: Job<T>[] = [];
  private active: Job<T> | null = null;
  onChange: (keys: string[]) => void = () => {};

  enqueue(key: string, run: () => Promise<T>, coalesce = false): Promise<T> {
    if (!coalesce) {
      const duplicate = this.active?.key === key ? this.active : this.jobs.find(job => job.key === key);
      if (duplicate) return duplicate.promise;
    } else {
      // Do not move a preference across an intervening action/reset.
      for (let i = this.jobs.length - 1; i >= 0 && this.jobs[i].coalesce; i--) {
        if (this.jobs[i].key === key) {
          this.jobs[i].run = run;
          return this.jobs[i].promise;
        }
      }
    }
    let resolve!: (value: T) => void;
    let reject!: (reason: unknown) => void;
    const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
    this.jobs.push({ key, run, coalesce, resolve, reject, promise });
    this.emit();
    void this.drain();
    return promise;
  }

  cancelPending(reason: unknown) {
    const pending = this.jobs.splice(0);
    pending.forEach(job => job.reject(reason));
    this.emit();
  }

  private emit() {
    this.onChange([...new Set([...(this.active ? [this.active.key] : []), ...this.jobs.map(job => job.key)])]);
  }

  private async drain() {
    if (this.active) return;
    const job = this.jobs.shift();
    if (!job) return;
    this.active = job;
    this.emit();
    try { job.resolve(await job.run()); }
    catch (error) { job.reject(error); }
    finally { this.active = null; this.emit(); void this.drain(); }
  }
}

export function parseSettingNumber(text: string, min: number, max: number): number | null {
  if (!text.trim()) return null;
  const value = Number(text);
  return Number.isInteger(value) && value >= min && value <= max ? value : null;
}
