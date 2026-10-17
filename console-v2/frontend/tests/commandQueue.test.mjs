import test from 'node:test';
import assert from 'node:assert/strict';
import { CommandQueue, parseSettingNumber } from '../src/commandQueue.ts';
const gate = () => { let release; const promise = new Promise(resolve => { release = resolve; }); return { promise, release }; };

test('slider changes keep the last queued value without losing other preferences', async () => {
  const queue = new CommandQueue(); const hold = gate(); const calls = [];
  const first = queue.enqueue('size', async () => { calls.push(110); await hold.promise; return 110; }, true);
  const second = queue.enqueue('size', async () => { calls.push(120); return 120; }, true);
  const other = queue.enqueue('opacity', async () => { calls.push('opacity'); return 80; }, true);
  const last = queue.enqueue('size', async () => { calls.push(150); return 150; }, true);
  assert.equal(second, last); hold.release();
  assert.deepEqual(await Promise.all([first, second, other, last]), [110, 150, 80, 150]);
  assert.deepEqual(calls, [110, 150, 'opacity']);
});
test('duplicate actions execute only once while pending', async () => {
  const queue = new CommandQueue(); const hold = gate(); let calls = 0;
  const first = queue.enqueue('jump', async () => { calls++; await hold.promise; return true; });
  const second = queue.enqueue('jump', async () => { calls++; return true; });
  assert.equal(first, second); hold.release(); await second; assert.equal(calls, 1);
});
test('reset stays between earlier and later preferences', async () => {
  const queue = new CommandQueue(); const hold = gate(); const calls = [];
  const first = queue.enqueue('active', async () => { await hold.promise; });
  const before = queue.enqueue('size', async () => { calls.push(150); }, true);
  const reset = queue.enqueue('reset', async () => { calls.push('reset'); });
  const after = queue.enqueue('size', async () => { calls.push(90); }, true);
  hold.release(); await Promise.all([first, before, reset, after]); assert.deepEqual(calls, [150, 'reset', 90]);
});
test('failure does not block the next operation and pending status clears', async () => {
  const queue = new CommandQueue(); const keys = []; queue.onChange = value => keys.push(value);
  const failed = queue.enqueue('bad', async () => { throw Error('offline'); });
  const next = queue.enqueue('good', async () => 42);
  await assert.rejects(failed, /offline/); assert.equal(await next, 42); assert.deepEqual(keys.at(-1), []);
});
test('disconnect cancels unsent operations', async () => {
  const queue = new CommandQueue(); const hold = gate(); let called = false;
  const first = queue.enqueue('active', async () => { await hold.promise; });
  const pending = queue.enqueue('next', async () => { called = true; });
  queue.cancelPending(Error('disconnected')); await assert.rejects(pending, /disconnected/);
  hold.release(); await first; assert.equal(called, false);
});
test('numeric settings accept only bounded integers', () => {
  for (const text of ['', ' ', 'abc', '49', '201', '99.5', 'Infinity']) assert.equal(parseSettingNumber(text, 50, 200), null);
  assert.equal(parseSettingNumber('50', 50, 200), 50); assert.equal(parseSettingNumber('200', 50, 200), 200);
});
