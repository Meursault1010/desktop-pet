"""Local wall time selects a rhythm; monotonic time still schedules animations."""
import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def schedule():
    return json.loads((Path(__file__).parent/'assets/daily-routine.json').read_text(encoding='utf-8'))


def current_period(local_time=None):
    hour = (local_time or datetime.now()).hour
    return next(period for period in reversed(schedule()) if hour >= period['start'])


class DailyRoutine:
    def __init__(self):
        self.period = current_period()

    def update(self, local_time=None):
        period = current_period(local_time)
        changed = period['key'] != self.period['key']
        self.period = period
        return changed

    def snapshot(self):
        return {'key': self.period['key'], 'name': self.period['name'],
                'resting': self.period['key'] == 'night'}
