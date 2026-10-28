import {test} from 'node:test';
import assert from 'node:assert/strict';
import {liveStatusView} from '../src/activityStatus.ts';

const snapshot={status:'移动中',activity:{key:'walking',label:'移动中',detail:'正走向目的地',posture:null}};

test('connected workbench mirrors the backend activity descriptor',()=>{
 assert.deepEqual(liveStatusView(snapshot,true,false),{key:'walking',label:'移动中',detail:'正走向目的地',live:true});
});

test('legacy snapshots without an activity still show the shared status text',()=>{
 assert.deepEqual(liveStatusView({status:'安静模式'},true,false),{key:'pending',label:'安静模式',detail:'',live:true});
});

test('a lost connection never presents the last known state as current',()=>{
 assert.deepEqual(liveStatusView(snapshot,false,false),{key:'offline',label:'桌宠未连接',detail:'状态暂时无法同步',live:false});
 assert.deepEqual(liveStatusView(snapshot,false,true),{key:'connecting',label:'正在连接桌宠…',detail:'等待桌面宠物响应',live:false});
});

test('browser preview is labeled as a preview instead of live data',()=>{
 assert.deepEqual(liveStatusView(snapshot,true,false,true),{key:'preview',label:'移动中',detail:'界面预览，不连接真实宠物',live:false});
});
