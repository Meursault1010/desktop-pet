"""Interruptible recovery after a completed dance; never after a user cancellation."""
from action_player import catalog

ACTION_ID='dance-rest'

class DanceRecovery:
    def __init__(self,pet):
        self.pet=pet
        self.watched=None
        self.owned_start=None
        self.owned_generation=None
        self.until=0.
        self.exit_after_recovery=False

    def blocked(self):
        p=self.pet;s=p.state
        return (not p.isVisible() or p.drag_origin is not None or p.presence.active
                or p.preferences.paused or p.preferences.quiet or s.physics.active
                or s.sleep.transitioning or s.travel_target is not None
                or bool(s.patrol and s.patrol.active)
                or bool(s.edge_attachment and s.edge_attachment.active)
                or bool(s.icon_sleep and s.icon_sleep.target)
                or bool(getattr(p.controller,'quick_pending',None))
                or bool(p.bubble.parts and p.bubble.kind!='ambient'))

    def start(self,now):
        p=self.pet;s=p.state;player=s.action_player
        self.watched=None
        if self.blocked() or ACTION_ID not in catalog():return False
        if player.action and player.action['id']!='music-waltz':return False
        s.ambient.current=None;s.walking=False;s.gait_until=0
        player.play(ACTION_ID,now=now)
        self.owned_start=player.started
        self.owned_generation=player.generation
        duration=sum(player.action['durations'])/1000
        self.until=now+duration
        self.exit_after_recovery=True
        s.ambient.defer(now,p.preferences.activity)
        if s.music:
            s.music.resting_until=max(s.music.resting_until,now+duration)
            s.music.next_at=max(s.music.next_at,now+duration+3)
        p.state_changed.emit()
        return True

    def tick(self,now):
        s=self.pet.state;player=s.action_player;action=player.action
        if self.owned_start is not None:
            if (player.started!=self.owned_start or not action or action['id']!=ACTION_ID
                    or player.generation!=self.owned_generation):
                completed=(player.started==self.owned_start and action is None
                           and player.generation==self.owned_generation+1 and now>=self.until)
                self.owned_start=None
                if completed and self.exit_after_recovery and not self.blocked():
                    self.exit_after_recovery=False
                    duration=s.ambient.play(player,'sit-neat',now,exit_only=True)
                    s.ambient.current=None
                    from action_inbetweens import manifest, pair_key, prefetch
                    before=('dance-rest',catalog()['dance-rest']['frames']-1)
                    after=('sit-neat',3)
                    if pair_key(before,after) in manifest():
                        player.begin_handover(before,after,now,.34)
                        prefetch(((before,after),))
                    self.owned_start=player.started
                    self.owned_generation=player.generation
                    self.until=player.started+duration
                    return
                self.exit_after_recovery=False
            elif self.blocked():
                player.stop();self.owned_start=None;self.exit_after_recovery=False
                s.ambient.defer(now,self.pet.preferences.activity)
            return
        if self.blocked():
            self.watched=None
            return
        if action and action['id']=='music-waltz':
            if player.loop:
                self.watched=None  # music owner finishes full phrases explicitly
                return
            self.watched=(player.started,sum(action['durations'])/1000/player.speed)
            if now-player.started>=self.watched[1]:self.start(now)
        elif self.watched:
            start,duration=self.watched;self.watched=None
            if action is None and player.started==start and now-start>=duration:
                self.start(now)
