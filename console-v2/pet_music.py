"""WASAPI playback-only capture and low-frequency, interruptible music reactions."""
import math
import queue
import random
import threading
import time
from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import QApplication
from audio_rhythm import RhythmAnalyzer
from music_timing import dance_speed, follow_tempo
from music_dance_asset import ACTION_ID as DANCE_ACTION, preload as preload_dance, ready as dance_ready
from pet_ui_style import companion_menu_for


LABELS = dict(silent='等待声音',rhythm='节奏渐渐清晰',sudden='突然响了一声',soft='轻柔的声音',active='活跃的声音')


class PlaybackWorker(QThread):
    features = Signal(object)
    status = Signal(str,str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.stopping = threading.Event()

    def stop(self):
        self.stopping.set()

    def run(self):
        # Import inside the worker so unavailable audio drivers never prevent launch.
        try:
            import pyaudiowpatch as pa
            while not self.stopping.is_set():
                try:
                    packets = queue.Queue(maxsize=6)
                    analyzer = RhythmAnalyzer()
                    with pa.PyAudio() as audio:
                        device = audio.get_default_wasapi_loopback()
                        if not device.get('isLoopbackDevice'):
                            raise RuntimeError('Playback loopback unavailable')
                        channels = min(2,int(device['maxInputChannels']))
                        rate = int(device['defaultSampleRate'])
                        def callback(data, count, timing, flags):
                            if not self.stopping.is_set():
                                try:
                                    packets.put_nowait((data,time.monotonic()))
                                except queue.Full:
                                    pass
                            return (None,pa.paComplete if self.stopping.is_set() else pa.paContinue)
                        with audio.open(format=pa.paFloat32,channels=channels,rate=rate,input=True,
                                        input_device_index=device['index'],frames_per_buffer=1024,
                                        stream_callback=callback) as stream:
                            self.status.emit(str(device['name']).replace(' [Loopback]',''),'')
                            emitted = time.monotonic()
                            pending_onset = pending_sudden = False
                            last_packet = emitted
                            while not self.stopping.is_set() and stream.is_active():
                                try:
                                    data, now = packets.get(timeout=.1)
                                    last_packet = now
                                    feature = analyzer.feed(data,rate,channels,now)
                                except queue.Empty:
                                    now = time.monotonic()
                                    feature = analyzer.feed(bytes(1024*channels*4),rate,channels,now) if now-last_packet > .3 else None
                                if feature:
                                    pending_onset |= feature['onset']
                                    pending_sudden |= feature['sudden']
                                if feature and (feature['onset'] or now-emitted >= .09):
                                    feature['onset'],feature['sudden'] = pending_onset,pending_sudden
                                    self.features.emit(feature)
                                    pending_onset = pending_sudden = False
                                    emitted = now
                            if not self.stopping.is_set():
                                raise OSError('Playback device disconnected')
                except (OSError,LookupError,RuntimeError,ValueError):
                    if not self.stopping.is_set():
                        self.status.emit('','未连接播放设备，正在重试；切换声卡后可关闭再开启。')
                        self.stopping.wait(4)
        except ImportError:
            self.status.emit('','缺少系统音频组件，请重新构建 yuki。')


class MusicCompanion(QObject):
    def __init__(self, pet):
        super().__init__(pet)
        self.pet = pet
        self.worker = None
        self.closed = False
        self.source = self.error = ''
        self.feature = dict(kind='silent',bpm=0,level=0.,bands=[0.,0.,0.],onset=False,sudden=False)
        self.last_feature = 0.
        self.sounding_since = None
        self.last_audible = 0.
        self.last_rhythm = None
        self.session_bpm = 0.
        self.resting_until = 0.
        self.active = ''
        self.started = self.until = self.owned_start = 0.
        self.owned_generation = None
        self.last_tempo_tick = 0.
        self.dance_end_position = None
        self.next_at = time.monotonic()+4
        self.pending_onset = self.pending_sudden = False
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.sync)

    def start(self):
        self.timer.start()
        self.sync()

    def sync(self):
        p = self.pet
        wanted = (not self.closed and p.preferences.music_reactions and p.isVisible()
                  and p.desired_visible() and not p.preferences.quiet and not p.preferences.paused)
        if not wanted:
            self.cancel()
            if self.worker:
                self.worker.stop()
            return
        preload_dance()
        if not self.worker and QApplication.platformName() != 'offscreen':
            worker = PlaybackWorker(self)
            self.worker = worker
            worker.features.connect(self.receive)
            worker.status.connect(self.device_status)
            worker.finished.connect(self.finished)
            worker.start()

    def finished(self):
        worker = self.worker
        self.worker = None
        self.source = ''
        self.feature = dict(kind='silent',bpm=0,level=0.,bands=[0.,0.,0.],onset=False,sudden=False)
        self.sounding_since = None
        self.last_rhythm = None
        if worker:
            worker.deleteLater()

    def receive(self, feature):
        if self.closed or not self.pet.preferences.music_reactions:
            return
        now = time.monotonic()
        if self.pet.state.sleep.active and feature['level'] >= .75 and feature['sudden']:
            self.pet.state.sleep.wake(self.pet, '较大播放声音', now)
        self.feature = feature
        self.last_feature = now
        if feature['kind'] == 'rhythm':
            self.last_rhythm = now
            self.session_bpm = feature['bpm']
        self.pending_onset |= feature['onset']
        self.pending_sudden |= feature['sudden']
        if feature['kind'] != 'silent':
            if self.sounding_since is None or now-self.last_audible > 1.2:
                self.sounding_since = now
            self.last_audible = now
        elif now-self.last_audible > 1.2:
            self.sounding_since = None

    def device_status(self, source, error):
        self.source, self.error = source,error
        self.pet.state_changed.emit()

    def snapshot(self):
        p = self.pet
        suspended = p.preferences.quiet or p.preferences.paused or not p.desired_visible()
        reason = ('安静模式已开启，请关闭后聆听音乐' if p.preferences.quiet else
                  '宠物已暂停，请恢复后聆听音乐' if p.preferences.paused else
                  '宠物已隐藏' if not p.desired_visible() else '')
        listening = bool(self.worker and self.source and not suspended and p.preferences.music_reactions)
        return dict(enabled=p.preferences.music_reactions,listening=listening,source=self.source,
                    error=self.error,kind=self.feature['kind'],label=LABELS[self.feature['kind']],
                    bpm=self.feature['bpm'],level=self.feature['level'],bands=self.feature['bands'],
                    reaction={'dance':'跟着节拍跳舞','sway':'轻轻晃一会儿','notice':'竖起耳朵听听'}.get(self.active,'跳累了，歇一会儿再继续' if time.monotonic() < self.resting_until else ''),
                    suspended=suspended,suspend_reason=reason)

    def cancel(self, now=None, *, rest=False):
        if not self.active:
            return
        now = time.monotonic() if now is None else now
        s = self.pet.state
        owned = (s.action_player.started == self.owned_start
                 and s.action_player.generation == self.owned_generation)
        if owned:
            s.action_player.stop()
        if self.active == 'dance' and self.pet.drag_origin is None and not s.physics.active:
            self.pet.animator.timer.setInterval(16)
        was_dance = self.active == 'dance'
        self.active = ''
        self.dance_end_position = None
        self.next_at = now+random.uniform(12,20) if rest and was_dance else now+random.uniform(3,6)
        self.resting_until = self.next_at if rest and was_dance else 0.
        if owned and rest and was_dance:
            self.pet.dance_recovery.start(now)
        s.ambient.defer(now,self.pet.preferences.activity)
        self.pet.state_changed.emit()

    def blocked(self):
        p,s = self.pet,self.pet.state
        popup = QApplication.activePopupWidget()
        return (s.sleep.active or s.sleep.transitioning or not p.preferences.music_reactions or p.preferences.quiet or p.preferences.paused
                or not p.isVisible() or not p.desired_visible() or p.presence.active
                or p.drag_origin is not None or s.physics.active or s.travel_target is not None
                or bool(s.patrol and s.patrol.active)
                or (popup is not None and companion_menu_for(p, popup) is None)
                or bool(s.icon_sleep and s.icon_sleep.target)
                or bool(s.edge_attachment and s.edge_attachment.active)
                or bool(getattr(p.controller,'quick_pending',None))
                or bool(p.bubble.parts and p.bubble.kind != 'ambient'))

    def tick(self, now):
        s = self.pet.state
        onset,sudden = self.pending_onset,self.pending_sudden
        self.pending_onset = self.pending_sudden = False
        if self.blocked():
            self.cancel(now)
            return
        if self.active:
            if (self.active == 'dance' and s.action_player.started == self.owned_start and s.action_player.action
                    and s.action_player.generation == self.owned_generation):
                dt = max(0., min(.1, now-self.last_tempo_tick))
                self.last_tempo_tick = now
                bpm = self.feature['bpm'] if self.feature['kind'] == 'rhythm' else self.session_bpm
                self.owned_start, _ = follow_tempo(s.action_player, bpm, now, dt)
                if self.dance_end_position is not None:
                    position=max(0.,(now-s.action_player.started)*s.action_player.speed)
                    self.until=now+max(0.,self.dance_end_position-position)/s.action_player.speed
            if (now >= self.until or now-self.last_feature > 2.5 or now-self.last_audible > 3
                    or s.action_player.started != self.owned_start or s.action_player.action is None
                    or s.action_player.generation != self.owned_generation):
                self.cancel(now, rest=now >= self.until)
            return
        if companion_menu_for(self.pet, QApplication.activePopupWidget()) is not None:
            return
        ambient = s.ambient.current
        ambient_owned = bool(ambient and s.action_player.action
                             and s.action_player.started == ambient[1]
                             and not s.action_player.action['id'].startswith('sleep'))
        if (now < self.next_at or now-self.last_feature > 2.5
                or (s.action_player.action and not ambient_owned) or s.walking
                or not s.gait_settled(now)):
            return
        kind = self.feature['kind']
        if (self.last_rhythm is not None and now-self.last_rhythm <= 8
                and kind != 'silent' and self.sounding_since is not None and now-self.sounding_since >= 4):
            if not dance_ready():
                return
            self.active,key,duration = 'dance',DANCE_ACTION,random.uniform(30,50)
        elif sudden:
            self.active,key,duration = 'notice','curious',4.
        elif kind in ('soft','active') and self.sounding_since is not None and now-self.sounding_since >= 8:
            self.active,key,duration = 'sway','smile',random.uniform(5,9)
        else:
            return
        if s.routine.period['key'] == 'night':
            self.active = ''
            self.next_at = now+40
            return
        s.ambient.current = None
        s.gait_until = 0
        speed = dance_speed(self.feature['bpm'] if self.feature['kind'] == 'rhythm' else self.session_bpm) if self.active == 'dance' else .75
        beat_at = self.feature.get('beat_at')
        start = (max(now-.15, min(now, beat_at)) if self.active == 'dance'
                 and isinstance(beat_at, (int,float)) and math.isfinite(beat_at) else now)
        s.action_player.play(key,now=start,loop=True,speed=speed)
        if self.active == 'dance':
            self.pet.animator.timer.setInterval(16)
        self.started = self.owned_start = start
        self.owned_generation = s.action_player.generation
        self.last_tempo_tick = now
        if self.active == 'dance':
            # Finish a whole closed phrase instead of cutting to idle mid-turn.
            phrase=sum(s.action_player.action['durations'])/1000
            low=math.ceil(30*speed/phrase)
            high=max(low,math.floor(50*speed/phrase))
            cycles=max(low,min(high,round(duration*speed/phrase)))
            self.dance_end_position=cycles*phrase
            self.until=start+self.dance_end_position/speed
        else:
            self.dance_end_position=None
            self.until=start+duration/speed
        self.resting_until = 0.
        self.pet.state_changed.emit()

    def transform(self, now):
        if not self.active or self.active == 'notice':
            return 0.,0.,0.
        age = max(0.,now-self.started)
        fade = min(1.,age/.4,max(0.,(self.until-now)/.5))
        hz = (self.feature['bpm'] or 90)/60
        phase = age*math.tau*hz
        if self.active == 'dance':
            # This clip already includes its own continuous rise/fall and steps.
            return 0.,0.,0.
        return 1.5*math.sin(phase/2)*fade,-1.5*(1-math.cos(phase/2))*fade,2.5*math.sin(phase/2)*fade

    def cleanup(self):
        self.closed = True
        self.timer.stop()
        self.cancel()
        if self.worker:
            self.worker.stop()
            self.worker.wait(3000)
