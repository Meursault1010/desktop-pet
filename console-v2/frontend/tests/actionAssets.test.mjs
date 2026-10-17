import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';

test('action catalog is bundled, not dependent on runtime fetch', () => {
  const source=readFileSync('src/components/ActionLibrary.tsx','utf8');
  assert.match(source,/import bundledCatalog from/);
  assert.doesNotMatch(source,/fetch\(/);
});
test('all catalog posters and atlases are packaged and schedules match', () => {
  const catalog=JSON.parse(readFileSync('public/actions/catalog.json','utf8'));
  assert.equal(catalog.length,31);
  for(const action of catalog){
    assert.ok(existsSync(resolve('public',action.atlas)),action.id);
    assert.ok(existsSync(resolve('public',action.poster)),action.id);
    assert.equal(action.durations.length,action.frames);
  }
});
test('release security policy permits same-origin local resources', () => {
  const config=JSON.parse(readFileSync('src-tauri/tauri.conf.json','utf8'));
  assert.match(config.app.security.csp,/connect-src 'self'/);
});
