'use strict';

const {setTimeout: delay} = require('node:timers/promises');

const GITHUB_DEVICE_CODE = 'https://github.com/login/device/code';
const GITHUB_ACCESS_TOKEN = 'https://github.com/login/oauth/access_token';
const STAR_ENDPOINT = 'https://api.github.com/user/starred/Meursault1010/desktop-pet';
const CLIENT_ID = /^Iv[0-9][A-Za-z0-9.]{8,78}$/;

function githubAppClientId(value) {
  const id = typeof value === 'string' ? value.trim() : '';
  if (id && !CLIENT_ID.test(id)) throw new Error('GitHub App Client ID 格式无效。');
  return id;
}

async function postForm(url, fields, signal) {
  const response = await fetch(url, {
    method: 'POST',
    headers: {Accept: 'application/json'},
    body: new URLSearchParams(fields),
    redirect: 'error',
    signal: AbortSignal.any([signal, AbortSignal.timeout(15000)]),
  });
  const result = await response.json();
  if (!response.ok && !result?.error) throw new Error('GitHub authorization request failed');
  return result;
}

class GithubStar {
  constructor(clientId) {
    this.clientId = clientId;
    this.state = {phase: clientId ? 'idle' : 'manual'};
  }

  start() {
    if (!this.clientId || this.session || this.state.phase === 'starred') return this.state;
    const session = new AbortController();
    this.session = session;
    this.state = {phase: 'requesting'};
    void this.run(session);
    return this.state;
  }

  cancel() {
    if (this.state.phase !== 'starring') this.stop();
    return this.state;
  }

  stop() {
    if (!this.session) return;
    this.session.abort();
    this.session = undefined;
    this.state = {phase: 'idle'};
  }

  async run(session) {
    const {signal} = session;
    const fail = message => { this.state = {phase: 'error', message}; };
    const expired = () => fail('授权码已过期，请重新开始。');
    try {
      const device = await postForm(GITHUB_DEVICE_CODE, {client_id: this.clientId}, signal);
      signal.throwIfAborted();
      if (device?.error === 'device_flow_disabled' || device?.error === 'incorrect_client_credentials') {
        return fail('GitHub 加星授权暂不可用，请前往项目页加星。');
      }
      if (typeof device?.device_code !== 'string' || !/^[A-Z0-9-]{4,20}$/.test(device.user_code ?? '')
          || !Number.isFinite(device.expires_in) || device.expires_in <= 0) {
        return fail('GitHub 未返回授权码，请重试或前往项目页加星。');
      }
      const deadline = Date.now() + Math.min(device.expires_in, 900) * 1000;
      let interval = Math.max(5, Number(device.interval) || 5);
      this.state = {phase: 'pending', code: device.user_code};
      while (Date.now() < deadline) {
        await delay(Math.min(interval * 1000, deadline - Date.now()), undefined, {signal});
        if (Date.now() >= deadline) break;
        const result = await postForm(GITHUB_ACCESS_TOKEN, {
          client_id: this.clientId,
          device_code: device.device_code,
          grant_type: 'urn:ietf:params:oauth:grant-type:device_code',
        }, signal);
        signal.throwIfAborted();
        if (result?.error === 'authorization_pending') continue;
        if (result?.error === 'slow_down') {
          interval = Math.max(interval + 5, Number(result.interval) || 0);
          continue;
        }
        if (result?.error === 'expired_token') return expired();
        if (result?.error === 'access_denied') return fail('GitHub 授权已拒绝，可以重新开始。');
        if (typeof result?.access_token !== 'string' || !result.access_token) {
          return fail('GitHub 未完成授权，请重新开始。');
        }

        this.state = {phase: 'starring'};
        const star = await fetch(STAR_ENDPOINT, {
          method: 'PUT',
          headers: {
            Accept: 'application/vnd.github+json',
            Authorization: `Bearer ${result.access_token}`,
            'Content-Length': '0',
            'X-GitHub-Api-Version': '2026-03-10',
          },
          body: '',
          redirect: 'error',
          signal: AbortSignal.any([signal, AbortSignal.timeout(15000)]),
        });
        signal.throwIfAborted();
        if (star.status === 204) this.state = {phase: 'starred'};
        else if ([403, 404].includes(star.status)) fail('GitHub 未允许这次加星，请前往项目页加星。');
        else fail('GitHub 未确认加星结果，请在项目页查看或重试。');
        return;
      }
      expired();
    } catch {
      if (!signal.aborted) {
        fail(this.state.phase === 'starring'
          ? 'GitHub 未确认加星结果，请在项目页查看或重试。'
          : '无法完成 GitHub 授权，请检查网络后重试。');
      }
    } finally {
      if (this.session === session) this.session = undefined;
    }
  }
}

module.exports = {GithubStar, githubAppClientId};
