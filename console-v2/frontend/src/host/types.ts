import type { Message } from '../bridge';

export interface DesktopHost {
  readonly kind: 'electron' | 'tauri';
  request(name: string, payload: Record<string, unknown>): Promise<Message>;
  subscribe(onMessage: (message: Message) => void, onDisconnect: (reason: string) => void): Promise<() => void>;
  reconnect(): Promise<void>;
  exit(): Promise<void>;
  aiModels?(): Promise<{endpoint:string;models:string[]}>;
  aiChat?(payload: {id:string;model:string;messages:{role:'user'|'assistant';content:string}[]}): Promise<{text:string}>;
  aiCancel?(): Promise<void>;
  aiSubscribe?(listener:(update:{id:string;phase:string;text:string})=>void):()=>void;
}

declare global {
  interface Window { yukiHost?: DesktopHost }
}
