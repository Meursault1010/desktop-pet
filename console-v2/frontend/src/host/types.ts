import type { Message } from '../bridge';

export interface DesktopHost {
  readonly kind: 'electron' | 'tauri';
  request(name: string, payload: Record<string, unknown>): Promise<Message>;
  subscribe(onMessage: (message: Message) => void, onDisconnect: (reason: string) => void): Promise<() => void>;
  reconnect(): Promise<void>;
  exit(): Promise<void>;
}

declare global {
  interface Window { yukiHost?: DesktopHost }
}
