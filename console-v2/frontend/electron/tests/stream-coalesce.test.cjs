const {test,mock} = require('node:test');
const assert = require('node:assert/strict');
const {coalesceUpdates} = require('../main/stream-coalesce.cjs');

test('answer frames that arrive inside the window are merged into the newest one', () => {
  mock.timers.enable({apis: ['setTimeout']});
  try {
    let time = 1000; const now = () => time; const sent = [];
    const stream = coalesceUpdates(value => sent.push(value), 140, now);
    stream.push({phase: 'answer', text: '一'});
    for (const text of ['一二', '一二三', '一二三四']) stream.push({phase: 'answer', text});
    assert.deepEqual(sent.map(value => value.text), ['一'], 'only the first frame is delivered');
    time += 140; mock.timers.tick(140);
    assert.deepEqual(sent.map(value => value.text), ['一', '一二三四'], 'the merged frame is the latest text');
    stream.flush();
    assert.equal(sent.length, 2, 'flushing an empty queue does not duplicate the last frame');
  } finally { mock.timers.reset(); }
});

test('phase changes go straight through and clear what was queued', () => {
  let time = 0; const now = () => time; const sent = [];
  const stream = coalesceUpdates(value => sent.push(`${value.phase}:${value.text}`), 140, now);
  stream.push({phase: 'thinking', text: ''});
  stream.push({phase: 'answer', text: 'a'});
  stream.push({phase: 'answer', text: 'ab'});
  time = 40; stream.push({phase: 'thinking', text: 'z'});
  assert.deepEqual(sent, ['thinking:', 'thinking:z'], 'a new phase is delivered at once and the merged text waits for the next window');
  time = 200; stream.push({phase: 'answer', text: 'c'});
  assert.deepEqual(sent[sent.length - 1], 'answer:c', 'the first answer of a new window is delivered immediately');
  stream.flush();
  assert.equal(sent.length, 3, 'the frame dropped for the phase change is not replayed');
});

test('flush delivers the pending frame and a long reply stays well under one message per delta', () => {
  mock.timers.enable({apis: ['setTimeout']});
  try {
    let time = 0; const now = () => time; const sent = [];
    const stream = coalesceUpdates(value => sent.push(value.text), 140, now);
    stream.push({phase: 'answer', text: '开始'});
    for (let frame = 1; frame <= 200; frame++) { time += 5; mock.timers.tick(5); stream.push({phase: 'answer', text: `第${frame}帧`}); }
    const before = sent.length;
    stream.flush();
    assert.equal(sent[sent.length - 1], '第200帧', 'the last frame always reaches the renderer');
    assert.ok(before <= 12, `200 deltas became ${before} IPC messages`);
    assert.equal(sent[0], '开始');
  } finally { mock.timers.reset(); }
});
