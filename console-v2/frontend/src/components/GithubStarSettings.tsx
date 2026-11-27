import {useEffect, useRef, useState} from 'react';
import {ExternalLink, Star} from 'lucide-react';
import {host} from '../host';
import type {GithubStarStatus} from '../host/types';

const repositoryUrl = 'https://github.com/Meursault1010/desktop-pet';
const authorizationUrl = 'https://github.com/login/device';

export function GithubStarSettings() {
  const [status, setStatus] = useState<GithubStarStatus | null>(host?.githubStar ? null : {phase: 'manual'});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const revision = useRef(0);
  const phase = status?.phase;
  const polling = phase === 'requesting' || phase === 'pending' || phase === 'starring';
  const alert = error || (status?.phase === 'error' ? status.message : '');
  const canAuthorize = phase === 'idle' || phase === 'error';
  const starred = phase === 'starred';
  const projectLabel = starred ? '查看 GitHub 项目' : '去 GitHub 加星';

  useEffect(() => {
    const getStatus = host?.githubStar;
    if (!getStatus) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const read = async () => {
      const requested = revision.current;
      try {
        const next = await getStatus('status');
        if (active && requested === revision.current) setStatus(next);
      } catch {
        if (active && requested === revision.current) {
          setStatus({phase: 'manual'});
          setError('无法读取加星状态。');
        }
      }
      if (polling && active) timer = setTimeout(read, 750);
    };
    void read();
    return () => { active = false; clearTimeout(timer); };
  }, [polling]);

  async function run(action: 'start' | 'cancel') {
    if (!host?.githubStar || busy) return;
    revision.current++;
    setError('');
    setBusy(true);
    try {
      setStatus(await host.githubStar(action));
    } catch {
      setError('无法操作 GitHub 加星，请重试。');
    } finally {
      setBusy(false);
    }
  }

  async function open(url: string) {
    try {
      await host?.openExternal?.(url);
    } catch {
      setError('无法打开浏览器，请重试。');
    }
  }

  const projectLink = host?.openExternal ? (
    <button type="button" className="button secondary" onClick={() => void open(repositoryUrl)}
      title={starred ? '在浏览器查看 Yuki 的 GitHub 仓库。' : '在浏览器打开 Yuki 的 GitHub 仓库，从仓库页面点击 Star。'}>
      <ExternalLink size={15} aria-hidden="true" />{projectLabel}
    </button>
  ) : (
    <a className="button secondary" href={repositoryUrl} target="_blank" rel="noreferrer">
      <ExternalLink size={15} aria-hidden="true" />{projectLabel}
    </a>
  );

  return (
    <div className="setting-row github-star-row">
      <span>
        <strong>为 Yuki 加星</strong>
        <small>在 GitHub 上支持 Yuki 桌面宠物。</small>
        <small role="status" aria-atomic="true">
          {phase === 'manual' && '授权加星暂未启用。'}
          {phase === 'idle' && '授权后，Yuki 会自动为项目加星。'}
          {phase === 'requesting' && '正在获取 GitHub 授权码…'}
          {status?.phase === 'pending' && <>请在 GitHub 输入授权码 <code>{status.code}</code>，确认后 Yuki 会自动加星。</>}
          {phase === 'starring' && '正在提交加星…'}
          {phase === 'starred' && 'GitHub 已确认加星，感谢支持！'}
        </small>
        {alert && <small role="alert" className="github-star-error">{alert}</small>}
      </span>
      <div className="github-star-actions">
        {(phase === 'requesting' || phase === 'pending') && <button type="button" className="button secondary" disabled={busy}
          onClick={() => void run('cancel')}>取消授权</button>}
        {projectLink}
        {starred ? (
          <span className="github-star-confirmed">
            <Star size={15} fill="currentColor" aria-hidden="true" />已加星
          </span>
        ) : (
          <button type="button" className="button secondary" disabled={busy || (!canAuthorize && phase !== 'pending')}
            onClick={() => void (phase === 'pending' ? open(authorizationUrl) : run('start'))}
            title="通过 GitHub 确认授权后，Yuki 会为项目仓库加星。">
            <Star size={15} aria-hidden="true" />
            {phase === 'pending' ? '打开 GitHub 授权' : '授权加星'}
          </button>
        )}
      </div>
    </div>
  );
}
