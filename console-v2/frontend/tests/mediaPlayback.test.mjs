import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mediaPosition,lyricIndex} from '../src/mediaPlayback.ts';
test('media progress respects boundaries, playback rate, paused state and stale samples',()=>{
 const m={available:true,status:'Playing',position:30,start:10,duration:90,observedAt:1000};
 assert.equal(mediaPosition(m,4000),33);assert.equal(mediaPosition({...m,status:'Paused'},4000),30);
 assert.equal(mediaPosition({...m,rate:2},4000),36);assert.equal(mediaPosition(m,100000),40);
 assert.equal(mediaPosition({...m,position:89},4000),90);
});
test('lyrics follow seek backwards, blank instrumental breaks and prelude',()=>{
 const lines=[{at:5},{at:10},{at:15}];assert.equal(lyricIndex(lines,0),-1);assert.equal(lyricIndex(lines,10),1);assert.equal(lyricIndex(lines,99),2);assert.equal(lyricIndex(lines,5),0);assert.equal(lyricIndex([],5),-1);
});
