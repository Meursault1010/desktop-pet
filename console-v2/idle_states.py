"""Shared posture taxonomy for the scheduler, IPC and action library."""
import json
import time
from pathlib import Path

CONFIG = json.loads((Path(__file__).parent/'assets/actions/idle-states.json').read_text(encoding='utf-8'))
STATES = {state['id']: state for state in CONFIG['states']}
ACTION_STATE = {key: state['id'] for state in STATES.values() for key in state['actions']}
AUTOMATIC_ACTIONS = tuple(key for state in STATES.values() for key in state['automatic'])


def posture_for(action_id):
    return ACTION_STATE.get(action_id)


def snapshot(state):
    """Report the visible idle owner; manual/physics/attachments stay distinct."""
    sleep = state.sleep
    action = state.action_player.action
    automatic = bool(action and state.ambient.current
                     and state.ambient.current[0] == action['id']
                     and state.ambient.current[1] == state.action_player.started)
    posture = 'sleep' if sleep.transitioning else posture_for(action['id']) if action else 'stand'
    interacting = (not sleep.transitioning and (state.physics.active
                   or state.drag_feedback is not None or state.walking
                   or time.monotonic() < state.gait_until
                   or bool(state.edge_attachment and state.edge_attachment.active)
                   or bool(state.icon_sleep and state.icon_sleep.target)))
    if interacting:
        return dict(state=None, name='互动', action_id=action['id'] if action else None,
                    automatic=False, phase='interaction')
    return dict(state=posture, name=STATES[posture]['name'] if posture else '互动',
                action_id=action['id'] if action else None,
                automatic=sleep.transitioning or automatic or action is None,
                phase=sleep.phase if sleep.transitioning else 'action' if action else 'rest')
