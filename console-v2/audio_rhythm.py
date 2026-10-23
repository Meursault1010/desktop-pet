"""Small, dependency-free DSP for playback audio. No speech/content recognition."""
from array import array
from collections import deque
import math
import statistics


class RhythmAnalyzer:
    def __init__(self):
        self.envelope = .001
        self.previous = .001
        self.lowpass = self.smooth = 0.
        self.onsets = deque(maxlen=12)
        self.last_loud = self.started = None
        self.silent_since = None
        self.bpm = 0
        self.bass_envelope = self.previous_bass = .001

    def feed(self, data, rate, channels, now):
        samples = array('f')
        samples.frombytes(data)
        if not samples or channels < 1:
            return None
        # Downsample mono to ~4 kHz; enough for loudness/rough bands and rhythm.
        stride = max(1, int(rate/4000))
        values = [sum(samples[i:i+channels])/channels
                  for i in range(0,len(samples)-channels+1,channels*stride)]
        if not values:
            return None
        if any(not math.isfinite(v) for v in values):
            return None
        actual_rate = rate/stride
        bass_alpha = 1-math.exp(-math.tau*180/actual_rate)
        treble_alpha = 1-math.exp(-math.tau*1200/actual_rate)
        total = bass = treble = 0.
        for value in values:
            self.lowpass += bass_alpha*(value-self.lowpass)
            self.smooth += treble_alpha*(value-self.smooth)
            total += value*value
            bass += self.lowpass*self.lowpass
            treble += (value-self.smooth)**2
        rms = math.sqrt(total/len(values))
        peak = max(abs(v) for v in values)
        if self.started is None:
            self.started = now
        if rms < .0015:
            self.silent_since = self.silent_since if self.silent_since is not None else now
            if now-self.silent_since > 1.2:
                self.onsets.clear()
                self.bpm = 0
        else:
            self.silent_since = None
        bass_rms = math.sqrt(bass/len(values))
        bass_onset = (bass_rms > .006 and bass_rms > self.bass_envelope*1.5
                      and bass_rms > self.previous_bass*1.18)
        onset = (rms > .008 and (bass_onset or (rms > self.envelope*1.48
                 and rms > self.previous*1.18
                 ))
                 and (not self.onsets or now-self.onsets[-1] > .25))
        sudden = peak > .3 and rms > max(.035,self.envelope*3.5)
        if onset:
            self.onsets.append(now)
        self.previous = rms
        self.envelope = self.envelope*.94+rms*.06
        self.bass_envelope = self.bass_envelope*.94+bass_rms*.06
        self.previous_bass = bass_rms
        intervals = [b-a for a,b in zip(self.onsets,list(self.onsets)[1:]) if .28 <= b-a <= 1.25]
        regular = False
        if len(intervals) >= 4 and now-self.onsets[-1] < 1.8:
            median = statistics.median(intervals)
            regular = sum(abs(i-median) < median*.18 for i in intervals)/len(intervals) >= .75
            if regular:
                self.bpm = round(60/median)
        if not regular:
            self.bpm = 0
        silent = rms < .0015
        kind = ('silent' if silent else 'rhythm' if regular else
                'sudden' if sudden else 'soft' if rms < .055 else 'active')
        return dict(kind=kind, bpm=self.bpm, onset=onset, sudden=sudden,
                    beat_at=self.onsets[-1] if self.onsets else None,
                    level=round(min(1.,rms*5),3), peak=round(min(1.,peak),3),
                    bands=[round(min(1.,math.sqrt(v/len(values))*6),3)
                           for v in (bass,max(0,total-bass-treble),treble)])
