import { DUR, BPM, CUES } from './timeline.js';
export { DUR };

const verse = [
  ['D3', ['F#4', 'A4', 'B4', 'F#4']],
  ['B2', ['E4', 'F#4', 'A4', 'D4']],
  ['G2', ['B4', 'A4', 'F#4', 'E4']],
  ['A2', ['E4', 'F#4', 'E4', 'C#4']],
];

function musicTrack(S) {
  const keys = S.bus('keys', { gain: .46, reverb: .14 });
  const melody = S.bus('kalimba', { gain: .82, reverb: .21, highpass: 150 });
  const wood = S.bus('wood', { gain: .17, pan: .14, reverb: .13 });
  const roots = ['add9', 'min7', 'maj7', 'sus4'];
  const offsets = [0, .75, 1.5, 2.75];
  for (let bar = 0; bar < 11; bar++) {
    const chord = bar % verse.length;
    const [root, notes] = verse[chord];
    const t = S.bar(bar);
    const quiet = bar === 6 || bar === 7;
    keys.add(S.keys(S.chord(root, roots[chord]), 1.62, { index: .75, decay: .68 }), t, { gain: quiet ? .53 : .82 });
    for (const [i, note] of notes.entries()) {
      if (quiet && i === 2) continue;
      melody.add(S.mallet(note, .57, { material: 'kalimba', bright: .28, decay: .25 }),
        t + S.beat(offsets[i]), { gain: quiet ? .54 : [.91, .63, .77, .62][i], pan: i % 2 ? .17 : -.17 });
    }
    if (bar > 1 && !quiet) {
      wood.add(S.rim({ tone: 530, decay: .042 }), t + S.beat(1.25));
      wood.add(S.rim({ tone: 425, decay: .035 }), t + S.beat(3.25), { gain: .68 });
    }
  }
  keys.add(S.keys(S.chord('D3', 'add9'), 2.2, { index: .55, decay: .94 }), S.bar(11));
  melody.add(S.mallet('D5', 1.06, { material: 'kalimba', bright: .29, decay: .42 }), S.bar(11), { gain: .58 });
}

function effectsTrack(S) {
  const effects = S.bus('effects', { gain: .36, reverb: .22, highpass: 220, lowpass: 4900 });
  for (const { t, sfx } of CUES) {
    if (sfx === 'snow') {
      effects.add(S.bell('A5', .52, { ratio: 2, index: .8 }), t, { gain: .45 });
      effects.add(S.bell('D6', .63, { ratio: 2, index: .68 }), t + .12, { gain: .3, pan: .25 });
    } else if (sfx === 'swish') {
      effects.add(S.whoosh(.33, { peak: .62 }), t - .20, { gain: .16 });
    } else if (sfx === 'reply') {
      effects.add(S.mallet('F#5', .4, { material: 'glock', bright: .2 }), t, { gain: .52 });
    } else if (sfx === 'click') {
      effects.add(S.tick({ tone: 780 }), t, { gain: .36 });
    } else {
      effects.add(S.pop('D5'), t, { gain: .42 });
    }
  }
}

export default function score(S) {
  S.tempo(BPM);
  S.space({ room: .44, damp: .58, width: .76 });
  musicTrack(S);
  effectsTrack(S);
}
