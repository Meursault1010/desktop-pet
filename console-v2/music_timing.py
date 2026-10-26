"""Continuous, bounded tempo following for the existing authored dance.

120 BPM is a playback reference, not a claim of annotated foot contacts.
Changing speed preserves the current animation position.
Music dancing uses a relaxed 50% pace; other actions are unaffected.
"""
import math

DANCE_PACE = .5


def dance_speed(bpm):
    if not isinstance(bpm, (int, float)) or not math.isfinite(bpm) or bpm <= 0:
        return DANCE_PACE
    return DANCE_PACE * max(.8, min(1.2, bpm/120.))


def follow_tempo(player, bpm, now, dt):
    position = max(0., (now-player.started)*player.speed)
    target = dance_speed(bpm)
    # A two-second response, capped at 8% speed change per second.
    delta = (target-player.speed)*(1-math.exp(-max(0., dt)/2.))
    limit = .08*max(0., dt)
    speed = player.speed+max(-limit, min(limit, delta))
    player.speed = speed
    player.started = now-position/speed
    action = getattr(player, 'action', None)
    duration = sum(action['durations'])/1000 if action else 10.
    return player.started, now+max(0., duration-position)/speed
