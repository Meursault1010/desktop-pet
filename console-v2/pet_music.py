"""WASAPI playback-only capture and low-frequency, interruptible music reactions."""
import math
import queue
import random
import threading
import time
from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import QApplication
from audio_rhythm import RhythmAnalyzer


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
                                if feature and now-emitted >= .09:
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
        self.active = ''
        self.started = self.until = self.owned_start = 0.
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
        if worker:
            worker.deleteLater()

    def receive(self, feature):
        if self.closed or not self.pet.preferences.music_reactions:
            return
        now = time.monotonic()
        self.feature = feature
        self.last_feature = now
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
        listening = bool(self.worker and self.source and not suspended and p.preferences.music_reactions)
        return dict(enabled=p.preferences.music_reactions,listening=listening,source=self.source,
                    error=self.error,kind=self.feature['kind'],label=LABELS[self.feature['kind']],
                    bpm=self.feature['bpm'],level=self.feature['level'],bands=self.feature['bands'],
                    reaction={'dance':'跟着节拍跳舞','sway':'轻轻晃一会儿','notice':'竖起耳朵听听'}.get(self.active,''),
                    suspended=suspended)

    def cancel(self, now=None):
        if not self.active:
            return
        now = time.monotonic() if now is None else now
        s = self.pet.state
        if s.action_player.started == self.owned_start:
            s.action_player.stop()
        self.active = ''
        self.next_at = now+random.uniform(35,70)
        s.ambient.defer(now,self.pet.preferences.activity)
        self.pet.state_changed.emit()

    def blocked(self):
        p,s = self.pet,self.pet.state
        return (not p.preferences.music_reactions or p.preferences.quiet or p.preferences.paused
                or not p.isVisible() or not p.desired_visible() or p.presence.active
                or p.drag_origin is not None or s.physics.active or s.travel_target is not None
                or bool(s.patrol and s.patrol.active) or QApplication.activePopupWidget() is not None
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
            if (now >= self.until or now-self.last_feature > .8 or now-self.last_audible > 1.2
                    or s.action_player.started != self.owned_start or s.action_player.action is None):
                self.cancel(now)
            return
        if now < self.next_at or now-self.last_feature > .8 or s.action_player.action or s.walking:
            return
        kind = self.feature['kind']
        if kind == 'rhythm' and self.sounding_since is not None and now-self.sounding_since >= 4 and onset:
            self.active,key,duration = 'dance','celebrate',random.uniform(8,14)
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
        speed = max(.65,min(1.5,self.feature['bpm']/110)) if self.active == 'dance' else .75
        s.action_player.play(key,now=now,loop=True,speed=speed)
        self.started = self.owned_start = now
        self.until = now+duration
        self.pet.state_changed.emit()

    def transform(self, now):
        if not self.active or self.active == 'notice':
            return 0.,0.,0.
        age = max(0.,now-self.started)
        fade = min(1.,age/.4,max(0.,(self.until-now)/.5))
        hz = (self.feature['bpm'] or 90)/60
        phase = age*math.tau*hz
        if self.active == 'dance':
            return 3.5*math.sin(phase/2)*fade,-5*(1-math.cos(phase))*fade,5*math.sin(phase/2)*fade
        return 1.5*math.sin(phase/2)*fade,-1.5*(1-math.cos(phase/2))*fade,2.5*math.sin(phase/2)*fade

    def cleanup(self):
        self.closed = True
        self.timer.stop()
        self.cancel()
        if self.worker:
            self.worker.stop()
            self.worker.wait(3000)
