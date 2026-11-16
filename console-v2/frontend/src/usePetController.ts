import { useCallback, useEffect, useRef, useState } from 'react';
import { command, demo, exitApp, reconnect, subscribe, type Message, type PetSnapshot, type Preferences } from './bridge';
import { CommandQueue } from './commandQueue';

type Notice = { text: string; error: boolean; key?: string; retry?: () => void };
export function usePetController() {
  const [state, setState] = useState<PetSnapshot | null>(null);
  const [source, setSource] = useState('/pet-preview.png');
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(true);
  const [failure, setFailure] = useState('');
  const [notice, setNotice] = useState<Notice | null>(null);
  const [pending, setPending] = useState<string[]>([]);
  const [failedKeys, setFailedKeys] = useState<string[]>([]);
  const queue = useRef(new CommandQueue<boolean>());
  const online = useRef(false);
  const epoch = useRef(0);
  const retrying = useRef(false);
  const noticeTimer = useRef<number | undefined>(undefined);

  const notify = useCallback((text: string, error = false, retry?: () => void, key?: string) => {
    window.clearTimeout(noticeTimer.current);
    setNotice(previous => !error && previous?.error ? previous : { text, error, retry, key });
    if (!error) noticeTimer.current = window.setTimeout(() => setNotice(previous => previous?.error ? previous : null), 4000);
  }, []);
  const accept = useCallback((message: Message) => {
    if (message.state) {
      const incoming = message.state;
      setState(previous => !previous || incoming.revision >= previous.revision ? incoming : previous);
      online.current = true; setConnected(true); setConnecting(false); setFailure('');
    }
    if (message.preview) setSource(message.preview);
  }, []);

  useEffect(() => {
    let cancelled = false; let cleanup: (() => void) | undefined;
    queue.current.onChange = keys => { if (!cancelled) setPending(keys); };
    void (async () => {
      try {
        cleanup = await subscribe(message => { if (!cancelled && !retrying.current) accept(message); }, reason => {
          if (cancelled || retrying.current) return;
          online.current = false; epoch.current++;
          queue.current.cancelPending(new Error('连接已断开'));
          setConnected(false); setConnecting(false); setFailure(reason);
        });
        if (cancelled) { cleanup(); return; }
        for (let attempt = 0; attempt < 12; attempt++) {
          try { const result = await command('get_state'); if (!cancelled) accept(result); return; }
          catch (error) { if (cancelled) return; if (attempt === 11) throw error; await new Promise(resolve => window.setTimeout(resolve, 350)); }
        }
      } catch (error) { if (!cancelled) { setConnecting(false); setFailure(String(error)); } }
    })();
    return () => { cancelled = true; cleanup?.(); queue.current.onChange = () => {}; window.clearTimeout(noticeTimer.current); };
  }, [accept]);

  useEffect(() => {
    const resync = () => {
      if (document.visibilityState !== 'visible' || !online.current) return;
      void command('get_state').then(accept).catch(() => {});
    };
    document.addEventListener('visibilitychange', resync);
    window.addEventListener('focus', resync);
    return () => { document.removeEventListener('visibilitychange', resync); window.removeEventListener('focus', resync); };
  }, [accept]);

  const act = (name: string, payload: Record<string, unknown> = {}, success?: string): Promise<boolean> => {
    const preference = name === 'set_preference' || name === 'configure_icon_sleep' || name === 'configure_edge_attachment' || name === 'set_appearance_preview';
    const key = name === 'set_preference' ? `preference:${String(payload.key)}`
      : name === 'set_appearance_preview' ? 'appearance-preview'
      : name === 'configure_icon_sleep' ? `icon_sleep:${Object.keys(payload).sort().join(',')}`
      : name === 'configure_edge_attachment' ? `edge_attachment:${Object.keys(payload).sort().join(',')}` : name;
    const token = epoch.current;
    if (!online.current) { notify('宠物未连接，请先重新连接。', true); return Promise.resolve(false); }
    return queue.current.enqueue(key, async () => {
      if (token !== epoch.current || !online.current) return false;
      try {
        const message = await command(name, payload);
        if (token !== epoch.current) return false;
        accept(message);
        if (message.state?.storage_error) {
          setFailedKeys(previous => [...new Set([...previous, key])]);
          notify('设置已应用，但未能写入本地。请检查配置目录权限后重试。', true, () => { void act(name, payload, success); }, key);
          return false;
        }
        setFailedKeys(previous => name === 'reset_defaults' ? [] : previous.filter(item => item !== key));
        setNotice(previous => previous?.key === key || name === 'reset_defaults' ? null : previous);
        if (success) notify(success);
        return true;
      } catch (error) {
        if (token !== epoch.current) return false;
        setFailedKeys(previous => [...new Set([...previous, key])]);
        notify(`操作未完成：${String(error).replace(/^Error:\s*/, '')}`, true,
          preference || name === 'set_visible' ? () => { void act(name, payload, success); } : undefined, key);
        return false;
      }
    }, preference).catch(() => false);
  };
  const setPreference = (key: keyof Preferences, value: Preferences[keyof Preferences]) => act('set_preference', { key, value });
  const retry = async () => {
    if (retrying.current) return;
    retrying.current = true; online.current = false; epoch.current++;
    queue.current.cancelPending(new Error('正在重新连接'));
    setConnecting(true); setConnected(false); setFailure(''); setState(null);
    try {
      await reconnect();
      for (let i = 0; i < 12; i++) {
        try { accept(await command('get_state')); return; }
        catch (error) { if (i === 11) throw error; await new Promise(resolve => window.setTimeout(resolve, 350)); }
      }
    } catch (error) { setFailure(String(error)); setConnecting(false); }
    finally { retrying.current = false; }
  };
  const exit = async () => {
    // Exit waits behind all already accepted changes.
    return queue.current.enqueue('exit_app', async () => {
      try { if (demo) notify('这是界面预览，未退出真实宠物'); else await exitApp(); return true; }
      catch (error) { notify(`退出失败：${String(error)}`, true); return false; }
    }).catch(() => false);
  };
  const saveLabel = !connected ? '等待宠物连接' : pending.length ? '正在应用更改…'
    : state?.storage_error ? '设置未能保存' : failedKeys.length ? '有操作未完成' : demo ? '预览模式 · 不保存到桌面' : '偏好已保存到本机';
  return { state, source, connected, connecting, failure, notice, pending, failedKeys, saveLabel, act, setPreference, retry, exit, dismissNotice: () => setNotice(null) };
}
