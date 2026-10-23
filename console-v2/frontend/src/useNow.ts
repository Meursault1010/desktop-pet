import {useSyncExternalStore} from 'react';

let current = Date.now();
let timer: number | undefined;
const listeners = new Set<() => void>();

function tick() {
  current = Date.now();
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void) {
  if (!listeners.size) {
    current = Date.now();
    timer = window.setInterval(tick, 1000);
  }
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
    if (!listeners.size && timer !== undefined) {
      window.clearInterval(timer);
      timer = undefined;
    }
  };
}

function snapshot() {
  return current;
}

/** One shared one-second clock; only components that call this hook re-render. */
export function useNow() {
  return useSyncExternalStore(subscribe, snapshot, snapshot);
}
