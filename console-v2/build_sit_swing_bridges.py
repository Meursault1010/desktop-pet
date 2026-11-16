"""Layout for the densified side-saddle leg swing: 12 key poses + 4 drawn bridges.

The runtime rerolls the dwell (base pose <-> one small gesture at a time), so a
bridge frame has to be addressable from the gesture it belongs to. Each bridge
sits twice in the linear clip - once leaving the base pose, once returning to it
- which keeps the library preview honest without a second copy of the schedule.
"""
from pathlib import Path
import json
import random

from PIL import Image

ROOT = Path(__file__).resolve().parent
KEYS = ROOT / 'action-work/sit-swing-lock/frames'
OUT = ROOT / 'action-work/sit-swing-bridge'

# (clip index, key pose, role, hold ms). role: key | bridge | base | blink
LAYOUT = (
    ('kf1', 'key', 320),
    ('kf2', 'key', 400),
    ('kf3', 'key', 380),
    ('kf4', 'base', 1500),
    ('b45', 'bridge', 130), ('kf5', 'key', 520), ('b45', 'bridge', 130),
    ('kf4', 'base', 1500),
    ('b46', 'bridge', 130), ('kf6', 'key', 520), ('b46', 'bridge', 130),
    ('kf4', 'base', 1500),
    ('kf7', 'blink', 140),
    ('kf4', 'base', 1500),
    ('b48', 'bridge', 130), ('kf8', 'key', 520), ('b48', 'bridge', 130),
    ('kf4', 'base', 1500),
    ('b49', 'bridge', 130), ('kf9', 'key', 560), ('b49', 'bridge', 130),
    ('kf4', 'base', 1200),
    ('kf10', 'key', 320),
    ('kf11', 'key', 340),
    ('kf12', 'key', 360),
)

# Key pose -> published frame file of the locked clip.
KEY_SOURCE = {'kf1': 1, 'kf2': 2, 'kf3': 3, 'kf4': 4, 'kf5': 5, 'kf6': 6,
              'kf7': 7, 'kf8': 8, 'kf9': 9, 'kf10': 28, 'kf11': 29, 'kf12': 30}

# gesture index -> (bridge in, bridge out) for the reroll.
BRIDGES = {5: (4, 6), 9: (8, 10), 15: (14, 16), 19: (18, 20)}
BASE = 3
BLINK = 12
GESTURES = (5, 9, 15, 19)


def durations():
    return [hold for _, _, hold in LAYOUT]


def roles():
    return [role for _, role, _ in LAYOUT]


def bridge_targets():
    """The four pose pairs that still need a drawn in-between."""
    return {'b45': ('kf4', 'kf5'), 'b46': ('kf4', 'kf6'),
            'b48': ('kf4', 'kf8'), 'b49': ('kf4', 'kf9')}


def key_frames():
    return {name: Image.open(KEYS / f'{index:02d}.png').convert('RGBA')
            for name, index in KEY_SOURCE.items()}


def reroll(rng=random):
    """Mirror of action_player.ground_idle_timeline with bridge slots inserted."""
    order = [0, 1, 2, BASE]
    holds = durations()
    times = [holds[0], holds[1], holds[2], rng.randint(1000, 2200)]
    for gesture in rng.sample(GESTURES, rng.randint(2, len(GESTURES))):
        bridge_in, bridge_out = BRIDGES[gesture]
        times_gesture = (rng.randint(140, 220) if gesture == 5 else rng.randint(350, 650))
        order.extend((bridge_in, gesture, bridge_out, BASE))
        times.extend((rng.randint(110, 170), times_gesture,
                      rng.randint(110, 170), rng.randint(1400, 2600)))
        if rng.random() < .6:
            order.extend((BLINK, BASE))
            times.extend((rng.randint(100, 160), rng.randint(700, 1500)))
    order.extend(range(len(LAYOUT) - 3, len(LAYOUT)))
    times.extend(holds[-3:])
    return order, times


def grey_preview(seed=5, seconds=13.0):
    """Placeholder animation: bridge slots use a 50/50 blend of their endpoints."""
    frames = key_frames()
    standins = {}
    for name, (left, right) in bridge_targets().items():
        standins[name] = Image.blend(frames[left], frames[right], .5)
    images = []
    for name, role, _ in LAYOUT:
        source = frames[name] if role != 'bridge' else standins[name]
        card = Image.new('RGB', (256, 256), '#24334a')
        card.paste(source, mask=source.getchannel('A'))
        images.append(card)
    order, times = reroll(random.Random(seed))
    shots, holds = [], []
    elapsed = 0
    while elapsed < seconds * 1000:
        for index, frame in enumerate(order):
            shots.append(images[frame])
            holds.append(times[index])
            elapsed += times[index]
            if elapsed >= seconds * 1000:
                break
    shots = [shot.resize((200, 200), Image.LANCZOS) for shot in shots]
    shots[0].save(OUT / 'grey-preview.gif', save_all=True, append_images=shots[1:],
                  duration=holds, loop=0, optimize=True)
    return len(shots)


def main():
    OUT.mkdir(exist_ok=True)
    count = grey_preview()
    report = {'frames': len(LAYOUT), 'durations': durations(),
              'duration_ms': sum(durations()), 'roles': roles(),
              'bridges': bridge_targets(), 'reroll_frame_count_sample': None,
              'grey_shots': count}
    (OUT / 'layout.json').write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                     encoding='utf-8')
    print(f'{len(LAYOUT)} frames, {sum(durations())} ms, grey preview {count} shots')


if __name__ == '__main__':
    main()
