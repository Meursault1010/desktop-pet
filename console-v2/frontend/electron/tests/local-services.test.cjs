const {test} = require('node:test');
const assert = require('node:assert/strict');
const {discoverLocalServices, LOOPBACK} = require('../main/local-services.cjs');

const answer = (ids) => ({ok: true, json: async () => ({data: ids.map(id => ({id}))})});
const refused = () => { throw new Error('ECONNREFUSED'); };

test('only the listed loopback ports are probed and the running one is labelled', async () => {
  const urls = [];
  const services = await discoverLocalServices({fetchImpl: async url => {
    urls.push(url);
    if (url === 'http://127.0.0.1:1235/v1/models') return answer(['qwen3.8-4b', 'llama-3.2-3b']);
    throw new Error('connect refused');
  }});
  assert.ok(urls.length >= 5, 'every known local runtime gets a look');
  assert.ok(urls.every(url => LOOPBACK.test(url.replace(/\/models$/, ''))), 'nothing leaves the machine');
  const running = services.filter(service => service.running);
  assert.equal(running.length, 1);
  assert.equal(running[0].label, 'LM Studio');
  assert.deepEqual(running[0].models, ['qwen3.8-4b', 'llama-3.2-3b']);
  assert.equal(running[0].port, '1235');
  assert.equal(services.find(service => service.endpoint === 'http://127.0.0.1:11434/v1').running, false);
});

test('a hand-typed loopback endpoint joins the list once, remote ones never do', async () => {
  const urls = [];
  const fetchImpl = async url => { urls.push(url); if (url === 'http://127.0.0.1:9090/v1/models') return answer(['custom-model']); throw new Error('down'); };
  const services = await discoverLocalServices({fetchImpl, current: 'http://127.0.0.1:9090/v1'});
  assert.equal(services.filter(service => service.endpoint === 'http://127.0.0.1:9090/v1').length, 1);
  assert.equal(urls.filter(url => url.includes('9090')).length, 1, 'no duplicate probe for the same port');
  assert.equal(services[0].label, '当前配置');
  const remote = await discoverLocalServices({fetchImpl: async url => { urls.push(url); throw new Error('never'); }, current: 'https://api.example.com/v1'});
  assert.equal(urls.filter(url => url.includes('example.com')).length, 0, 'a cloud address is never probed');
  assert.equal(remote.length, 6);
});

test('the built-in model is offered with the right hint for its switch', async () => {
  const down = () => { throw new Error('down'); };
  const builtinOf = list => list.find(item => item.endpoint === 'http://127.0.0.1:1236/v1');
  const off = await discoverLocalServices({fetchImpl: down, builtinEnabled: false});
  assert.equal(builtinOf(off).running, false);
  assert.match(builtinOf(off).note, /设置 → 通用/);
  const on = await discoverLocalServices({fetchImpl: down, builtinEnabled: true});
  assert.match(builtinOf(on).note, /自动加载/);
  assert.equal(builtinOf(on).running, false);
});

test('a service that answers with an error page is not counted as running', async () => {
  const services = await discoverLocalServices({fetchImpl: async url => url.includes('8080') ? {ok: false, status: 503, json: async () => ({})} : {ok: true, json: async () => ({})}});
  assert.equal(services.find(item => item.port === '8080').running, false);
  assert.equal(services.find(item => item.port === '1235').running, true, 'an empty model list is still a live service');
  assert.deepEqual(services.find(item => item.port === '1235').models, []);
});
