'use strict';

const {spawn} = require('node:child_process');
const {createHash} = require('node:crypto');
const fs = require('node:fs/promises');
const {constants, createWriteStream} = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {Readable, Transform} = require('node:stream');
const {pipeline} = require('node:stream/promises');

const REPOSITORY = 'Meursault1010/desktop-pet';
const RELEASE_API = `https://api.github.com/repos/${REPOSITORY}/releases/latest`;
const VERSION = /^(?:0|[1-9]\d{0,5})\.(?:0|[1-9]\d{0,5})\.(?:0|[1-9]\d{0,5})$/;
const SHA256 = /^sha256:([a-f\d]{64})$/i;
const STAGE = /^yuki-update-[a-z\d]{6}$/i;
const MODEL_FILE = 'Qwen3.8-4B-Q4_K_M.gguf';
const MAX_ARCHIVE = 2 ** 31 - 1;
const CHECK_INTERVAL = 12 * 60 * 60 * 1000;
const stageRoot = path.resolve(os.tmpdir());
const samePath = (left, right) => path.resolve(left).toLowerCase() === path.resolve(right).toLowerCase();
const validStage = dir => typeof dir === 'string' && path.isAbsolute(dir)
  && STAGE.test(path.basename(dir)) && samePath(path.dirname(dir), stageRoot);

class UpdateError extends Error {}

function releaseAsset(release, current) {
  if (!release || release.draft || release.prerelease || typeof release.tag_name !== 'string'
      || !release.tag_name.startsWith('v')) throw new UpdateError('暂时无法读取正式版本信息。');
  const version = release.tag_name.slice(1);
  if (!VERSION.test(version)) throw new UpdateError('发布版本号无效。');
  const parts = current.split('.').map(Number);
  const next = version.split('.').map(Number);
  const firstDifference = next.findIndex((part, i) => part !== parts[i]);
  if (firstDifference === -1 || next[firstDifference] < parts[firstDifference]) return null;
  const name = `yuki-win32-x64-v${version}.zip`;
  const url = `https://github.com/${REPOSITORY}/releases/download/v${version}/${name}`;
  const asset = release.assets?.find(item => item.name === name);
  const sha256 = SHA256.exec(asset?.digest || '')?.[1].toLowerCase();
  if (asset?.state !== 'uploaded' || asset.browser_download_url !== url || !sha256
      || !Number.isSafeInteger(asset.size) || asset.size < 1 || asset.size > MAX_ARCHIVE) {
    throw new UpdateError('新版暂不支持应用内安装，请前往 GitHub 发布页下载。');
  }
  return {version, name, url, sha256, size: asset.size};
}

async function assetResponse(url, signal) {
  let target = new URL(url);
  for (let redirects = 0; redirects < 5; redirects++) {
    if (target.protocol !== 'https:' || target.port || target.username || target.password ||
        !['github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'].includes(target.hostname)) {
      throw new UpdateError('更新下载地址无效。');
    }
    const response = await fetch(target, {signal, redirect: 'manual'});
    if (![301, 302, 303, 307, 308].includes(response.status)) return response;
    await response.body?.cancel();
    const location = response.headers.get('location');
    if (!location) break;
    target = new URL(location, target);
  }
  throw new UpdateError('暂时无法获取更新包。');
}

class Updater {
  constructor({app, changed, log, quit, enabled}) {
    this.changed = changed;
    this.log = log;
    this.quit = quit;
    this.enabled = enabled && VERSION.test(app.getVersion());
    this.installDir = path.dirname(process.execPath);
    this.userData = app.getPath('userData');
    this.marker = path.join(this.userData, 'pending-update.json');
    this.state = {phase: this.enabled ? 'idle' : 'unsupported', currentVersion: app.getVersion()};
  }

  snapshot() {
    return {...this.state};
  }

  set(phase, details = {}) {
    this.state = {phase, currentVersion: this.state.currentVersion, ...details};
    this.changed(this.snapshot());
    return this.snapshot();
  }

  fail(error, fallback, details) {
    this.log('Yuki 更新：' + (error.code || error.name || 'Error')
      + (error instanceof UpdateError ? ' ' + error.message : ''));
    return this.set('error', {...details, message: error instanceof UpdateError ? error.message : fallback});
  }

  async start(readyFile) {
    if (!this.enabled) return;
    const installed = await fs.lstat(this.installDir).catch(() => null);
    const dataLocation = path.relative(this.installDir, this.userData);
    const dataIsExternal = path.isAbsolute(dataLocation) || dataLocation === '..' || dataLocation.startsWith('..' + path.sep);
    const release = await fs.readFile(path.join(this.installDir, 'release-manifest.json'), 'utf8')
      .then(JSON.parse).catch(() => null);
    if (!/^[a-z]:\\.+/i.test(this.installDir) || !installed?.isDirectory() || !dataIsExternal
        || release?.version !== `v${this.state.currentVersion}`
        || release.modelFile !== MODEL_FILE || !/^[a-f\d]{64}$/i.test(release.modelSha256)) {
      this.enabled = false;
      this.set('unsupported', {message: '请从本机磁盘上完整解压的发布版检查更新。'});
      return;
    }
    const pending = await fs.readFile(this.marker, 'utf8').then(JSON.parse).catch(() => null);
    if (validStage(pending?.stage) && typeof pending.version === 'string' && VERSION.test(pending.version)) {
      this.set('installing', {version: pending.version});
      if (readyFile === path.join(pending.stage, 'startup-ready') && pending.version === this.state.currentVersion) {
        await fs.writeFile(readyFile, String(process.pid), {flag: 'wx'});
      }
      await this.observeResult(pending);
    }
    if (this.stopped) return;
    if (this.state.phase === 'idle') {
      this.initialCheck = setTimeout(() => void this.check(true), 15000);
      this.initialCheck.unref();
    }
    this.interval = setInterval(() => void this.check(true), CHECK_INTERVAL);
    this.interval.unref();
  }

  async observeResult(pending) {
    let result;
    try {
      result = JSON.parse(await fs.readFile(path.join(pending.stage, 'result.json'), 'utf8'));
    } catch {
      if (this.stopped) return;
      if (Number.isFinite(pending.startedAt) && Date.now() - pending.startedAt < 15 * 60 * 1000) {
        this.resultTimer = setTimeout(() => void this.observeResult(pending), 2000);
        this.resultTimer.unref();
        return;
      }
      result = {status: 'error', message: '无法确认上次更新结果，请重新检查更新。'};
    }
    await fs.unlink(this.marker).catch(() => {});
    if (result.status === 'success' && this.state.currentVersion === pending.version) {
      await this.removeStage(pending.stage);
      this.set('current');
    } else {
      this.set('error', {message: String(result.message || '安装未完成，请重新检查更新。').slice(0, 250)});
    }
  }

  async check(background = false) {
    if (!this.enabled || this.stopped || ['checking', 'downloading', 'installing'].includes(this.state.phase)
        || (background && ['ready', 'error'].includes(this.state.phase))) return this.snapshot();
    if (this.state.phase === 'ready') return this.snapshot();
    const previous = this.state;
    this.set('checking');
    try {
      const response = await fetch(RELEASE_API, {
        headers: {Accept: 'application/vnd.github+json', 'User-Agent': 'Yuki-Updater'},
        redirect: 'error',
        signal: AbortSignal.timeout(15000),
      });
      if (!response.ok) throw new Error(`GitHub HTTP ${response.status}`);
      const asset = releaseAsset(await response.json(), this.state.currentVersion);
      if (this.stopped) return this.snapshot();
      this.asset = asset;
      return asset ? this.set('available', {version: asset.version, size: asset.size}) : this.set('current');
    } catch (error) {
      if (this.stopped) return this.snapshot();
      if (background) return this.set(previous.phase, previous);
      this.asset = null;
      return this.fail(error, '检查更新失败，请稍后重试。');
    }
  }

  async download() {
    if (this.stopped || !this.asset || !['available', 'error'].includes(this.state.phase)) return this.snapshot();
    const {version, url, size, sha256, name} = this.asset;
    this.set('downloading', {version, size, progress: 0});
    const controller = new AbortController();
    this.controller = controller;
    let stage, deadline;
    const resetDeadline = () => {
      clearTimeout(deadline);
      deadline = setTimeout(() => controller.abort(), 60000);
      deadline.unref();
    };
    try {
      stage = await fs.mkdtemp(path.join(stageRoot, 'yuki-update-'));
      const archive = path.join(stage, name);
      resetDeadline();
      const response = await assetResponse(url, controller.signal);
      if (response.status !== 200 || !response.body) throw new Error(`Download HTTP ${response.status}`);
      const hash = createHash('sha256');
      let received = 0, progress = 0;
      const meter = new Transform({transform: (chunk, _encoding, callback) => {
        received += chunk.length;
        if (received > size) return callback(new UpdateError('更新包大小不符，请重新下载。'));
        hash.update(chunk);
        resetDeadline();
        const percent = Math.min(99, Math.floor(received * 100 / size));
        if (percent > progress) {
          progress = percent;
          this.set('downloading', {version, size, progress});
        }
        callback(null, chunk);
      }});
      await pipeline(Readable.fromWeb(response.body), meter, createWriteStream(archive, {flags: 'wx'}), {signal: controller.signal});
      if (received !== size || hash.digest('hex') !== sha256) throw new UpdateError('更新包校验失败，请重新下载。');
      if (this.stopped) {
        await this.removeStage(stage);
        return this.snapshot();
      }
      this.downloaded = {stage, archive, version, sha256};
      return this.set('ready', {version, size, progress: 100});
    } catch (error) {
      if (stage) await this.removeStage(stage);
      if (this.stopped) return this.snapshot();
      return this.fail(error, error.code === 'ENOSPC' ? '磁盘空间不足，清理后再试。' : '下载更新失败，请检查网络后重试。', {version, size});
    } finally {
      clearTimeout(deadline);
      this.controller = null;
    }
  }

  async install() {
    if (this.stopped || this.state.phase !== 'ready' || !this.downloaded) return this.snapshot();
    const {stage, ...download} = this.downloaded;
    this.set('installing', {version: download.version});
    try {
      const plan = path.join(stage, 'plan.json');
      const helper = path.join(stage, 'apply-update.ps1');
      await fs.access(path.dirname(this.installDir), constants.W_OK);
      await fs.copyFile(path.join(__dirname, 'apply-update.ps1'), helper);
      await fs.writeFile(plan, JSON.stringify({...download, pid: process.pid, installDir: this.installDir}));
      await fs.writeFile(this.marker, JSON.stringify({stage, version: download.version, startedAt: Date.now()}));
      if (this.stopped) throw new Error('App is exiting');
      const powershell = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32/WindowsPowerShell/v1.0/powershell.exe');
      const child = spawn(powershell, ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', helper, '-Plan', plan],
        {cwd: stage, detached: true, windowsHide: true, stdio: 'ignore'});
      await new Promise((resolve, reject) => {
        child.once('spawn', resolve);
        child.once('error', reject);
      });
      child.unref();
      this.downloaded = null;
      setImmediate(this.quit);
      return this.snapshot();
    } catch (error) {
      await fs.unlink(this.marker).catch(() => {});
      await this.removeStage(stage);
      this.downloaded = null;
      return this.fail(error, '无法启动更新程序，请重新下载后再试。', {version: download.version});
    }
  }

  removeStage(stage) {
    if (validStage(stage)) return fs.rm(stage, {recursive: true, force: true}).catch(() => {});
  }

  stop() {
    this.stopped = true;
    clearTimeout(this.initialCheck);
    clearTimeout(this.resultTimer);
    clearInterval(this.interval);
    this.controller?.abort();
    if (this.downloaded && this.state.phase !== 'installing') void this.removeStage(this.downloaded.stage);
  }
}

module.exports = {Updater};
