import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loopPosition} from '../src/actionTimeline.ts';
test('take-out intro plays once and loop keeps device held',()=>{
  assert.equal(loopPosition(50,[100,200,300],1),50);
  assert.equal(loopPosition(600,[100,200,300],1),100);
  assert.equal(loopPosition(1100,[100,200,300],1),100);
  for(let t=600;t<10000;t+=37)assert.ok(loopPosition(t,[100,200,300],1)>=100);
});
test('ordinary actions still loop from frame zero',()=>{
  assert.equal(loopPosition(650,[100,200,300]),50);
});
