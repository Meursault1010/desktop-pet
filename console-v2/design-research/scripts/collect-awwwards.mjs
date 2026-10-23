import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const OUT = path.join(ROOT, 'data', 'awwwards-sites.jsonl');
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';
const targets = [
  ...Array.from({ length: 22 }, (_, i) => ({ url: `https://www.awwwards.com/websites/?page=${i + 1}`, category: 'general' })),
  ...Array.from({ length: 8 }, (_, i) => ({ url: `https://www.awwwards.com/websites/ui-design/?page=${i + 1}`, category: 'ui-design' })),
  ...Array.from({ length: 4 }, (_, i) => ({ url: `https://www.awwwards.com/websites/react/?page=${i + 1}`, category: 'react' })),
  ...Array.from({ length: 4 }, (_, i) => ({ url: `https://www.awwwards.com/websites/mobile-apps/?page=${i + 1}`, category: 'mobile-apps' })),
  ...Array.from({ length: 4 }, (_, i) => ({ url: `https://www.awwwards.com/websites/business-corporate/?page=${i + 1}`, category: 'business' })),
  ...Array.from({ length: 2 }, (_, i) => ({ url: `https://www.awwwards.com/websites/design-agencies/?page=${i + 1}`, category: 'agency' })),
  ...Array.from({ length: 2 }, (_, i) => ({ url: `https://www.awwwards.com/websites/portfolio/?page=${i + 1}`, category: 'portfolio' })),
  ...Array.from({ length: 2 }, (_, i) => ({ url: `https://www.awwwards.com/websites/e-commerce/?page=${i + 1}`, category: 'commerce' })),
];

const blocked = /(awwwards\.com|fonts\.|cdn\.|twitter\.com|x\.com|facebook\.com|instagram\.com|linkedin\.com|google\.com|apple\.com|youtube\.com|cloudflare\.com|typekit\.com|adobe\.com|googletagmanager|shopify\.com\/apps|sentry\.io|unsplash\.com|vimeo\.com|dribbble\.com|behance\.net|github\.com\/awwwards|medium\.com|t\.me|discord\.)/i;

async function fetchPage(target) {
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 25000);
      const response = await fetch(target.url, {
        signal: controller.signal,
        headers: { 'user-agent': UA, accept: 'text/html,application/xhtml+xml', 'accept-language': 'en-US,en;q=0.8' },
      });
      clearTimeout(timer);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const html = await response.text();
      const links = [...html.matchAll(/href="(https?:\/\/[^"]+)"/g)]
        .map((match) => match[1].replaceAll('&amp;', '&'))
        .filter((url) => !blocked.test(url))
        .map((url) => url.replace(/[?#].*$/, ''));
      return [...new Set(links)];
    } catch (error) {
      if (attempt === 1) return { error: String(error.message || error) };
      await new Promise((resolve) => setTimeout(resolve, 800));
    }
  }
}

const rows = [];
let cursor = 0;
async function worker() {
  while (cursor < targets.length) {
    const index = cursor++;
    const target = targets[index];
    const result = await fetchPage(target);
    if (Array.isArray(result)) {
      for (const siteUrl of result) rows.push({ siteUrl, category: target.category, source: 'awwwards', page: target.url });
      console.log(`[awwwards] ${index + 1}/${targets.length} ${target.category} +${result.length}`);
    } else {
      console.log(`[awwwards] ${index + 1}/${targets.length} ${target.category} FAIL ${result.error}`);
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
}
await Promise.all(Array.from({ length: 3 }, worker));
fs.writeFileSync(OUT, rows.map((row) => JSON.stringify(row)).join('\n') + '\n');
const unique = new Set(rows.map((row) => row.siteUrl));
console.log(`[awwwards] done ${rows.length} links, ${unique.size} unique`);
