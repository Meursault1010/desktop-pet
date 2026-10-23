import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const DATA = path.join(ROOT, 'data');
const CORPUS = JSON.parse(fs.readFileSync(process.env.CORPUS_FILE || path.join(DATA, 'corpus.json'), 'utf8'));
const OUT = process.env.FEATURES_FILE || path.join(DATA, 'page-features.jsonl');
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';
const MAX_HTML = 3_000_000;
const MAX_CSS_TOTAL = 3_000_000;
const MAX_CSS_FILE = 1_400_000;
const TIMEOUT = 20000;
const CONCURRENCY = Math.max(1, Number(process.env.CONCURRENCY || 6));

const done = new Set();
for (const file of [process.env.DONE_FILE, OUT].filter(Boolean)) {
  if (!fs.existsSync(file)) continue;
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    if (!line.trim()) continue;
    try { const record = JSON.parse(line); if (record.id) done.add(record.id); } catch {}
  }
}
const queue = CORPUS.filter((item) => !done.has(item.id));
if (process.env.REVERSE === '1') queue.reverse();
console.log(`[analyze] corpus=${CORPUS.length} done=${done.size} queue=${queue.length}${process.env.REVERSE === '1' ? ' reverse' : ''}`);

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
const round = (value, digits = 0) => Number(value.toFixed(digits));
const topEntries = (map, limit = 12) => [...map.entries()].sort((a, b) => b[1] - a[1]).slice(0, limit);

function decodeEntities(value = '') {
  return value
    .replaceAll('&amp;', '&').replaceAll('&quot;', '"').replaceAll('&#39;', "'")
    .replaceAll('&apos;', "'").replaceAll('&lt;', '<').replaceAll('&gt;', '>')
    .replaceAll('&nbsp;', ' ').replace(/&#(\d+);/g, (_, code) => String.fromCodePoint(Number(code)))
    .replace(/&#x([0-9a-f]+);/gi, (_, code) => String.fromCodePoint(parseInt(code, 16)));
}
const stripTags = (value = '') => decodeEntities(value.replace(/<script[\s\S]*?<\/script>/gi, ' ').replace(/<style[\s\S]*?<\/style>/gi, ' ').replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ').trim();
const firstMatch = (text, regex) => text.match(regex)?.[1]?.trim() || '';

function normalizeHost(host) {
  return host.toLowerCase().replace(/^www\./, '');
}

const NAMED_COLORS = {
  white: '#ffffff', black: '#000000', gray: '#808080', grey: '#808080', silver: '#c0c0c0',
  red: '#ff0000', maroon: '#800000', orange: '#ffa500', yellow: '#ffff00', olive: '#808000',
  lime: '#00ff00', green: '#008000', teal: '#008080', aqua: '#00ffff', cyan: '#00ffff',
  blue: '#0000ff', navy: '#000080', fuchsia: '#ff00ff', magenta: '#ff00ff', purple: '#800080',
  pink: '#ffc0cb', brown: '#a52a2a', beige: '#f5f5dc', ivory: '#fffff0', gold: '#ffd700',
};
function oklchToRgb(l, c, h) {
  const hr = (h * Math.PI) / 180;
  const a = c * Math.cos(hr), b = c * Math.sin(hr);
  const l_ = l + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = l - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = l - 0.0894841775 * a - 1.291485548 * b;
  const L = l_ ** 3, M = m_ ** 3, S = s_ ** 3;
  const linear = [
    4.0767416621 * L - 3.3077115913 * M + 0.2309699292 * S,
    -1.2684380046 * L + 2.6097574011 * M - 0.3413193965 * S,
    -0.0041960863 * L - 0.7034186147 * M + 1.707614701 * S,
  ];
  return linear.map((value) => {
    const gamma = value <= 0.0031308 ? 12.92 * value : 1.055 * Math.abs(value) ** (1 / 2.4) * Math.sign(value) - 0.055 * Math.sign(value);
    return clamp(Math.round(gamma * 255), 0, 255);
  });
}
function parseColor(token) {
  if (!token) return null;
  const value = token.trim().toLowerCase();
  if (value === 'transparent' || value === 'currentcolor' || value === 'inherit' || value === 'none') return null;
  if (NAMED_COLORS[value]) {
    const hex = NAMED_COLORS[value];
    return { hex, alpha: 1, r: parseInt(hex.slice(1, 3), 16), g: parseInt(hex.slice(3, 5), 16), b: parseInt(hex.slice(5, 7), 16) };
  }
  let match;
  if ((match = value.match(/^oklch\(\s*([\d.]+)(%?)\s+([\d.]+)(%?)\s+([\d.]+)(?:deg)?(?:\s*\/\s*([\d.]+)(%?))?\s*\)$/))) {
    const l = parseFloat(match[1]) / (match[2] === '%' || parseFloat(match[1]) > 1 ? 100 : 1);
    const c = parseFloat(match[3]) / (match[4] === '%' ? 100 : 1);
    const alpha = match[6] ? (match[7] === '%' ? parseFloat(match[6]) / 100 : parseFloat(match[6])) : 1;
    if (alpha < 0.02) return null;
    const [r, g, b] = oklchToRgb(clamp(l, 0, 1), c, parseFloat(match[5]));
    return { hex: `#${[r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('')}`, alpha, r, g, b };
  }
  if ((match = value.match(/^#([0-9a-f]{3,8})$/))) {
    let hex = match[1];
    if (hex.length === 3) hex = [...hex].map((c) => c + c).join('');
    if (hex.length === 4) hex = hex.slice(0, 3).split('').map((c) => c + c).join('') + hex[3] + hex[3];
    if (hex.length !== 6 && hex.length !== 8) return null;
    const alpha = hex.length === 8 ? parseInt(hex.slice(6, 8), 16) / 255 : 1;
    if (alpha < 0.02) return null;
    return { hex: `#${hex.slice(0, 6)}`, alpha, r: parseInt(hex.slice(0, 2), 16), g: parseInt(hex.slice(2, 4), 16), b: parseInt(hex.slice(4, 6), 16) };
  }
  if ((match = value.match(/^rgba?\(\s*([\d.]+%?)[\s,]+([\d.]+%?)[\s,]+([\d.]+%?)(?:[\s,/]+([\d.]+%?))?\s*\)$/))) {
    const channel = (raw) => raw.endsWith('%') ? Math.round(parseFloat(raw) * 2.55) : Math.round(parseFloat(raw));
    const r = clamp(channel(match[1]), 0, 255), g = clamp(channel(match[2]), 0, 255), b = clamp(channel(match[3]), 0, 255);
    const alpha = match[4] ? (match[4].endsWith('%') ? parseFloat(match[4]) / 100 : parseFloat(match[4])) : 1;
    if (alpha < 0.02) return null;
    return { hex: `#${[r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('')}`, alpha, r, g, b };
  }
  if ((match = value.match(/^hsla?\(\s*([\d.]+)(?:deg)?[\s,]+([\d.]+)%?[\s,]+([\d.]+)%?(?:[\s,/]+([\d.]+%?))?\s*\)$/))) {
    const h = ((parseFloat(match[1]) % 360) + 360) % 360;
    const s = clamp(parseFloat(match[2]) / 100, 0, 1), l = clamp(parseFloat(match[3]) / 100, 0, 1);
    const alpha = match[4] ? (match[4].endsWith('%') ? parseFloat(match[4]) / 100 : parseFloat(match[4])) : 1;
    if (alpha < 0.02) return null;
    const c = (1 - Math.abs(2 * l - 1)) * s, x = c * (1 - Math.abs(((h / 60) % 2) - 1)), m = l - c / 2;
    let rgb;
    if (h < 60) rgb = [c, x, 0]; else if (h < 120) rgb = [x, c, 0]; else if (h < 180) rgb = [0, c, x];
    else if (h < 240) rgb = [0, x, c]; else if (h < 300) rgb = [x, 0, c]; else rgb = [c, 0, x];
    const [r, g, b] = rgb.map((v) => Math.round((v + m) * 255));
    return { hex: `#${[r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('')}`, alpha, r, g, b };
  }
  return null;
}
function colorInfo({ r, g, b }) {
  const rn = r / 255, gn = g / 255, bn = b / 255;
  const max = Math.max(rn, gn, bn), min = Math.min(rn, gn, bn), delta = max - min;
  const l = (max + min) / 2;
  const s = delta === 0 ? 0 : delta / (1 - Math.abs(2 * l - 1));
  let h = 0;
  if (delta !== 0) {
    if (max === rn) h = ((gn - bn) / delta) % 6;
    else if (max === gn) h = (bn - rn) / delta + 2;
    else h = (rn - gn) / delta + 4;
    h = (h * 60 + 360) % 360;
  }
  const neutral = s < 0.12 || l < 0.07 || l > 0.96;
  let hueBucket = null;
  if (!neutral && s >= 0.18) {
    if (h < 15 || h >= 345) hueBucket = 'red';
    else if (h < 45) hueBucket = 'orange';
    else if (h < 70) hueBucket = 'yellow';
    else if (h < 160) hueBucket = 'green';
    else if (h < 200) hueBucket = 'cyan';
    else if (h < 260) hueBucket = 'blue';
    else if (h < 300) hueBucket = 'violet';
    else hueBucket = 'magenta';
  }
  return { h: round(h), s: round(s, 3), l: round(l, 3), neutral, hueBucket };
}
function parseCssLength(raw) {
  if (!raw) return null;
  const value = raw.trim().toLowerCase();
  const match = value.match(/^(-?[\d.]+)(px|rem|em|pt|vw|vh|%)?$/);
  if (!match) return null;
  const number = parseFloat(match[1]);
  const unit = match[2] || 'px';
  if (unit === 'px' || unit === 'pt') return { px: number * (unit === 'pt' ? 1.333 : 1), raw: value, unit };
  if (unit === 'rem' || unit === 'em') return { px: number * 16, raw: value, unit };
  return { px: null, raw: value, unit };
}

function extractCssSignals(css) {
  const clean = css.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/@font-face\s*{[\s\S]*?}/gi, ' ').replace(/url\([^)]*\)/gi, 'url()');
  const colors = new Map(), backgroundColors = new Map(), textColors = new Map();
  const namedColorPattern = '(?<![\\w-])(?:white|black|gray|grey|silver|red|maroon|orange|yellow|olive|lime|green|teal|aqua|cyan|blue|navy|fuchsia|magenta|purple|pink|brown|beige|ivory|gold)(?![\\w-])';
  const colorRegex = new RegExp(`#[0-9a-f]{3,8}\\b|rgba?\\([^)]*\\)|hsla?\\([^)]*\\)|oklch\\([^)]*\\)|${namedColorPattern}`, 'gi');
  for (const raw of clean.match(colorRegex) || []) {
    const parsed = parseColor(raw);
    if (parsed) colors.set(parsed.hex, (colors.get(parsed.hex) || 0) + 1);
  }
  for (const rule of clean.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const body = rule[2];
    for (const declaration of body.matchAll(/(?:^|;)\s*(background(?:-color)?|color)\s*:\s*([^;]+)/gi)) {
      const property = declaration[1].toLowerCase();
      for (const raw of declaration[2].match(colorRegex) || []) {
        const parsed = parseColor(raw);
        if (!parsed) continue;
        const target = property === 'color' ? textColors : backgroundColors;
        target.set(parsed.hex, (target.get(parsed.hex) || 0) + 1);
      }
    }
  }

  const fonts = new Map(), fontStacks = new Map(), googleFamilies = new Map();
  const cssVars = new Map();
  for (const declaration of clean.matchAll(/--([\w-]+)\s*:\s*([^;}]+)/g)) cssVars.set(declaration[1], declaration[2].trim());
  const resolveVars = (value) => value.replace(/var\(\s*--([\w-]+)\s*(?:,\s*([^)]+))?\)/g, (_, name, fallback) => cssVars.get(name) || fallback || '');
  const validFamily = (name) => {
    if (!name || name.length > 60) return false;
    if (/^(var\(|inherit|initial|unset|revert|normal|none|auto|--)/.test(name)) return false;
    if (/^[\d.]+(px|rem|em|%|vw|vh)?$/.test(name)) return false;
    if (/^wfont_/.test(name)) return false;
    if (/["']\s*\d/.test(name)) return false;
    if (/\d+(?:px|rem|em)\b/.test(name)) return false;
    return true;
  };
  for (const declaration of clean.matchAll(/font-family\s*:\s*([^;}]+)/gi)) {
    const resolved = resolveVars(declaration[1]);
    const families = resolved.split(',').map((part) => part.trim().replace(/^['"]|['"]$/g, '').toLowerCase()).filter(Boolean);
    if (!families.length) continue;
    const primary = families[0];
    if (validFamily(primary)) fonts.set(primary, (fonts.get(primary) || 0) + 1);
    const stack = families.slice(0, 3).join(', ');
    fontStacks.set(stack, (fontStacks.get(stack) || 0) + 1);
  }
  for (const declaration of clean.matchAll(/(?<![\w-])font\s*:\s*([^;}]+)/gi)) {
    const segment = declaration[1].split(',')[0].replace(/^.*?\d+(?:px|rem|em|%|pt)(?:\s*\/\s*[^ ]+)?\s*/i, '').trim().replace(/^['"]|['"]$/g, '').toLowerCase();
    if (validFamily(segment)) fonts.set(segment, (fonts.get(segment) || 0) + 1);
  }
  for (const declaration of clean.matchAll(/--[\w-]*(?:font-family|font-sans|font-serif|font-mono|font-display|font-body|font-heading|font-ui|font-primary|font-secondary|font)\s*:\s*([^;}]+)/gi)) {
    const families = resolveVars(declaration[1]).split(',').map((part) => part.trim().replace(/^['"]|['"]$/g, '').toLowerCase());
    if (validFamily(families[0])) fonts.set(families[0], (fonts.get(families[0]) || 0) + 1);
  }
  for (const raw of css.match(/fonts\.googleapis\.com\/css2?\?[^"'\s)]+/gi) || []) {
    for (const family of raw.matchAll(/family=([^&:]+)/gi)) googleFamilies.set(decodeURIComponent(family[1].replaceAll('+', ' ')), 1);
  }

  const radiusValues = new Map();
  for (const declaration of clean.matchAll(/border-radius\s*:\s*([^;}]+)/gi)) {
    for (const token of declaration[1].split(/[\s/]+/)) {
      if (!token) continue;
      const parsed = parseCssLength(token);
      if (parsed?.px != null) radiusValues.set(String(round(parsed.px)), (radiusValues.get(String(round(parsed.px))) || 0) + 1);
      else if (token.includes('%')) radiusValues.set(token, (radiusValues.get(token) || 0) + 1);
    }
  }
  const radiusBuckets = { zero: 0, xs: 0, sm: 0, md: 0, lg: 0, xl: 0, pill: 0, percent: 0 };
  for (const [raw, count] of radiusValues) {
    const px = Number(raw);
    if (Number.isNaN(px)) { radiusBuckets.percent += count; continue; }
    if (px === 0) radiusBuckets.zero += count;
    else if (px <= 4) radiusBuckets.xs += count;
    else if (px <= 8) radiusBuckets.sm += count;
    else if (px <= 12) radiusBuckets.md += count;
    else if (px <= 16) radiusBuckets.lg += count;
    else if (px < 100) radiusBuckets.xl += count;
    else radiusBuckets.pill += count;
  }

  const spacingValues = new Map(), fontSizes = new Map(), lineHeights = new Map(), letterSpacings = new Map();
  for (const declaration of clean.matchAll(/(?:^|;)\s*(gap|row-gap|column-gap|padding(?:-[\w]+)?|margin(?:-[\w]+)?)\s*:\s*([^;}]+)/gi)) {
    for (const token of declaration[2].split(/\s+/)) {
      const parsed = parseCssLength(token);
      if (parsed?.px != null && parsed.px >= 0 && parsed.px <= 200) spacingValues.set(String(round(parsed.px)), (spacingValues.get(String(round(parsed.px))) || 0) + 1);
    }
  }
  for (const declaration of clean.matchAll(/font-size\s*:\s*([^;}]+)/gi)) {
    const token = declaration[1].trim().split(/\s+/)[0];
    if (/^(var\(|inherit|initial|unset|revert)/.test(token)) continue;
    const parsed = parseCssLength(token);
    if (parsed?.px != null && parsed.px >= 6 && parsed.px <= 200) fontSizes.set(String(round(parsed.px)), (fontSizes.get(String(round(parsed.px))) || 0) + 1);
    else if (token.includes('clamp(')) fontSizes.set('clamp', (fontSizes.get('clamp') || 0) + 1);
  }
  for (const declaration of clean.matchAll(/line-height\s*:\s*([^;}]+)/gi)) {
    const token = declaration[1].trim().split(/\s+/)[0];
    if (/^[\d.]+$/.test(token)) lineHeights.set(token, (lineHeights.get(token) || 0) + 1);
    else {
      const parsed = parseCssLength(token);
      if (parsed?.px != null) lineHeights.set(`${round(parsed.px)}px`, (lineHeights.get(`${round(parsed.px)}px`) || 0) + 1);
    }
  }
  for (const declaration of clean.matchAll(/letter-spacing\s*:\s*([^;}]+)/gi)) {
    const token = declaration[1].trim().split(/\s+/)[0];
    const parsed = parseCssLength(token);
    if (parsed?.px != null) letterSpacings.set(`${round(parsed.px, 2)}px`, (letterSpacings.get(`${round(parsed.px, 2)}px`) || 0) + 1);
  }

  const durations = new Map(), easings = new Map();
  for (const declaration of clean.matchAll(/(?:^|;)\s*(transition(?:-[\w]+)?|animation(?:-[\w]+)?)\s*:\s*([^;}]+)/gi)) {
    for (const raw of declaration[2].matchAll(/(?<![\w.])(\d*\.?\d+)(m?s)\b/gi)) {
      const ms = raw[2].toLowerCase() === 's' ? parseFloat(raw[1]) * 1000 : parseFloat(raw[1]);
      if (ms > 0 && ms <= 5000) durations.set(String(round(ms)), (durations.get(String(round(ms))) || 0) + 1);
    }
    for (const raw of declaration[2].matchAll(/cubic-bezier\([^)]*\)|steps\([^)]*\)|\b(ease-in-out|ease-out|ease-in|ease|linear)\b/gi)) {
      const value = raw[0].toLowerCase();
      easings.set(value, (easings.get(value) || 0) + 1);
    }
  }

  const breakpoints = new Map(), maxWidths = new Map(), shadowBlurs = new Map();
  for (const raw of clean.matchAll(/@media[^{]*?\((?:max|min)-width\s*:\s*([\d.]+)(px|rem|em)\)/gi)) {
    const px = raw[2].toLowerCase() === 'px' ? parseFloat(raw[1]) : parseFloat(raw[1]) * 16;
    breakpoints.set(String(round(px)), (breakpoints.get(String(round(px))) || 0) + 1);
  }
  for (const raw of clean.matchAll(/max-width\s*:\s*([^;}]+)/gi)) {
    const parsed = parseCssLength(raw[1].trim().split(/\s+/)[0]);
    if (parsed?.px != null && parsed.px >= 480 && parsed.px <= 2400) maxWidths.set(String(round(parsed.px)), (maxWidths.get(String(round(parsed.px))) || 0) + 1);
  }
  let shadowCount = 0, softShadowCount = 0;
  for (const raw of clean.matchAll(/box-shadow\s*:\s*([^;}]+)/gi)) {
    const value = raw[1].trim().toLowerCase();
    if (!value || value === 'none') continue;
    shadowCount++;
    const lengths = [...value.matchAll(/(-?[\d.]+)(px|rem)/g)].map((m) => parseFloat(m[1]) * (m[2] === 'rem' ? 16 : 1));
    const blur = lengths.length >= 3 ? lengths[Math.min(2, lengths.length - 1)] : 0;
    if (blur >= 8) softShadowCount++;
    shadowBlurs.set(String(round(blur)), (shadowBlurs.get(String(round(blur))) || 0) + 1);
  }

  const accents = new Map(), neutralCount = { neutral: 0, chromatic: 0 }, hueCounts = new Map();
  for (const [hex, count] of colors) {
    const parsed = parseColor(hex);
    if (!parsed) continue;
    const info = colorInfo(parsed);
    if (info.neutral) neutralCount.neutral += count;
    else {
      neutralCount.chromatic += count;
      if (info.hueBucket) hueCounts.set(info.hueBucket, (hueCounts.get(info.hueBucket) || 0) + count);
    }
    if (info.s && info.s >= 0.35 && info.l >= 0.2 && info.l <= 0.8) accents.set(hex, count);
  }

  const borderCount = (clean.match(/(?:^|;)\s*border(?:-[\w]+)?\s*:/gi) || []).length;
  const gridCount = (clean.match(/display\s*:\s*grid/gi) || []).length;
  const flexCount = (clean.match(/display\s*:\s*flex/gi) || []).length;
  const gradientCount = (clean.match(/(?:linear|radial|conic)-gradient\(/gi) || []).length;
  const backdropCount = (clean.match(/backdrop-filter\s*:/gi) || []).length;
  const blurFilterCount = (clean.match(/filter\s*:[^;}]*blur\(/gi) || []).length;
  const mixBlendCount = (clean.match(/mix-blend-mode\s*:/gi) || []).length;
  const cssVarDefs = (clean.match(/--[\w-]+\s*:/g) || []).length;
  const varRefs = (clean.match(/var\(\s*--/g) || []).length;

  return {
    colors: [...colors.entries()].sort((a, b) => b[1] - a[1]).slice(0, 24).map(([hex, count]) => ({ hex, count })),
    backgroundColors: [...backgroundColors.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8).map(([hex, count]) => ({ hex, count })),
    textColors: [...textColors.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8).map(([hex, count]) => ({ hex, count })),
    accents: [...accents.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8).map(([hex, count]) => ({ hex, count })),
    neutralShare: neutralCount.neutral + neutralCount.chromatic ? round(neutralCount.neutral / (neutralCount.neutral + neutralCount.chromatic), 3) : null,
    hueCounts: Object.fromEntries(hueCounts),
    fonts: topEntries(fonts, 6),
    fontStacks: topEntries(fontStacks, 4),
    googleFamilies: topEntries(googleFamilies, 4),
    fontSizes: topEntries(fontSizes, 10),
    lineHeights: topEntries(lineHeights, 6),
    letterSpacings: topEntries(letterSpacings, 6),
    radii: topEntries(radiusValues, 10),
    radiusBuckets,
    spacing: topEntries(spacingValues, 12),
    durations: topEntries(durations, 10),
    easings: topEntries(easings, 6),
    breakpoints: topEntries(breakpoints, 10),
    maxWidths: topEntries(maxWidths, 8),
    shadowCount,
    softShadowCount,
    shadowBlurs: topEntries(shadowBlurs, 6),
    borderCount,
    gridCount,
    flexCount,
    gradientCount,
    backdropCount,
    blurFilterCount,
    mixBlendCount,
    cssVarDefs,
    varRefs,
    clampCount: (clean.match(/clamp\(/gi) || []).length,
    balanceCount: (clean.match(/text-wrap\s*:\s*(?:balance|pretty)/gi) || []).length,
    stickyCount: (clean.match(/position\s*:\s*sticky/gi) || []).length,
    dvhCount: (clean.match(/\b(?:100|9\d)dvh|\b(?:100|9\d)svh/gi) || []).length,
    reducedMotion: /prefers-reduced-motion/i.test(clean),
    colorScheme: /prefers-color-scheme|color-scheme\s*:/i.test(clean),
    darkSelectors: /(?:^|[},])\s*(?:\.dark|\[data-theme|:root\[data-theme|html\.dark)/i.test(clean),
    focusVisible: /:focus-visible/i.test(clean),
    containerQueries: (clean.match(/@container/gi) || []).length,
  };
}

function detectFramework(html) {
  const hints = [];
  if (/__NEXT_DATA__|\/_next\//i.test(html)) hints.push('next');
  if (/__NUXT__|\/_nuxt\//i.test(html)) hints.push('nuxt');
  if (/data-framer|framer\.website|framer\.com/i.test(html)) hints.push('framer');
  if (/webflow/i.test(html)) hints.push('webflow');
  if (/wixstatic|wix\.com/i.test(html)) hints.push('wix');
  if (/squarespace/i.test(html)) hints.push('squarespace');
  if (/cdn\.shopify|shopify/i.test(html)) hints.push('shopify');
  if (/wp-content|wp-json/i.test(html)) hints.push('wordpress');
  if (/astro-island/i.test(html)) hints.push('astro');
  if (/data-v-[0-9a-f]{6,}|__vue__/i.test(html)) hints.push('vue');
  if (/svelte-[a-z0-9]+/i.test(html)) hints.push('svelte');
  if (/react(?:-dom)?(?:\.production|\.development)?\.js|data-reactroot/i.test(html)) hints.push('react');
  if (/tailwind/i.test(html)) hints.push('tailwind');
  return [...new Set(hints)];
}

function htmlSignals(html, finalUrl) {
  const title = decodeEntities(firstMatch(html, /<title[^>]*>([\s\S]*?)<\/title>/i));
  const description = decodeEntities(html.match(/<meta[^>]+name=["']description["'][^>]+content=["']([^"']*)["']/i)?.[1]
    || html.match(/<meta[^>]+content=["']([^"']*)["'][^>]+name=["']description["']/i)?.[1] || '');
  const themeColor = html.match(/<meta[^>]+name=["']theme-color["'][^>]+content=["']([^"']*)["']/i)?.[1] || '';
  const lang = html.match(/<html[^>]+lang=["']([^"']+)["']/i)?.[1] || '';
  const generator = html.match(/<meta[^>]+name=["']generator["'][^>]+content=["']([^"']*)["']/i)?.[1] || '';
  const h1 = stripTags(firstMatch(html, /<h1[^>]*>([\s\S]*?)<\/h1>/i));
  const navBlock = html.match(/<nav[^>]*>([\s\S]*?)<\/nav>/i)?.[1] || '';
  const navLinks = (navBlock.match(/<a\b/gi) || []).length;
  const anchors = (html.match(/<a\b/gi) || []).length;
  const buttons = (html.match(/<button\b/gi) || []).length;
  const images = [...html.matchAll(/<img\b[^>]*>/gi)].map((m) => m[0]);
  const imagesWithAlt = images.filter((tag) => /\balt\s*=\s*["'][^"']+["']/i.test(tag)).length;
  const ariaCount = (html.match(/aria-[a-z]+=/gi) || []).length;
  const classNames = [...html.matchAll(/class=["']([^"']+)["']/gi)].map((m) => m[1]).join(' ');
  const utilityHits = (classNames.match(/\b(?:flex|grid|items-center|justify-between|gap-\d+|p[xy]?-\d+|m[xy]?-\d+|text-(?:xs|sm|base|lg|xl|2xl|3xl)|font-(?:medium|semibold|bold)|rounded(?:-\w+)?|bg-\w+|border-\w+|w-\d+|h-\d+|space-[xy]-\d+)\b/g) || []).length;
  const classes = (classNames.match(/\S+/g) || []).length;
  return {
    title: title.slice(0, 180),
    description: description.slice(0, 300),
    themeColor,
    lang,
    generator,
    h1: h1.slice(0, 180),
    navLinks,
    anchors,
    buttons,
    images: images.length,
    imagesWithAlt,
    ariaCount,
    classes,
    tailwindScore: classes ? round(utilityHits / classes, 3) : 0,
    hasMain: /<main\b/i.test(html),
    hasSkipLink: /href=["']#(?:main|content|skip)/i.test(html) || /skip to (?:main|content)/i.test(html),
    inlineSvg: (html.match(/<svg\b/gi) || []).length,
    framework: detectFramework(html),
    finalHost: normalizeHost(new URL(finalUrl).hostname),
  };
}

async function fetchWithTimeout(url, timeout = TIMEOUT) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    return await fetch(url, {
      signal: controller.signal,
      redirect: 'follow',
      headers: {
        'user-agent': UA,
        accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'accept-language': 'en-US,en;q=0.9',
      },
    });
  } catch (error) {
    error.causeCode = error.cause?.code || error.cause?.message || '';
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

function resolveStylesheets(html, baseUrl) {
  const baseHref = html.match(/<base[^>]+href=["']([^"']+)["']/i)?.[1];
  let base = baseUrl;
  try { if (baseHref) base = new URL(baseHref, baseUrl).href; } catch {}
  const urls = [];
  for (const tag of html.match(/<link\b[^>]*>/gi) || []) {
    if (!/rel=["'][^"']*stylesheet/i.test(tag)) continue;
    const href = tag.match(/href=["']([^"']+)["']/i)?.[1];
    if (!href) continue;
    try {
      const resolved = new URL(decodeEntities(href), base);
      if (resolved.protocol === 'http:' || resolved.protocol === 'https:') urls.push(resolved.href);
    } catch {}
  }
  return [...new Set(urls)];
}

async function fetchPage(url) {
  let lastError;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const response = await fetchWithTimeout(url);
      if (response.status >= 500 && attempt < 2) {
        lastError = new Error(`HTTP ${response.status}`);
        await new Promise((resolve) => setTimeout(resolve, 600 * (attempt + 1)));
        continue;
      }
      return response;
    } catch (error) {
      lastError = error;
      if (attempt < 2) await new Promise((resolve) => setTimeout(resolve, 700 * (attempt + 1)));
    }
  }
  throw lastError;
}

async function analyzePage(item) {
  const started = Date.now();
  let response;
  try {
    response = await fetchPage(item.url);
  } catch (error) {
    return { id: item.id, url: item.url, ok: false, error: `fetch: ${error.message}${error.causeCode ? ` (${error.causeCode})` : ''}`, durationMs: Date.now() - started };
  }
  const status = response.status;
  const contentType = response.headers.get('content-type') || '';
  if (!response.ok) return { id: item.id, url: item.url, ok: false, status, error: `HTTP ${status}`, durationMs: Date.now() - started };
  if (!/text\/html|application\/xhtml/i.test(contentType)) {
    return { id: item.id, url: item.url, ok: false, status, error: `content-type ${contentType.slice(0, 60)}`, durationMs: Date.now() - started };
  }
  let html;
  try {
    const buffer = await response.arrayBuffer();
    html = new TextDecoder('utf-8', { fatal: false }).decode(buffer.slice(0, MAX_HTML));
  } catch (error) {
    return { id: item.id, url: item.url, ok: false, status, error: `body: ${error.message}`, durationMs: Date.now() - started };
  }
  const finalUrl = response.url || item.url;
  const htmlMeta = htmlSignals(html, finalUrl);
  const inlineCss = [...html.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/gi)].map((m) => m[1]).join('\n');
  const sheetUrls = resolveStylesheets(html, finalUrl).slice(0, 4);
  let css = inlineCss.slice(0, MAX_CSS_TOTAL);
  let cssBytes = inlineCss.length;
  let cssFiles = 0;
  const sheets = await Promise.allSettled(sheetUrls.map(async (sheetUrl) => {
    const sheet = await fetchWithTimeout(sheetUrl, 12000);
    if (!sheet.ok) return null;
    const type = sheet.headers.get('content-type') || '';
    if (!/css|text\/plain/i.test(type) && !/\.css(?:$|\?)/i.test(sheetUrl)) return null;
    return (await sheet.text()).slice(0, MAX_CSS_FILE);
  }));
  for (const result of sheets) {
    if (result.status !== 'fulfilled' || !result.value) continue;
    if (css.length >= MAX_CSS_TOTAL) break;
    css += `\n${result.value}`;
    cssBytes += result.value.length;
    cssFiles++;
  }
  const cssSignals = extractCssSignals(css);
  const summary = {
    id: item.id,
    url: item.url,
    finalUrl,
    ok: true,
    status,
    source: item.source,
    category: item.category,
    tags: item.tags,
    title: htmlMeta.title,
    host: normalizeHost(new URL(finalUrl).hostname),
    html: htmlMeta,
    cssBytes,
    cssFiles,
    inlineCssBytes: inlineCss.length,
    css: cssSignals,
    durationMs: Date.now() - started,
    fetchedAt: new Date().toISOString(),
  };
  return summary;
}

let cursor = 0, ok = 0, failed = 0, finished = 0;
async function worker() {
  while (cursor < queue.length) {
    const item = queue[cursor++];
    let record;
    try {
      record = await analyzePage(item);
    } catch (error) {
      record = { id: item.id, url: item.url, ok: false, error: String(error.stack || error), durationMs: 0 };
    }
    fs.appendFileSync(OUT, `${JSON.stringify(record)}\n`);
    if (record.ok) ok++; else failed++;
    finished++;
    if (finished % 25 === 0) console.log(`[analyze] ${finished}/${queue.length} ok=${ok} failed=${failed} last=${item.host}`);
  }
}

await Promise.all(Array.from({ length: CONCURRENCY }, worker));
console.log(`[analyze] done ok=${ok} failed=${failed} total=${done.size + finished}`);
