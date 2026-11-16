export const BPM = 96;
export const BEAT = 60 / BPM;
export const DUR = 30;
export const SHOTS = [
  { id: 'hello', label: '嗨，我是 Yuki', t0: 0, t1: 5 },
  { id: 'peek', label: '从文件夹后探头', t0: 5, t1: 10 },
  { id: 'chat', label: '和雪聊两句', t0: 10, t1: 15 },
  { id: 'focus', label: '一起专注', t0: 15, t1: 20 },
  { id: 'dance', label: '随音乐舞动', t0: 20, t1: 25 },
  { id: 'signoff', label: '桌面见', t0: 25, t1: DUR },
];
export const CUES = [
  { t: .42, sfx: 'snow' }, { t: 1.25, sfx: 'pop' },
  { t: 5, sfx: 'swish' }, { t: 6.35, sfx: 'pop' },
  { t: 10, sfx: 'swish' }, { t: 11.25, sfx: 'click' },
  { t: 12.5, sfx: 'reply' }, { t: 15, sfx: 'swish' },
  { t: 16.25, sfx: 'click' }, { t: 20, sfx: 'swish' },
  { t: 20.625, sfx: 'pop' }, { t: 25, sfx: 'snow' },
  { t: 26.25, sfx: 'reply' },
];
export const HOLDS = [[28.75, 30]];
export const DROPS = [];
