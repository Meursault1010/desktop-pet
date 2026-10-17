import { invoke, isTauri } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import type { Message } from '../bridge';
import type { DesktopHost } from './types';

export function tauriHost(): DesktopHost | undefined {
  if (!isTauri()) return;
  return {
    kind: 'tauri',
    request: (name, payload) => invoke<Message>('pet_command', { name, payload }),
    async subscribe(onMessage, onDisconnect) {
      const stop = await listen<Message>('pet-message', event => onMessage(event.payload));
      try {
        const disconnect = await listen<string>('pet-disconnected', event => onDisconnect(event.payload));
        return () => { stop(); disconnect(); };
      } catch (error) { stop(); throw error; }
    },
    reconnect: () => invoke('restart_pet'),
    exit: () => invoke('exit_app'),
  };
}
