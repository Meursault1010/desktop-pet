import { stageSize } from './motion.js';
import { DUR, SHOTS, BEAT } from './timeline.js';

const W = 1920, H = 1080;
const canvas = document.querySelector('#art');
const art = canvas.getContext('2d', { alpha: false });
const wipe = document.querySelector('#wipe').getContext('2d');
let ctx = art;
const stage = document.querySelector('#stage');
const copy = document.querySelector('#copy');
const title = document.querySelector('#title');
const subtitle = document.querySelector('#subtitle');
const { W: viewW, H: viewH } = stageSize();
const scale = Math.min(viewW / W, viewH / H);
stage.style.transform = `translate(${(viewW - W * scale) / 2}px,${(viewH - H * scale) / 2}px) scale(${scale})`;

const clamp = (v) => Math.min(1, Math.max(0, v));
const tween = (t, a, b) => clamp((t - a) / (b - a));
const ease = (t, a, b) => {
  const u = tween(t, a, b);
  return u * u * (3 - 2 * u);
};
const mix = (a, b, p) => a + (b - a) * p;
const tau = Math.PI * 2;
const bob = (t, period) => Math.sin(t / period * tau);
const colors = {
  cream: '#faf7f0', ink: '#233b5c', blue: '#517fab', line: '#a7bed2', paper: '#fffcf7',
  sky: '#d9eafa', lilac: '#e8e2f5', blush: '#f8e4e8', mint: '#deeee7', yellow: '#fae2a3',
};
const captions = [
  ['Yuki', '一只住在 Windows 桌面上的小雪。'],
  ['桌面是她的\n小天地', '散步、探头，和桌面图标玩耍。'],
  ['和雪\n聊两句', '在桌面上，随手打开 AI 对话。'],
  ['一起\n专注一会儿', '开个专注计时，她就安静陪你。'],
  ['音乐响了，\n她会跳舞', '跟着电脑正在播放的音乐舞动。'],
  ['桌面见！', 'Yuki 雪 · 你的 Windows 桌面伙伴'],
];
const accents = [colors.sky, colors.sky, colors.blush, colors.mint, colors.lilac, colors.sky];
const clips = await (await fetch('./assets/clips.json')).json();
const sprites = Object.fromEntries(await Promise.all(Object.keys(clips).map(async name => {
  const image = new Image();
  image.src = `./assets/${name}.webp`;
  await image.decode();
  return [name, image];
})));

function pill(x, y, w, h, r, fill, stroke = '', width = 1) {
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
  ctx.fillStyle = fill;
  ctx.fill();
  if (stroke) {
    ctx.strokeStyle = stroke;
    ctx.lineWidth = width;
    ctx.stroke();
  }
}

function ellipse(x, y, w, h, fill) {
  ctx.beginPath();
  ctx.ellipse(x, y, w, h, 0, 0, tau);
  ctx.fillStyle = fill;
  ctx.fill();
}

function label(str, x, y, size, fill = colors.ink, family = 'Reel', weight = 700, align = 'left') {
  ctx.fillStyle = fill;
  ctx.font = `${weight} ${size}px ${family}, "Microsoft YaHei", sans-serif`;
  ctx.textAlign = align;
  ctx.textBaseline = 'middle';
  ctx.fillText(str, x, y);
}

function snow(x, y, r, fill, outline = '') {
  ctx.save();
  ctx.translate(x, y);
  ctx.beginPath();
  for (let i = 0; i < 6; i++) {
    const a = i * tau / 6;
    const dx = Math.cos(a), dy = Math.sin(a);
    ctx.moveTo(0, 0);
    ctx.lineTo(dx * r, dy * r);
    for (const sign of [-1, 1]) {
      const branch = a + sign * .82;
      ctx.moveTo(dx * r * .56, dy * r * .56);
      ctx.lineTo(dx * r * .56 + Math.cos(branch) * r * .29, dy * r * .56 + Math.sin(branch) * r * .29);
    }
  }
  ctx.lineCap = 'round';
  if (outline) {
    ctx.lineWidth = r * .30;
    ctx.strokeStyle = outline;
    ctx.stroke();
  }
  ctx.lineWidth = r * .115;
  ctx.strokeStyle = fill;
  ctx.stroke();
  ctx.restore();
}

function sparkle(x, y, r, fill) {
  ctx.beginPath();
  ctx.moveTo(x, y - r);
  ctx.quadraticCurveTo(x + r * .18, y - r * .17, x + r, y);
  ctx.quadraticCurveTo(x + r * .18, y + r * .17, x, y + r);
  ctx.quadraticCurveTo(x - r * .18, y + r * .17, x - r, y);
  ctx.quadraticCurveTo(x - r * .18, y - r * .17, x, y - r);
  ctx.fillStyle = fill;
  ctx.fill();
}

const paperGrain = document.createElement('canvas');
paperGrain.width = paperGrain.height = 160;
const grainCtx = paperGrain.getContext('2d');
const grain = grainCtx.createImageData(160, 160);
for (let i = 0; i < grain.data.length; i += 4) {
  const value = ((i * 997) ^ (i * 97 >>> 5) ^ (i * 31 >>> 11)) & 255;
  grain.data[i] = grain.data[i + 1] = grain.data[i + 2] = value > 125 ? 255 : 69;
  grain.data[i + 3] = value % 15;
}
grainCtx.putImageData(grain, 0, 0);
const pattern = ctx.createPattern(paperGrain, 'repeat');

function backdrop(t, shot) {
  ctx.fillStyle = colors.cream;
  ctx.fillRect(0, 0, W, H);
  const accent = accents[shot];
  ellipse(1430, 538, 532, 450, accent);
  ctx.save();
  ctx.translate(1480, 548);
  ctx.rotate(-.30);
  ctx.beginPath();
  ctx.ellipse(0, 0, 437, 343, 0, 0, tau);
  ctx.setLineDash([3, 13]);
  ctx.lineWidth = 2;
  ctx.strokeStyle = '#85a4bb99';
  ctx.stroke();
  ctx.restore();
  for (const [x, y, r, i] of [[1740, 174, 18, 0], [849, 288, 11, 1], [1831, 749, 14, 2], [918, 850, 15, 3], [1650, 920, 10, 4]]) {
    sparkle(x, y + bob(t + i, 4) * 9, r, i % 2 ? '#97b9d4' : '#fffdf7');
  }
  ctx.fillStyle = pattern;
  ctx.fillRect(0, 0, W, H);
}

function cornerBrand() {
  pill(126, 108, 193, 54, 27, '#fffdf7', '#cfdeeb', 2);
  snow(155, 135, 12, colors.blue);
  label('YUKI  /  雪', 178, 136, 21, colors.ink, 'Reel', 750);
}

function chapterMarker(shot, t) {
  const x = 130, y = 939;
  for (let i = 0; i < SHOTS.length; i++) {
    const w = i === shot ? 56 : 14;
    pill(x + i * 64, y, w, 8, 4, i === shot ? '#81a4c4' : '#d8e3e9');
    if (i === shot) pill(x + i * 64, y, w * tween(t, SHOTS[i].t0, SHOTS[i].t1), 8, 4, colors.blue);
  }
}

function sprite(name, frame, x, feet, size, { outline = false } = {}) {
  const index = Math.min(clips[name] - 1, Math.max(0, frame));
  const sx = (index % 8) * 256, sy = Math.floor(index / 8) * 256;
  ctx.save();
  ctx.translate(x, feet);
  if (outline) {
    ctx.shadowColor = '#fffdf7';
    ctx.shadowBlur = 1;
    for (let a = 0; a < 8; a++) {
      ctx.shadowOffsetX = Math.cos(a * tau / 8) * 8;
      ctx.shadowOffsetY = Math.sin(a * tau / 8) * 8;
      ctx.drawImage(sprites[name], sx, sy, 256, 256, -size / 2, -size, size, size);
    }
    ctx.shadowColor = 'transparent';
  }
  ctx.drawImage(sprites[name], sx, sy, 256, 256, -size / 2, -size, size, size);
  ctx.restore();
}

function desktop(x, y, accent, contents, angle) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(angle);
  pill(-417, -298, 836, 617, 47, '#668bad23');
  pill(-430, -321, 856, 619, 45, '#fffdf7', '#a9c1d6', 3);
  pill(-413, -253, 822, 533, 31, accent);
  for (const [i, fill] of ['#eca9bb', '#f3d78f', '#b5d6ca'].entries()) ellipse(-380 + i * 26, -288, 6.6, 6.6, fill);
  snow(318, -288, 12, '#8aabc9');
  label('Yuki', 345, -287, 21, colors.blue, 'DM', 750);
  ctx.save();
  ctx.beginPath();
  ctx.roundRect(-413, -253, 822, 533, 31);
  ctx.clip();
  ellipse(155, 165, 304, 234, '#fffdf761');
  ellipse(-252, -160, 192, 146, '#fffdf74a');
  for (const [ix, iy] of [[-355,-173], [-270,102], [270,-133], [326,153], [63,-207], [80,218]]) {
    sparkle(ix, iy, 9, '#fffdf7b9');
  }
  contents();
  ctx.restore();
  ctx.restore();
}

function folder(x, y, s, fill) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(s, s);
  pill(-103, -69, 95, 49, 15, '#dfaa6b');
  pill(-103, -51, 206, 127, 21, '#dfaa6b');
  pill(-104, -36, 208, 111, 20, fill, '#fff0c7', 3);
  pill(-74, -15, 37, 5, 2, '#fffae1');
  ctx.restore();
}

function cursor(x, y, scale, ring = 0) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(scale, scale);
  if (ring > 0 && ring < 1) {
    ctx.beginPath();
    ctx.arc(1, 1, mix(9, 57, ring), 0, tau);
    ctx.lineWidth = 4;
    ctx.strokeStyle = `rgba(94,135,179,${1-ring})`;
    ctx.stroke();
  }
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.lineTo(11, 51);
  ctx.lineTo(22, 34);
  ctx.lineTo(40, 29);
  ctx.closePath();
  ctx.fillStyle = '#fffdf7';
  ctx.strokeStyle = '#476b90';
  ctx.lineWidth = 3.3;
  ctx.lineJoin = 'round';
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

function bubble(x, y, w, message, fill, rise) {
  if (rise <= 0) return;
  ctx.save();
  ctx.translate(x, y + 22 * (1 - rise));
  ctx.globalAlpha = rise;
  pill(0, 4, w, 78, 27, '#43668d18');
  pill(0, 0, w, 78, 27, fill);
  label(message, 23, 40, 34);
  ctx.restore();
}

function hello(s) {
  folder(-275, 64, .48, colors.yellow);
  ellipse(60, 203, 138, 23, '#7da9cc29');
  const enter = ease(s, .14, 1.17);
  const y = mix(405, 220, enter) - Math.sin(enter * Math.PI) * 92;
  sprite('wave', Math.floor(tween(s, 1.12, 3.62) * 33), 72, y, 484, { outline: true });
  const fall = ease(s, .03, .88);
  ctx.save();
  ctx.translate(264, mix(-310, -154, fall) + bob(s, 3.8) * 8);
  ctx.rotate(s * .14);
  snow(0, 0, 46, '#80b3df', '#fffdf7');
  ctx.restore();
  sparkle(-140, -124, 20 * enter, '#fffdf7');
}

function peek(s) {
  const slide = ease(s, .07, 1.06);
  const reach = ease(s, .95, 2.4);
  const x = mix(-104, 74, reach);
  ellipse(10, 199, 229, 29, '#739abc27');
  sprite('play-peek', Math.floor(reach * 19), x, 219, 464, { outline: true });
  folder(mix(-530, -121, slide), 69, 1.5, colors.yellow);
  folder(306, 146, .48, '#c4daf5');
  const found = ease(s, 1.28, 1.78);
  if (found) {
    sparkle(192, -150 + bob(s, 2.2) * 8, found * 24, '#fffdf7');
    sparkle(246, -96, found * 13, '#7da8cd');
  }
}

function chat(s) {
  const frame = Math.floor(ease(s, 2.22, 4.8) * 42);
  ellipse(219, 203, 117, 19, '#9d769725');
  sprite('smile', frame, 224, 220, 385, { outline: true });
  bubble(-337, -177, 354, '雪，今天一起加油！', '#fffdf7', ease(s, 1.16, 1.56));
  bubble(-298, -68, 357, '嗯，我在这儿陪你。', '#ffeff4', ease(s, 2.5, 2.9));
  const u = ease(s, .1, 1.24);
  cursor(mix(-410, -105, u), mix(220, 64, u), .94, tween(s, 1.25, 1.74));
}

function focus(s) {
  const u = ease(s, .03, .65);
  ellipse(210, 202, 114, 21, '#6d9f862b');
  const reading = ease(s, 1.21, 1.81);
  ctx.save();
  ctx.globalAlpha = 1 - reading;
  sprite('sit-swing', Math.floor(s * 12) % 30, 209, 221, 389, { outline: true });
  ctx.globalAlpha = reading;
  sprite('reading-pose-1', 0, 209, 221 + bob(s, 2.5) * 3, 389, { outline: true });
  ctx.restore();
  const x = -345, y = mix(-235, -141, u);
  pill(x, y, 337, 250, 33, '#fffdf7', '#c0d8cc', 2);
  label('专注计时', x + 31, y + 38, 25, '#476c60');
  const left = 1500 - Math.floor(Math.max(0, s - 1.25));
  const clock = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}`;
  label(clock, x + 167, y + 107, 76, '#33584d', 'DM', 800, 'center');
  pill(x + 29, y + 166, 279, 54, 18, s < 1.25 ? '#dceee4' : '#e8f3ea');
  label(s < 1.25 ? '开始专注' : '专注中', x + 168, y + 195, 24, '#365f52', 'Reel', 750, 'center');
  const m = ease(s, .18, 1.23);
  cursor(mix(-416, -111, m), mix(229, y + 197, m), .88, tween(s, 1.25, 1.73));
}

function notes(s) {
  for (const [i, x, y] of [[0, -285, -84], [1, 268, -133], [2, -218, 99], [3, 282, 64]]) {
    const p = ease(s, .22 + i * .14, .64 + i * .14);
    if (!p) continue;
    ctx.save();
    ctx.globalAlpha = p;
    ctx.translate(x, y + bob(s + i * .14, BEAT * 2) * 12);
    ctx.rotate((i % 2 ? 1 : -1) * .19);
    pill(-33, -38, 66, 76, 24, '#fffdf7');
    ellipse(-8, 11, 11, 8, '#7d76a9');
    pill(0, -21, 5, 34, 2, '#7d76a9');
    pill(1, -22, 18, 6, 3, '#7d76a9');
    ctx.restore();
  }
}

function dance(s) {
  const progress = tween(s, .3, 4.88);
  const x = bob(s - .2, 5) * 88;
  ellipse(x, 202, 137, 23, '#8471a530');
  sprite('music-waltz', Math.floor(progress * 103), x, 226, 491, { outline: true });
  notes(s);
}

function signoff(s) {
  const u = ease(s, 0, 1.04);
  ctx.save();
  ctx.translate(1391, 554);
  ctx.rotate(mix(-.065, .035, u));
  const box = mix(1.07, .81, u);
  ctx.scale(box, box);
  pill(-351, -383, 702, 795, 134, '#759bbb22');
  pill(-356, -397, 700, 787, 126, '#fffdf7');
  pill(-331, -372, 650, 737, 108, '#cfe4f7');
  snow(215, -228 + bob(s, 4) * 12, 45, '#fffdf7');
  sparkle(-222, -150, 31, '#fffdf7');
  sparkle(249, 137, 20, '#fffdf7');
  ellipse(-7, 248, 176, 24, '#80a9d12e');
  sprite('wave', Math.floor(tween(s, .84, 3.42) * 33), -7, 274, 671, { outline: true });
  ctx.restore();
}

const scenes = [hello, peek, chat, focus, dance];
const turns = [-.036, .032, -.026, .017, -.037];

function paperWipe(t) {
  const cut = Math.round(t / 5) * 5;
  if (cut < 5 || cut > 25 || Math.abs(cut - t) > .42) return;
  const p = ease(t, cut - .41, cut + .41);
  const x = mix(-1190, W + 1190, p);
  ctx.save();
  ctx.translate(x, 550);
  ctx.rotate(-.10);
  pill(-1150, -821, 2300, 1642, 182, '#b1d1ec');
  pill(-1126, -821, 2252, 1642, 170, '#dcecf8');
  snow(-21, 0, 78, '#fffdf7');
  ctx.restore();
}

let currentShot = -1;
function render(t) {
  t = Math.max(0, Math.min(DUR - .0001, t));
  const shot = Math.floor(t / 5);
  const s = t - SHOTS[shot].t0;
  if (shot !== currentShot) {
    const [headline, detail] = captions[shot];
    title.textContent = headline;
    title.className = shot === 0 ? 'hello' : '';
    subtitle.textContent = detail;
    currentShot = shot;
  }
  const entrance = ease(s, .13, .77);
  const exit = shot === SHOTS.length - 1 ? 1 : 1 - ease(s, 4.77, 5);
  copy.style.opacity = String(entrance * exit);
  copy.style.transform = `translate(${(1 - entrance) * -34}px,${shot === 0 || shot === 5 ? 33 : 0}px)`;
  backdrop(t, shot);
  cornerBrand();
  chapterMarker(shot, t);
  if (shot < 5) {
    const zoom = shot === 0 ? mix(.90, 1, ease(s, 0, 1.36)) : 1;
    ctx.save();
    ctx.translate(1374, 546);
    ctx.scale(zoom, zoom);
    desktop(0, 0, accents[shot], () => scenes[shot](s), turns[shot] + bob(s, 6) * .012);
    ctx.restore();
    label('情境示意', 1632, 899, 20, '#486989', 'Reel', 600);
  } else {
    signoff(s);
  }
  ctx = wipe;
  ctx.clearRect(0, 0, W, H);
  paperWipe(t);
  ctx = art;
}

await Promise.allSettled([document.fonts.load('800 100px Reel', '雪'), document.fonts.load('800 100px DM', 'Yuki')]);
window.DUR = DUR;
window.render = render;
render(0);
window.READY = true;
