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
  assert.equal(catalog.filter(action=>!action.physics_only).length,36);
  assert.equal(new Set(catalog.map(action=>action.id)).size,catalog.length);
  assert.deepEqual(catalog.filter(action=>action.id.includes('roll')).map(action=>action.id).sort(),['lazy-roll-away','lazy-roll-toward']);
  for(const action of catalog){
    assert.ok(existsSync(resolve('public',action.atlas)),action.id);
    assert.ok(existsSync(resolve('public',action.poster)),action.id);
    assert.equal(action.durations.length,action.frames);
    if(action.physics_only)assert.equal(action.category,'物理互动');
  }
  assert.deepEqual(catalog.filter(action=>action.physics_only).map(action=>action.id).sort(),
    ['impact-ceiling','impact-floor','impact-left','impact-right','throw-flight']);
});
test('release security policy permits same-origin local resources', () => {
  const config=JSON.parse(readFileSync('src-tauri/tauri.conf.json','utf8'));
  assert.match(config.app.security.csp,/connect-src 'self'/);
});
