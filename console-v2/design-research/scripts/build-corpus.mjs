import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const DATA = path.join(ROOT, 'data');
const TARGET_GALLERY = 1150;

const curated = JSON.parse(fs.readFileSync(path.join(DATA, 'curated-products.json'), 'utf8'));
const httpster = fs.existsSync(path.join(DATA, 'httpster-sites.jsonl'))
  ? fs.readFileSync(path.join(DATA, 'httpster-sites.jsonl'), 'utf8').split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line))
  : [];
const awwwards = fs.existsSync(path.join(DATA, 'awwwards-sites.jsonl'))
  ? fs.readFileSync(path.join(DATA, 'awwwards-sites.jsonl'), 'utf8').split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line))
  : [];

const STYLE_TAGS = new Set([
  'Minimal', 'Typographic', 'Grid', 'Dark', 'Light', 'Colourful', 'Interactive', 'Motion',
  'Unusual Layout', 'Unusual Navigation', 'Responsive', 'Photographic', 'Design & Illustration',
  'Ecommerce', 'Editorial', 'Magazine', 'Blog', 'Service', 'Education', 'Architecture & Industrial Design',
  'Art & Photography', 'Fashion', 'Food & Drink', 'Music', 'Event', 'Showcase', 'Fullscreen',
  'Illustrative', 'Monotone', 'Brutalist', 'Retro', 'Print',
]);
const TYPE_TAGS = new Set(['Application / Software', 'Product', 'Inspiration / Resource']);
const BLOCKED_HOSTS = new Set([
  'facebook.com', 'instagram.com', 'x.com', 'twitter.com', 'linkedin.com', 'youtube.com', 'vimeo.com',
  'pinterest.com', 'tiktok.com', 'behance.net', 'dribbble.com', 'medium.com', 'tumblr.com',
  'google.com', 'apple.com', 'spotify.com', 'soundcloud.com', 'github.com', 'gitlab.com',
  'httpster.net', 'awwwards.com', 'godly.website', 'land-book.com', 'typeform.com', 'notion.so',
]);

function normalize(raw) {
  if (!raw || !/^https?:\/\//i.test(raw)) return null;
  try {
    const url = new URL(raw);
    const host = url.hostname.toLowerCase().replace(/^www\./, '');
    if (!host.includes('.')) return null;
    let pathname = url.pathname.replace(/\/+$/, '') || '/';
    return { host, path: pathname, url: `https://${host}${pathname}` };
  } catch {
    return null;
  }
}

function mulberry32(seed) {
  return function random() {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const isBlockedGalleryHost = (host) => BLOCKED_HOSTS.has(host);
const random = mulberry32(20261023);
const shuffle = (items) => {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
};

const selected = [];
const usedHosts = new Set();
const usedUrls = new Set();

for (const item of curated) {
  const normalized = normalize(item.url);
  if (!normalized || usedHosts.has(normalized.host)) continue;
  usedHosts.add(normalized.host);
  usedUrls.add(normalized.url);
  selected.push({
    id: `c${String(selected.length + 1).padStart(4, '0')}`,
    ...normalized,
    title: item.name,
    source: 'curated',
    category: item.category,
    tags: [item.category],
  });
}

const galleryPool = [];
for (const row of httpster) {
  if (!row.siteUrl) continue;
  const normalized = normalize(row.siteUrl);
  if (!normalized || usedHosts.has(normalized.host) || isBlockedGalleryHost(normalized.host)) continue;
  const tags = (row.tags || []).filter((tag) => STYLE_TAGS.has(tag) || TYPE_TAGS.has(tag));
  galleryPool.push({
    ...normalized,
    title: row.title,
    source: 'httpster',
    category: TYPE_TAGS.has(tags[0]) ? 'software' : 'website',
    tags,
    tone: row.tone,
    image: row.image,
  });
}

const seenGallery = new Set();
const uniqueGallery = [];
for (const item of shuffle(galleryPool)) {
  if (seenGallery.has(item.host)) continue;
  seenGallery.add(item.host);
  uniqueGallery.push(item);
}

const priorityTags = ['Application / Software', 'Product', 'Minimal', 'Typographic', 'Grid', 'Dark', 'Interactive', 'Motion'];
const buckets = new Map();
for (const tag of priorityTags) {
  buckets.set(tag, uniqueGallery.filter((item) => item.tags.includes(tag)));
}
const priority = [];
const prioritySeen = new Set();
const bucketOrder = priorityTags.map((tag) => ({ tag, items: buckets.get(tag), index: 0 }));
let added = true;
while (added && priority.length < 650) {
  added = false;
  for (const bucket of bucketOrder) {
    while (bucket.index < bucket.items.length) {
      const item = bucket.items[bucket.index++];
      if (prioritySeen.has(item.host)) continue;
      prioritySeen.add(item.host);
      priority.push(item);
      added = true;
      break;
    }
    if (priority.length >= 650) break;
  }
}

const remainder = uniqueGallery.filter((item) => !prioritySeen.has(item.host));
const chosenGallery = [...priority, ...shuffle(remainder)];
for (const item of chosenGallery) {
  if (selected.length >= TARGET_GALLERY + curated.length) break;
  if (usedUrls.has(item.url)) continue;
  usedUrls.add(item.url);
  usedHosts.add(item.host);
  selected.push({
    id: `g${String(selected.length + 1).padStart(4, '0')}`,
    ...item,
  });
}

for (const row of awwwards) {
  if (selected.length >= TARGET_GALLERY + curated.length + 250) break;
  const normalized = normalize(row.siteUrl);
  if (!normalized || usedHosts.has(normalized.host) || isBlockedGalleryHost(normalized.host)) continue;
  usedHosts.add(normalized.host);
  selected.push({
    id: `a${String(selected.length + 1).padStart(4, '0')}`,
    ...normalized,
    title: normalized.host,
    source: 'awwwards',
    category: row.category || 'award',
    tags: [row.category].filter(Boolean),
  });
}

fs.writeFileSync(path.join(DATA, 'corpus.json'), JSON.stringify(selected, null, 2));
const stats = {
  total: selected.length,
  bySource: selected.reduce((acc, item) => ((acc[item.source] = (acc[item.source] || 0) + 1), acc), {}),
  byCategory: selected.reduce((acc, item) => ((acc[item.category] = (acc[item.category] || 0) + 1), acc), {}),
  galleryTagCounts: priorityTags.reduce((acc, tag) => ((acc[tag] = buckets.get(tag).length), acc), {}),
  uniqueGalleryHosts: uniqueGallery.length,
};
fs.writeFileSync(path.join(DATA, 'corpus-summary.json'), JSON.stringify(stats, null, 2));
console.log(JSON.stringify(stats, null, 2));
console.log('wrote', path.join(DATA, 'corpus.json'));
