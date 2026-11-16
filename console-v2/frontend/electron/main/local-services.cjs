'use strict';
// A local inference server needs neither a URL nor a key, so the settings page asks the
// main process what is already listening. Only these loopback addresses are ever probed:
// there is no port scanning and nothing leaves this machine.
const LOCAL_SERVICES = [
  { label: 'LM Studio', endpoint: 'http://127.0.0.1:1235/v1' },
  { label: 'LM Studio（备用端口）', endpoint: 'http://127.0.0.1:1234/v1' },
  { label: '内置 Qwen', endpoint: 'http://127.0.0.1:1236/v1', builtin: true },
  { label: 'Ollama', endpoint: 'http://127.0.0.1:11434/v1' },
  { label: 'llama.cpp server', endpoint: 'http://127.0.0.1:8080/v1' },
  { label: 'GPT4All', endpoint: 'http://127.0.0.1:4899/v1' },
];
const LOOPBACK = /^http:\/\/(127\.0\.0\.1|localhost|\[::1\])(:\d{2,5})?\/v1$/;

function portOf(endpoint) { const match = /:(\d{2,5})\//.exec(endpoint); return match ? match[1] : ''; }

async function probe(target, fetchImpl, timeout) {
  if (!LOOPBACK.test(target.endpoint)) throw new Error('只允许探测本机地址');
  const response = await fetchImpl(target.endpoint + '/models', { signal: AbortSignal.timeout(timeout), redirect: 'error', headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error('HTTP ' + response.status);
  const data = await response.json();
  const models = (Array.isArray(data?.data) ? data.data : [])
    .map(item => String(item?.id || item?.name || '').trim()).filter(Boolean).slice(0, 40);
  return models;
}

// `current` is the saved endpoint: a hand-typed loopback port is worth keeping in the list.
async function discoverLocalServices({ fetchImpl = fetch, timeout = 1500, current = '', builtinEnabled = false } = {}) {
  const wanted = [...LOCAL_SERVICES];
  if (LOOPBACK.test(String(current || ''))) wanted.unshift({ label: '当前配置', endpoint: current });
  const seen = new Set();
  const targets = wanted.filter(item => !seen.has(item.endpoint) && seen.add(item.endpoint));
  return Promise.all(targets.map(async target => {
    const base = { label: target.label, endpoint: target.endpoint, port: portOf(target.endpoint), builtin: target.builtin === true, running: false, models: [], note: '' };
    try {
      const models = await probe(target, fetchImpl, timeout);
      return { ...base, running: true, models };
    } catch {
      return { ...base, note: base.builtin ? (builtinEnabled ? '未启动，选用后会自动加载' : '需要先在设置 → 通用里开启内置模型') : '' };
    }
  }));
}

module.exports = { discoverLocalServices, LOCAL_SERVICES, LOOPBACK };
