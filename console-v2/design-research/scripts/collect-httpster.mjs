import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const DATA = path.join(ROOT, 'data');
const OUT = path.join(DATA, 'httpster-sites.jsonl');
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';

const source = JSON.parse(fs.readFileSync(path.join(DATA, 'httpster.json'), 'utf8')).websites;
const done = new Set();
if (fs.existsSync(OUT)) {
  for (const line of fs.readFileSync(OUT, 'utf8').split(/\r?\n/)) {
    if (!line.trim()) continue;
    try { done.add(JSON.parse(line).slug); } catch {}
  }
}
const queue = source.filter((item) => !done.has(item.url.replace('/website/', '').replaceAll('/', '')));
console.log(`[httpster] ${source.length} listed, ${done.size} cached, ${queue.length} to fetch`);

const decode = (value = '') => value
  .replaceAll('&amp;', '&').replaceAll('&quot;', '"').replaceAll('&#39;', "'")
  .replaceAll('&lt;', '<').replaceAll('&gt;', '>').replaceAll('&nbsp;', ' ');

function parse(html, item) {
  const slug = item.url.replace('/website/', '').replaceAll('/', '');
  const siteUrl = html.match(/WebsiteView__ext"\s+href="([^"]+)"/i)?.[1] || null;
  const title = decode(html.match(/<h1[^>]*>([\s\S]*?)<\/h1>/i)?.[1]?.replace(/<[^>]+>/g, '').trim() || item.title);
  const image = html.match(/<meta\s+property="og:image"\s+content="([^"]+)"/i)?.[1] || null;
  const description = decode(html.match(/<meta\s+name="description"\s+content="([^"]*)"/i)?.[1] || '');
  const tagText = description.split(/ website design\./i)[0];
  const tags = tagText.split(/,\s*(?:and\s+)?|\s+and\s+/i).map((t) => t.trim()).filter(Boolean);
  const color = html.match(/WebsiteView__ext[^>]*>[^<]*<\/a>/i)?.[0] || '';
  return {
    slug,
    title,
    siteUrl: siteUrl ? siteUrl.replace(/[?&]ref=httpster\.net$/i, '') : null,
    image,
    description,
    tags,
    tone: item.color || null,
    source: 'httpster',
    galleryUrl: `https://httpster.net${item.url}`,
  };
}

async function fetchOne(item, attempt = 0) {
  const slug = item.url.replace('/website/', '').replaceAll('/', '');
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 18000);
    const response = await fetch(`https://httpster.net${item.url}`, {
      signal: controller.signal,
      redirect: 'follow',
      headers: { 'user-agent': UA, accept: 'text/html,application/xhtml+xml' },
    });
    clearTimeout(timer);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const html = await response.text();
    return parse(html, item);
  } catch (error) {
    if (attempt < 1) {
      await new Promise((resolve) => setTimeout(resolve, 500));
      return fetchOne(item, attempt + 1);
    }
    return { slug, title: item.title, siteUrl: null, error: String(error.message || error), source: 'httpster', galleryUrl: `https://httpster.net${item.url}` };
  }
}

let cursor = 0;
let ok = 0;
let failed = 0;
let finished = 0;
async function worker() {
  while (cursor < queue.length) {
    const item = queue[cursor++];
    const record = await fetchOne(item);
    fs.appendFileSync(OUT, `${JSON.stringify(record)}\n`);
    if (record.siteUrl) ok++; else failed++;
    finished++;
    if (finished % 100 === 0) console.log(`[httpster] ${finished}/${queue.length} ok=${ok} failed=${failed}`);
  }
}

await Promise.all(Array.from({ length: 12 }, worker));
console.log(`[httpster] done ok=${ok} failed=${failed} total=${done.size + finished}`);
