import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const DATA = path.join(ROOT, 'data');
const OUT = path.join(ROOT, 'visual');
fs.mkdirSync(path.join(OUT, 'thumbs'), { recursive: true });
fs.mkdirSync(path.join(OUT, 'sheets'), { recursive: true });

const corpus = JSON.parse(fs.readFileSync(path.join(DATA, 'corpus.json'), 'utf8')).filter((item) => item.image && item.source === 'httpster');
const groups = [
  { name: 'software', match: (item) => item.tags.includes('Application / Software') || item.tags.includes('Product'), count: 30 },
  { name: 'minimal', match: (item) => item.tags.includes('Minimal'), count: 30 },
  { name: 'typographic', match: (item) => item.tags.includes('Typographic'), count: 30 },
  { name: 'dark', match: (item) => item.tags.includes('Dark'), count: 30 },
  { name: 'grid', match: (item) => item.tags.includes('Grid'), count: 30 },
  { name: 'colourful', match: (item) => item.tags.includes('Colourful'), count: 30 },
  { name: 'commerce-fashion', match: (item) => item.tags.includes('Ecommerce') || item.tags.includes('Fashion'), count: 30 },
  { name: 'editorial', match: (item) => item.tags.includes('Design & Illustration') || item.tags.includes('Art & Photography') || item.tags.includes('Photographic'), count: 30 },
];

function mulberry32(seed) {
  return function random() {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const random = mulberry32(20261023);
const shuffle = (items) => {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i--) { const j = Math.floor(random() * (i + 1)); [copy[i], copy[j]] = [copy[j], copy[i]]; }
  return copy;
};

const pools = new Map(groups.map((group) => [group.name, shuffle(corpus.filter(group.match))]));
const selected = [], used = new Set();
const cursors = new Map(groups.map((group) => [group.name, 0]));
let added = true;
while (added && selected.length < 240) {
  added = false;
  for (const group of groups) {
    if (selected.filter((s) => s.group === group.name).length >= group.count) continue;
    const pool = pools.get(group.name);
    let cursor = cursors.get(group.name);
    while (cursor < pool.length && used.has(pool[cursor].host)) cursor++;
    const item = pool[cursor++];
    cursors.set(group.name, cursor);
    if (!item) continue;
    used.add(item.host);
    selected.push({ ...item, group: group.name, index: selected.length + 1 });
    added = true;
    if (selected.length >= 240) break;
  }
}

fs.writeFileSync(path.join(OUT, 'index.json'), JSON.stringify(selected, null, 2));
console.log('selected', selected.length, 'by group', Object.fromEntries(groups.map((g) => [g.name, selected.filter((s) => s.group === g.name).length])));

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';
let cursor = 0, ok = 0, failed = 0;
async function worker() {
  while (cursor < selected.length) {
    const item = selected[cursor++];
    const target = path.join(OUT, 'thumbs', `${String(item.index).padStart(3, '0')}.jpg`);
    if (fs.existsSync(target) && fs.statSync(target).size > 1000) { ok++; continue; }
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 25000);
      const response = await fetch(item.image.replace('httpster.net//', 'httpster.net/'), { signal: controller.signal, headers: { 'user-agent': UA, accept: 'image/jpeg,image/*' } });
      clearTimeout(timer);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const buffer = Buffer.from(await response.arrayBuffer());
      if (buffer.length < 1000) throw new Error('empty image');
      fs.writeFileSync(target, buffer);
      ok++;
    } catch (error) {
      failed++;
      console.log(`[thumb] ${item.index} ${item.host} failed ${error.message}`);
    }
    if ((ok + failed) % 30 === 0) console.log(`[thumb] ${ok + failed}/${selected.length} ok=${ok} failed=${failed}`);
  }
}
await Promise.all(Array.from({ length: 10 }, worker));
console.log(`[thumb] done ok=${ok} failed=${failed}`);
