"""Desktop displacement from the visible planted shoe, sampled with the pose."""
import json
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=1)
def footwork():
    return json.loads((Path(__file__).resolve().parent/'assets/actions/music-waltz/footwork.json').read_text())

def stage_position(home,size,frame):
    dx,dy=footwork()['rows'][frame]['root'];factor=size[0]/180
    return home[0]+dx*factor,home[1]+dy*factor,1.

def route_fits(home,area,size):
    """Allow transparent margins; never clamp a planted-foot trajectory."""
    left,top,width,height=area;w,h=size;factor=w/180
    low,high=footwork()['bounds']
    return (home[0]+low[0]*factor+10*factor>=left and
            home[0]+high[0]*factor+w-10*factor<=left+width and
            home[1]+low[1]*factor+20*factor>=top and
            home[1]+high[1]*factor+h-8*factor<=top+height)

class DanceStage:
    def __init__(self,pet):
        self.pet=pet;self.active=False;self.home=(0.,0.)
        self.previous_elapsed=0.;self.action=None

    def advance(self,now):
        pet=self.pet;s=pet.state;player=s.action_player;action=player.action
        allowed=(action and action.get('spatial_dance') and pet.isVisible()
                 and not pet.presence.active and pet.drag_origin is None
                 and not s.physics.active and not s.sleep.transitioning
                 and not (s.edge_attachment and s.edge_attachment.active)
                 and not (s.icon_sleep and s.icon_sleep.target))
        if not allowed:
            self.active=False;s.dance_depth_scale=1.
            return False
        elapsed=max(0.,(now-player.started)*player.speed)
        if not self.active or self.action is not action or elapsed<self.previous_elapsed-.1:
            self.home=(pet.x(),pet.y());self.area=pet.screen_area().getRect()
            if not route_fits(self.home,self.area,(pet.width(),pet.height())):
                player.stop();self.active=False;s.dance_depth_scale=1.
                return False
        self.active=True;self.action=action;self.previous_elapsed=elapsed
        requested=player.frame(now)
        if requested is None:
            self.active=False;return False
        from music_dance_asset import frame,displayed_frame
        frame(requested)
        index=displayed_frame()
        if index is not None:
            x,y,_=stage_position(self.home,(pet.width(),pet.height()),index)
            pet.move(round(x),round(y))
        s.position_x=float(pet.x());s.dance_depth_scale=1.;s.walking=False
        return True
