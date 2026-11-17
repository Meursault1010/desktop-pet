import {useEffect, useState} from 'react';
import {Download, RefreshCw, RotateCw} from 'lucide-react';
import {host} from '../host';
import type {UpdateStatus} from '../host/types';

function formatSize(bytes?: number) {
  if (!bytes || bytes < 0) return '';
  return bytes >= 1e9 ? `${(bytes / 1e9).toFixed(2)} GB` : `${Math.max(1, Math.round(bytes / 1e6))} MB`;
}

function statusText(status: UpdateStatus) {
  const version = status.version ? ` v${status.version.replace(/^v/, '')}` : '';
  switch (status.phase) {
    case 'checking': return '正在检查更新…';
    case 'current': return '已是最新版本';
    case 'available': return ['发现新版本' + version, formatSize(status.size)].filter(Boolean).join(' · ');
    case 'downloading': return status.progress === 100 ? '正在准备更新…' : '正在下载更新…';
    case 'ready': return `新版${version} 已下载，安装后会重新打开 Yuki`;
    case 'installing': return '正在退出并安装更新…';
    case 'error': return status.message || '更新失败，请重试。';
    case 'unsupported': return status.message || '请在 Windows 发布版中使用更新功能';
    default: return '可检查是否有新版本';
  }
}

export function AppUpdateSettings() {
  const [status, setStatus] = useState<UpdateStatus | null>(null);
  const [requestError, setRequestError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!host?.updateStatus) return;
    let active = true;
    let receivedUpdate = false;
    const unsubscribe = host.onUpdateStatus?.(next => {
      if (!active) return;
      receivedUpdate = true;
      setStatus(next);
      setRequestError('');
    });
    void host.updateStatus().then(current => {
      if (active && !receivedUpdate) setStatus(current);
    }).catch(() => {
      if (active && !receivedUpdate) setRequestError('无法读取更新状态，请重试。');
    });
    return () => {
      active = false;
      unsubscribe?.();
    };
  }, []);

  const phase = status?.phase;
  const locked = busy || phase === 'checking' || phase === 'downloading' || phase === 'installing';
  const download = phase === 'available' || phase === 'downloading';
  const install = phase === 'ready' || phase === 'installing';
  const action = download ? host?.updateDownload : install ? host?.updateInstall : host?.updateCheck;
  const actionLabel = download ? '下载更新' : install ? '重启并安装' : '检查更新';
  const ActionIcon = download ? Download : install ? RotateCw : RefreshCw;
  const progress = status?.progress;

  async function runAction() {
    if (!action || locked) return;
    setBusy(true);
    setRequestError('');
    try {
      setStatus(await action());
    } catch {
      setRequestError('更新操作失败，请重试。');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="setting-row app-update-row">
      <span>
        <strong>版本更新</strong>
        {status?.currentVersion && <small>当前版本 v{status.currentVersion.replace(/^v/, '')}</small>}
        <small role="status" className={requestError || phase === 'error' ? 'app-update-error' : undefined}>
          {requestError || (status ? statusText(status) : host?.updateStatus ? '正在读取更新状态…' : '请在 Windows 发布版中使用更新功能')}
        </small>
        {phase === 'downloading' && (
          <span className="app-update-progress">
            <progress aria-label="更新下载进度" max={100} value={progress} />
            {progress !== undefined && <small aria-hidden="true">{Math.floor(progress)}%</small>}
          </span>
        )}
      </span>
      {action && phase !== 'unsupported' && (
        <button type="button" className={`button ${install || download ? 'primary' : 'secondary'}`} disabled={locked} onClick={() => void runAction()}>
          <ActionIcon aria-hidden="true" size={15} />{actionLabel}
        </button>
      )}
    </div>
  );
}
