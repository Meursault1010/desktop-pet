import { tauriHost } from './tauri';
import type { DesktopHost } from './types';

export const host: DesktopHost | undefined = window.yukiHost?.kind === 'electron' ? window.yukiHost : tauriHost();
