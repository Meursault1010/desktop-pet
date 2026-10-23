import {test} from 'node:test';
import assert from 'node:assert/strict';
import {normalizeOrder,moveItem} from '../src/sortOrder.ts';
test('saved order rejects malformed, duplicate and removed ids and appends new entries',()=>{
 assert.deepEqual(normalizeOrder(['b','gone','b',null],['a','b','c']),['b','a','c']);
 for(const saved of [null,{},42,'bad'])assert.deepEqual(normalizeOrder(saved,['a','b']),['a','b']);
});
test('moves preserve stable identities, content and original array',()=>{
 const ids=['overview','character','assistant','tools','settings'];
 assert.deepEqual(moveItem(ids,'settings','overview'),['settings','overview','character','assistant','tools']);
 assert.deepEqual(moveItem(ids,'overview','settings'),['character','assistant','tools','settings','overview']);
 assert.deepEqual(moveItem(ids,'missing','tools'),ids);
 assert.equal(ids[0],'overview');
});
