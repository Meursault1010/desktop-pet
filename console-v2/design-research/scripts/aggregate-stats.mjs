import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const FEATURES = process.env.FEATURES_FILE || path.join(ROOT, 'data', 'page-features.jsonl');
const OUT_JSON = path.join(ROOT, 'data', 'aggregate.json');
const OUT_MD = path.join(ROOT, 'data', 'aggregate.md');

const rows = (await fs.readFile(FEATURES, 'utf8')).split('\n').filter(Boolean).map((line) => {
  try { return JSON.parse(line); } catch { return null; }
}).filter(Boolean);
const ok = rows.filter((r) => r.ok && r.css && r.html);

const quantile = (arr, q) => {
  if (!arr.length) return null;
  const a = arr.slice().sort((x, y) => x - y);
  const pos = (a.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return a[lo] + (a[hi] - a[lo]) * (pos - lo);
};
const round = (v, d = 2) => (v == null || !Number.isFinite(v) ? null : Math.round(v * 10 ** d) / 10 ** d);
const share = (n, d) => (d ? round(n / d, 3) : 0);
const topMap = (map, n = 20) => [...map.entries()].sort((a, b) => b[1] - a[1]).slice(0, n);

function hexToRgb(hex) {
  let h = String(hex || '').replace('#', '');
  if (h.length === 3) h = h.split('').map((c) => c + c).join('');
  if (h.length !== 6) return null;
  const int = parseInt(h, 16);
  return [(int >> 16) & 255, (int >> 8) & 255, int & 255];
}
function luminance([r, g, b]) {
  return [r, g, b].map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  }).reduce((acc, c, i) => acc + c * [0.2126, 0.7152, 0.0722][i], 0);
}
function hueOf([r, g, b]) {
  const rn = r / 255, gn = g / 255, bn = b / 255;
  const max = Math.max(rn, gn, bn), min = Math.min(rn, gn, bn);
  const d = max - min;
  if (d === 0) return null;
  let h;
  if (max === rn) h = ((gn - bn) / d) % 6;
  else if (max === gn) h = (bn - rn) / d + 2;
  else h = (rn - gn) / d + 4;
  h *= 60;
  return h < 0 ? h + 360 : h;
}
const hueBucket = (h) => {
  if (h == null) return 'neutral';
  if (h < 20 || h >= 340) return 'red';
  if (h < 45) return 'orange';
  if (h < 70) return 'yellow';
  if (h < 160) return 'green';
  if (h < 200) return 'cyan';
  if (h < 255) return 'blue';
  if (h < 290) return 'purple';
  if (h < 340) return 'pink';
  return 'other';
};
const pxValue = (v) => {
  const m = String(v).trim().match(/^(-?\d*\.?\d+)(px)?$/);
  return m ? Number(m[1]) : null;
};

const stats = {
  generatedAt: new Date().toISOString(),
  corpus: { lines: rows.length, analyzed: ok.length, failed: rows.length - ok.length, successRate: share(ok.length, rows.length) },
  sources: {}, categories: {},
  frameworks: {}, cssBytes: {},
  fonts: {}, type: {}, color: {}, shape: {}, layout: {}, motion: {}, a11y: {}, chrome: {}, architecture: {},
};

// --- source / category ---
for (const r of ok) {
  stats.sources[r.source || 'unknown'] = (stats.sources[r.source || 'unknown'] || 0) + 1;
  stats.categories[r.category || 'uncategorized'] = (stats.categories[r.category || 'uncategorized'] || 0) + 1;
}
stats.cssBytes = {
  median: quantile(ok.map((r) => r.cssBytes || 0), 0.5),
  p75: quantile(ok.map((r) => r.cssBytes || 0), 0.75),
  p90: quantile(ok.map((r) => r.cssBytes || 0), 0.9),
};

// --- frameworks ---
{
  const m = new Map();
  for (const r of ok) for (const f of r.html.framework || []) m.set(f, (m.get(f) || 0) + 1);
  stats.frameworks = Object.fromEntries(topMap(m, 15).map(([k, v]) => [k, { pages: v, share: share(v, ok.length) }]));
}

// --- fonts ---
{
  const presence = new Map();
  const weighted = new Map();
  const countsPerPage = [];
  const GENERIC = new Set(['sans-serif', 'serif', 'monospace', 'ui-monospace', 'ui-sans-serif', 'system-ui', 'ui-serif', 'ui-rounded', 'emoji', 'math', 'inherit', 'initial', 'unset', 'revert', 'cursive', 'fantasy', '-apple-system', 'blinkmacsystemfont']);
  let serif = 0, mono = 0, variable = 0, google = 0;
  for (const r of ok) {
    const fonts = (r.css.fonts || []).filter(([name]) => name && name.length > 1 && !/[:!{}]/.test(name));
    countsPerPage.push(fonts.length);
    const seen = new Set();
    for (const [name, count] of fonts) {
      if (!GENERIC.has(name)) {
        if (!seen.has(name)) { presence.set(name, (presence.get(name) || 0) + 1); seen.add(name); }
        weighted.set(name, (weighted.get(name) || 0) + count);
      }
      if (/serif/i.test(name) && !/sans-serif/i.test(name)) serif += 1;
      if (/mono/i.test(name)) mono += 1;
      if (/variable|vf\b/i.test(name)) variable += 1;
    }
    if ((r.css.googleFamilies || []).length) google += 1;
  }
  const families = topMap(presence, 25).map(([name, pages]) => ({ name, pages, share: share(pages, ok.length), weight: weighted.get(name) }));
  stats.fonts = {
    families,
    pagePresence: Object.fromEntries(families.map((f) => [f.name, f.pages])),
    familyCountPerPage: { median: quantile(countsPerPage, 0.5), p75: quantile(countsPerPage, 0.75), p90: quantile(countsPerPage, 0.9) },
    pagesWithSerif: serif,
    pagesWithMono: mono,
    serifShare: share(serif, ok.length),
    monoShare: share(mono, ok.length),
    googleFontPages: google,
    googleShare: share(google, ok.length),
  };
}

// --- type scale ---
{
  const uniqueSizes = [];
  const maxSizes = [];
  const minSizes = [];
  const ratios = [];
  const sizePages = new Map();
  let negativeTracking = 0, tightLeading = 0, relaxedLeading = 0, uppercasePages = 0;
  for (const r of ok) {
    const sizes = [...new Set((r.css.fontSizes || []).map(([v]) => pxValue(v)).filter((v) => v != null && v >= 8 && v <= 200))].sort((a, b) => a - b);
    if (!sizes.length) continue;
    uniqueSizes.push(sizes.length);
    maxSizes.push(sizes[sizes.length - 1]);
    minSizes.push(sizes[0]);
    if (sizes.length >= 4) ratios.push(sizes[sizes.length - 1] / sizes[0]);
    for (const s of sizes) sizePages.set(s, (sizePages.get(s) || 0) + 1);
    if ((r.css.letterSpacings || []).some(([v]) => { const n = pxValue(v); return n != null && n < -0.05; })) negativeTracking += 1;
    if ((r.css.lineHeights || []).some(([v]) => { const n = Number(v); return Number.isFinite(n) && n > 0 && n <= 1.15; })) tightLeading += 1;
    if ((r.css.lineHeights || []).some(([v]) => { const n = Number(v); return Number.isFinite(n) && n >= 1.5; })) relaxedLeading += 1;
    uppercasePages += 1;
  }
  const bucket = (sizes) => {
    const out = { '<24': 0, '24-31': 0, '32-47': 0, '48-63': 0, '64-95': 0, '96+': 0 };
    for (const s of sizes) {
      if (s < 24) out['<24'] += 1;
      else if (s < 32) out['24-31'] += 1;
      else if (s < 48) out['32-47'] += 1;
      else if (s < 64) out['48-63'] += 1;
      else if (s < 96) out['64-95'] += 1;
      else out['96+'] += 1;
    }
    return out;
  };
  stats.type = {
    pagesWithSizes: uniqueSizes.length,
    uniqueSizesPerPage: { median: quantile(uniqueSizes, 0.5), p75: quantile(uniqueSizes, 0.75), p90: quantile(uniqueSizes, 0.9) },
    displaySizeBuckets: bucket(maxSizes),
    displayBucketShare: Object.fromEntries(Object.entries(bucket(maxSizes)).map(([k, v]) => [k, share(v, maxSizes.length)])),
    maxMinRatio: { median: quantile(ratios, 0.5), p75: quantile(ratios, 0.75), p90: quantile(ratios, 0.9) },
    commonSizes: Object.fromEntries([...sizePages.entries()].sort((a, b) => b[1] - a[1]).slice(0, 18)),
    negativeTrackingShare: share(negativeTracking, uniqueSizes.length),
    tightLeadingShare: share(tightLeading, uniqueSizes.length),
    relaxedLeadingShare: share(relaxedLeading, uniqueSizes.length),
    pxSizesInTokens: { medianMin: quantile(minSizes, 0.5), medianMax: quantile(maxSizes, 0.5) },
  };
}

// --- color ---
{
  const neutral = [];
  const accentCounts = [];
  const huePages = new Map();
  const accentPresence = new Map();
  const bgLightness = [];
  const scheme = { light: 0, mid: 0, dark: 0 };
  for (const r of ok) {
    neutral.push(r.css.neutralShare || 0);
    const accents = r.css.accents || [];
    accentCounts.push(accents.length);
    const hues = r.css.hueCounts || {};
    for (const [h, c] of Object.entries(hues)) if (c > 0) huePages.set(h, (huePages.get(h) || 0) + 1);
    for (const entry of accents) {
      const hex = Array.isArray(entry) ? entry[0] : entry?.hex;
      if (!hex) continue;
      const rgb = hexToRgb(hex);
      if (!rgb) continue;
      const max = Math.max(...rgb), min = Math.min(...rgb);
      if ((max - min) / (max || 1) < 0.08) continue;
      accentPresence.set(String(hex).slice(0, 7), (accentPresence.get(String(hex).slice(0, 7)) || 0) + 1);
    }
    const bgs = (r.css.backgroundColors || []).slice(0, 8).map((entry) => {
      const hex = Array.isArray(entry) ? entry[0] : entry?.hex;
      const count = Array.isArray(entry) ? entry[1] : entry?.count || 1;
      return { rgb: hexToRgb(hex), count };
    }).filter((x) => x.rgb);
    if (bgs.length) {
      const total = bgs.reduce((s, x) => s + x.count, 0);
      const L = bgs.reduce((s, x) => s + luminance(x.rgb) * x.count, 0) / total;
      bgLightness.push(L);
      if (L < 0.08) scheme.dark += 1;
      else if (L < 0.55) scheme.mid += 1;
      else scheme.light += 1;
    }
  }
  stats.color = {
    neutralShare: { p25: quantile(neutral, 0.25), median: quantile(neutral, 0.5), p75: quantile(neutral, 0.75), p90: quantile(neutral, 0.9) },
    accentsPerPage: { median: quantile(accentCounts, 0.5), p75: quantile(accentCounts, 0.75), p90: quantile(accentCounts, 0.9) },
    backgroundScheme: scheme,
    backgroundSchemeShare: { light: share(scheme.light, bgLightness.length), mid: share(scheme.mid, bgLightness.length), dark: share(scheme.dark, bgLightness.length) },
    accentHuePages: Object.fromEntries(topMap(huePages, 12)),
    topAccents: topMap(accentPresence, 20).map(([hex, pages]) => ({ hex, pages, share: share(pages, ok.length) })),
  };
}

// --- shape ---
{
  const dominantRadius = new Map();
  const radiiPerPage = [];
  let zeroDominant = 0, pillAny = 0, shadowAny = 0, softShadow = 0, gradient = 0, backdrop = 0, blur = 0, mixBlend = 0;
  const borderCounts = [];
  for (const r of ok) {
    const buckets = Object.entries(r.css.radiusBuckets || {}).sort((a, b) => b[1] - a[1]);
    if (buckets.length) dominantRadius.set(buckets[0][0], (dominantRadius.get(buckets[0][0]) || 0) + 1);
    if (buckets.length && buckets[0][0] === 'zero') zeroDominant += 1;
    if (buckets.some(([k, v]) => k === 'pill' && v > 0)) pillAny += 1;
    radiiPerPage.push(buckets.reduce((s, [, v]) => s + v, 0));
    if ((r.css.shadowCount || 0) > 0) shadowAny += 1;
    if ((r.css.softShadowCount || 0) > 0) softShadow += 1;
    if ((r.css.gradientCount || 0) > 0) gradient += 1;
    if ((r.css.backdropCount || 0) > 0) backdrop += 1;
    if ((r.css.blurFilterCount || 0) > 0) blur += 1;
    if ((r.css.mixBlendCount || 0) > 0) mixBlend += 1;
    borderCounts.push(r.css.borderCount || 0);
  }
  stats.shape = {
    dominantRadiusPages: Object.fromEntries(topMap(dominantRadius, 10)),
    dominantRadiusShare: Object.fromEntries([...dominantRadius.entries()].map(([k, v]) => [k, share(v, ok.length)])),
    zeroDominantShare: share(zeroDominant, ok.length),
    pillAnyShare: share(pillAny, ok.length),
    radiusTokensPerPage: { median: quantile(radiiPerPage, 0.5), p75: quantile(radiiPerPage, 0.75) },
    shadowAnyShare: share(shadowAny, ok.length),
    softShadowShare: share(softShadow, ok.length),
    gradientShare: share(gradient, ok.length),
    backdropBlurShare: share(backdrop, ok.length),
    blurFilterShare: share(blur, ok.length),
    mixBlendShare: share(mixBlend, ok.length),
    borderTokensPerPage: { median: quantile(borderCounts, 0.5), p75: quantile(borderCounts, 0.75) },
  };
}

// --- layout / spacing ---
{
  const maxWidthPages = new Map();
  const breakpointCounts = [];
  const commonBreakpoints = new Map();
  const spacings = new Map();
  let fourGridPages = 0, gridDominant = 0, containerPages = 0, clampPages = 0, stickyPages = 0, dvhPages = 0, balancePages = 0;
  for (const r of ok) {
    const widths = [...new Set((r.css.maxWidths || []).map(([v]) => pxValue(v)).filter((v) => v != null && v >= 480 && v <= 1920))];
    const contentWidth = widths.find((v) => v >= 1100 && v <= 1500) || null;
    maxWidthPages.set(contentWidth || 'none', (maxWidthPages.get(contentWidth || 'none') || 0) + 1);
    const bps = [...new Set((r.css.breakpoints || []).map(([v]) => pxValue(v)).filter((v) => v != null))];
    breakpointCounts.push(bps.length);
    for (const bp of bps) commonBreakpoints.set(bp, (commonBreakpoints.get(bp) || 0) + 1);
    const sp = [...new Set((r.css.spacing || []).map(([v]) => pxValue(v)).filter((v) => v != null && v > 0))];
    const aligned = sp.filter((v) => v % 4 === 0).length;
    if (sp.length && aligned / sp.length >= 0.75) fourGridPages += 1;
    for (const v of sp) spacings.set(v, (spacings.get(v) || 0) + 1);
    if ((r.css.gridCount || 0) > (r.css.flexCount || 0)) gridDominant += 1;
    if ((r.css.containerQueries || 0) > 0) containerPages += 1;
    if ((r.css.clampCount || 0) > 0) clampPages += 1;
    if ((r.css.stickyCount || 0) > 0) stickyPages += 1;
    if ((r.css.dvhCount || 0) > 0) dvhPages += 1;
    if ((r.css.balanceCount || 0) > 0) balancePages += 1;
  }
  stats.layout = {
    breakpointCountPerPage: { median: quantile(breakpointCounts, 0.5), p75: quantile(breakpointCounts, 0.75) },
    commonBreakpoints: Object.fromEntries(topMap(commonBreakpoints, 12)),
    dominantContentWidthPages: Object.fromEntries([...maxWidthPages.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10).map(([k, v]) => [String(k), v])),
    fourPointGridShare: share(fourGridPages, ok.length),
    gridOverFlexShare: share(gridDominant, ok.length),
    containerQueryShare: share(containerPages, ok.length),
    clampTypographyShare: share(clampPages, ok.length),
    stickyShare: share(stickyPages, ok.length),
    dvhShare: share(dvhPages, ok.length),
    textWrapBalanceShare: share(balancePages, ok.length),
    commonSpacings: Object.fromEntries(topMap(spacings, 14)),
  };
}

// --- motion ---
{
  const durations = [];
  const easingPages = new Map();
  const perPageDuration = [];
  for (const r of ok) {
    const local = (r.css.durations || []).map(([v, c]) => ({ ms: Number.parseFloat(v), c })).filter((x) => Number.isFinite(x.ms) && x.ms > 0 && x.ms < 5000);
    for (const { ms, c } of local) durations.push({ ms, c });
    perPageDuration.push(quantile(local.map((x) => x.ms), 0.5));
    for (const [e] of r.css.easings || []) {
      const key = e.replace(/\s+/g, '');
      easingPages.set(key, (easingPages.get(key) || 0) + 1);
    }
  }
  const weightedDurations = new Map();
  for (const { ms, c } of durations) weightedDurations.set(ms, (weightedDurations.get(ms) || 0) + c);
  stats.motion = {
    durationMs: { median: quantile(durations.map((d) => d.ms), 0.5), p75: quantile(durations.map((d) => d.ms), 0.75) },
    pageMedianDuration: { median: quantile(perPageDuration.filter((v) => v != null), 0.5), p75: quantile(perPageDuration.filter((v) => v != null), 0.75) },
    commonDurations: Object.fromEntries([...weightedDurations.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10)),
    easings: Object.fromEntries(topMap(easingPages, 10)),
  };
}

// --- a11y ---
{
  const altCoverage = [];
  let skip = 0, main = 0, reduced = 0, focus = 0, colorScheme = 0, darkSelectors = 0, lang = 0, themeColor = 0;
  for (const r of ok) {
    if (r.html.images) altCoverage.push((r.html.imagesWithAlt || 0) / r.html.images);
    if (r.html.hasSkipLink) skip += 1;
    if (r.html.hasMain) main += 1;
    if (r.css.reducedMotion) reduced += 1;
    if (r.css.focusVisible) focus += 1;
    if (r.css.colorScheme) colorScheme += 1;
    if (r.css.darkSelectors) darkSelectors += 1;
    if (r.html.lang) lang += 1;
    if (r.html.themeColor) themeColor += 1;
  }
  stats.a11y = {
    altCoverage: { median: quantile(altCoverage, 0.5), p25: quantile(altCoverage, 0.25) },
    skipLinkShare: share(skip, ok.length),
    mainLandmarkShare: share(main, ok.length),
    reducedMotionShare: share(reduced, ok.length),
    focusVisibleShare: share(focus, ok.length),
    colorSchemeShare: share(colorScheme, ok.length),
    darkSelectorShare: share(darkSelectors, ok.length),
    langShare: share(lang, ok.length),
    themeColorShare: share(themeColor, ok.length),
  };
}

// --- chrome ---
{
  const nav = [], anchors = [], buttons = [], images = [], aria = [], classes = [];
  let h1 = 0;
  for (const r of ok) {
    nav.push(r.html.navLinks || 0); anchors.push(r.html.anchors || 0); buttons.push(r.html.buttons || 0);
    images.push(r.html.images || 0); aria.push(r.html.ariaCount || 0); classes.push(r.html.classes || 0);
    if (r.html.h1) h1 += 1;
  }
  stats.chrome = {
    navLinks: { median: quantile(nav, 0.5), p75: quantile(nav, 0.75), p90: quantile(nav, 0.9) },
    anchors: { median: quantile(anchors, 0.5), p75: quantile(anchors, 0.75) },
    buttons: { median: quantile(buttons, 0.5), p75: quantile(buttons, 0.75) },
    images: { median: quantile(images, 0.5), p75: quantile(images, 0.75) },
    ariaAttributes: { median: quantile(aria, 0.5), p75: quantile(aria, 0.75) },
    classTokens: { median: quantile(classes, 0.5), p75: quantile(classes, 0.75) },
    h1Share: share(h1, ok.length),
  };
}

// --- architecture ---
{
  const vars = [];
  const refs = [];
  let varPages = 0, tailwindPages = 0, styleAttrPages = 0;
  const generators = new Map();
  for (const r of ok) {
    vars.push(r.css.cssVarDefs || 0); refs.push(r.css.varRefs || 0);
    if ((r.css.cssVarDefs || 0) > 0) varPages += 1;
    if ((r.html.tailwindScore || 0) > 0.3) tailwindPages += 1;
    if (r.html.generator) generators.set(r.html.generator, (generators.get(r.html.generator) || 0) + 1);
  }
  stats.architecture = {
    cssVarDefsPerPage: { median: quantile(vars, 0.5), p75: quantile(vars, 0.75) },
    cssVarRefsPerPage: { median: quantile(refs, 0.5), p75: quantile(refs, 0.75) },
    cssVarPageShare: share(varPages, ok.length),
    tailwindPageShare: share(tailwindPages, ok.length),
    generators: Object.fromEntries(topMap(generators, 8)),
  };
}

await fs.writeFile(OUT_JSON, JSON.stringify(stats, null, 2));

// --- markdown digest ---
const lines = [];
const pct = (v) => (v == null ? 'n/a' : `${Math.round(v * 100)}%`);
lines.push(`# Design corpus aggregate`);
lines.push('');
lines.push(`- Analyzed pages: **${ok.length}** / ${rows.length} targets (${pct(stats.corpus.successRate)} success)`);
lines.push(`- Sources: ${Object.entries(stats.sources).map(([k, v]) => `${k} ${v}`).join(' · ')}`);
lines.push(`- Median CSS bytes/page: ${stats.cssBytes.median}`);
lines.push('');
lines.push('## Fonts');
for (const f of stats.fonts.families.slice(0, 15)) lines.push(`- ${f.name} — ${f.pages} pages (${pct(f.share)})`);
lines.push(`- Mono on ${pct(stats.fonts.monoShare)} of pages · serif on ${pct(stats.fonts.serifShare)} · median families/page ${round(stats.fonts.familyCountPerPage.median, 1)}`);
lines.push('');
lines.push('## Type');
lines.push(`- Display max bucket: ${Object.entries(stats.type.displayBucketShare).map(([k, v]) => `${k} ${pct(v)}`).join(' · ')}`);
lines.push(`- Max/min size ratio median: ${round(stats.type.maxMinRatio.median, 1)} (p75 ${round(stats.type.maxMinRatio.p75, 1)})`);
lines.push(`- Negative tracking: ${pct(stats.type.negativeTrackingShare)} · tight leading: ${pct(stats.type.tightLeadingShare)} · relaxed leading: ${pct(stats.type.relaxedLeadingShare)}`);
lines.push(`- Common px sizes: ${Object.entries(stats.type.commonSizes).slice(0, 12).map(([k, v]) => `${k}(${v})`).join(', ')}`);
lines.push('');
lines.push('## Color');
lines.push(`- Neutral token share: median ${round(stats.color.neutralShare.median, 2)} (p25 ${round(stats.color.neutralShare.p25, 2)}, p75 ${round(stats.color.neutralShare.p75, 2)})`);
lines.push(`- Accents/page: median ${round(stats.color.accentsPerPage.median, 1)} (p75 ${round(stats.color.accentsPerPage.p75, 1)})`);
lines.push(`- Background scheme: light ${pct(stats.color.backgroundSchemeShare.light)} · mid ${pct(stats.color.backgroundSchemeShare.mid)} · dark ${pct(stats.color.backgroundSchemeShare.dark)}`);
lines.push(`- Accent hues (pages): ${Object.entries(stats.color.accentHuePages).map(([k, v]) => `${k} ${v}`).join(' · ')}`);
lines.push(`- Top accents: ${stats.color.topAccents.slice(0, 8).map((a) => `${a.hex}(${a.pages})`).join(', ')}`);
lines.push('');
lines.push('## Shape');
lines.push(`- Dominant radius share: ${Object.entries(stats.shape.dominantRadiusShare).map(([k, v]) => `${k} ${pct(v)}`).join(' · ')}`);
lines.push(`- Soft shadow ${pct(stats.shape.softShadowShare)} · gradient ${pct(stats.shape.gradientShare)} · backdrop blur ${pct(stats.shape.backdropBlurShare)} · pill ${pct(stats.shape.pillAnyShare)}`);
lines.push(`- Border tokens/page median: ${stats.shape.borderTokensPerPage.median}`);
lines.push('');
lines.push('## Layout');
lines.push(`- Breakpoints/page median: ${stats.layout.breakpointCountPerPage.median}; common: ${Object.entries(stats.layout.commonBreakpoints).slice(0, 8).map(([k, v]) => `${k}px(${v})`).join(', ')}`);
lines.push(`- 4pt spacing alignment: ${pct(stats.layout.fourPointGridShare)} · grid>flex: ${pct(stats.layout.gridOverFlexShare)} · clamp type: ${pct(stats.layout.clampTypographyShare)} · sticky: ${pct(stats.layout.stickyShare)}`);
lines.push(`- Content widths: ${Object.entries(stats.layout.dominantContentWidthPages).map(([k, v]) => `${k}(${v})`).join(', ')}`);
lines.push('');
lines.push('## Motion');
lines.push(`- Durations: median ${round(stats.motion.pageMedianDuration.median, 0)}ms, p75 ${round(stats.motion.pageMedianDuration.p75, 0)}ms`);
lines.push(`- Easings: ${Object.entries(stats.motion.easings).map(([k, v]) => `${k} ${v}`).join(' · ')}`);
lines.push('');
lines.push('## Accessibility');
lines.push(`- main ${pct(stats.a11y.mainLandmarkShare)} · skip link ${pct(stats.a11y.skipLinkShare)} · focus-visible ${pct(stats.a11y.focusVisibleShare)} · reduced-motion ${pct(stats.a11y.reducedMotionShare)} · alt median ${pct(stats.a11y.altCoverage.median)}`);
lines.push('');
lines.push('## Chrome');
lines.push(`- nav links median ${stats.chrome.navLinks.median}; anchors median ${stats.chrome.anchors.median}; buttons median ${stats.chrome.buttons.median}`);
lines.push(`- H1 present ${pct(stats.chrome.h1Share)} · CSS vars on ${pct(stats.architecture.cssVarPageShare)} pages · Tailwind on ${pct(stats.architecture.tailwindPageShare)}`);

await fs.writeFile(OUT_MD, lines.join('\n') + '\n');
console.log(`[aggregate] ok=${ok.length}/${rows.length} -> ${OUT_JSON}`);
console.log(lines.slice(0, 12).join('\n'));
