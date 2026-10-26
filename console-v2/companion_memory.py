"""Content-free companionship counters stored beside the local settings."""
import json
import os
import time
from datetime import date, datetime
from pathlib import Path

VERSION = 1
COUNTERS = ('clicks', 'headpats', 'focus_minutes', 'greetings')
MAX_DAYS = 800


def _stamp(now=None):
    return datetime.fromtimestamp(time.time() if now is None else now).isoformat(timespec='seconds')


def _empty(now=None):
    return {'version': VERSION, 'first_seen': _stamp(now), 'last_interaction': _stamp(now),
            'days': {}, 'clicks': 0, 'headpats': 0, 'focus_minutes': 0, 'greetings': 0}


def _counter(value):
    return value if type(value) is int and 0 <= value <= 100_000_000 else 0


class CompanionMemory:
    """Only counts and local dates: never text, window titles or file names."""

    def __init__(self, store, enabled=True, path=None):
        self.path = Path(path) if path else store.directory() / 'companion-memory.json'
        self.enabled = bool(enabled)
        self.error = ''
        self.data = self._load()
        if self.enabled and not self.data.get('first_seen'):
            self.data = _empty()
            self.save()

    def _load(self):
        try:
            value = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return _empty() if self.enabled else {}
        if not isinstance(value, dict):
            return _empty() if self.enabled else {}
        result = {'version': VERSION, 'first_seen': '', 'last_interaction': '',
                  'days': {}, 'clicks': 0, 'headpats': 0, 'focus_minutes': 0, 'greetings': 0}
        for key in ('first_seen', 'last_interaction'):
            if isinstance(value.get(key), str) and len(value[key]) <= 40:
                result[key] = value[key]
        for key in COUNTERS:
            result[key] = _counter(value.get(key))
        days = value.get('days')
        if isinstance(days, dict):
            for key, entry in list(days.items())[-MAX_DAYS:]:
                if not isinstance(key, str) or len(key) != 10 or not isinstance(entry, dict):
                    continue
                try:
                    date.fromisoformat(key)
                except ValueError:
                    continue
                result['days'][key] = {name: _counter(entry.get(name)) for name in COUNTERS}
        self.error = ''
        return result

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        if self.enabled and not self.data.get('first_seen'):
            self.data = _empty()
            self.save()

    def record(self, kind, amount=1, now=None):
        if not self.enabled or kind not in COUNTERS:
            return False
        if type(amount) is not int or not 1 <= amount <= 100_000:
            return False
        stamp = time.time() if now is None else now
        day = date.fromtimestamp(stamp).isoformat()
        self.data = {**self.data, kind: self.data.get(kind, 0) + amount}
        counts = self.data.setdefault('days', {}).setdefault(day, {name: 0 for name in COUNTERS})
        counts[kind] = counts.get(kind, 0) + amount
        self.data['last_interaction'] = _stamp(stamp)
        if len(self.data['days']) > MAX_DAYS:
            for key in sorted(self.data['days'])[:len(self.data['days'])-MAX_DAYS]:
                self.data['days'].pop(key, None)
        return self.save()

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(self.data, ensure_ascii=False, separators=(',', ':')),
                                 encoding='utf-8')
            os.replace(temporary, self.path)
            self.error = ''
            return True
        except OSError:
            self.error = '关系记忆无法写入本机'
            return False

    def clear(self, now=None):
        self.data = _empty(now)
        self.error = ''
        return self.save()

    def snapshot(self, now=None):
        stamp = time.time() if now is None else now
        today = date.fromtimestamp(stamp).isoformat()
        counts = self.data.get('days', {}).get(today, {})
        days_together = 0
        first_seen = self.data.get('first_seen') or ''
        if first_seen:
            try:
                days_together = max(1, (date.fromtimestamp(stamp) - datetime.fromisoformat(first_seen).date()).days+1)
            except ValueError:
                days_together = 0
        return {'enabled': self.enabled, 'first_seen': first_seen,
                'last_interaction': self.data.get('last_interaction', ''),
                'days_together': days_together,
                'clicks': _counter(self.data.get('clicks')),
                'headpats': _counter(self.data.get('headpats')),
                'focus_minutes': _counter(self.data.get('focus_minutes')),
                'greetings': _counter(self.data.get('greetings')),
                'today': {name: _counter(counts.get(name)) for name in COUNTERS},
                'error': self.error}
