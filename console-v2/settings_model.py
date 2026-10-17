"""本地偏好与位置存储；配置独立于安装目录，方便以后打包。"""
from dataclasses import asdict, dataclass, fields

from PySide6.QtCore import QPoint, QSettings, QStandardPaths


@dataclass(frozen=True)
class Preferences:
    size: int = 100
    opacity: int = 100
    always_on_top: bool = True
    speed: int = 48
    activity: str = '默认'
    random_movement: bool = True
    greeting: bool = True
    quiet: bool = False
    paused: bool = False
    auto_snap: bool = True


LIMITS = {'size': (50, 200), 'opacity': (30, 100), 'speed': (10, 150)}
ACTIVITIES = ('少动', '默认', '活跃')


def normalize(values):
    """损坏、过期或手动修改过的设置也不会让程序无法启动。"""
    defaults = Preferences()
    result = {}
    for field in fields(defaults):
        default = getattr(defaults, field.name)
        value = values.get(field.name, default)
        if field.name in LIMITS:
            try:
                low, high = LIMITS[field.name]
                value = max(low, min(high, int(value)))
            except (ValueError, TypeError, OverflowError):
                value = default
        elif isinstance(default, bool):
            if isinstance(value, str):
                value = {'true': True, 'false': False, '1': True, '0': False}.get(
                    value.lower(), default)
            elif not isinstance(value, bool):
                value = default
        elif field.name == 'activity' and value not in ACTIVITIES:
            value = default
        result[field.name] = value
    return Preferences(**result)


class SettingsStore:
    def __init__(self, path=None):
        if path is None:
            directory = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppLocalDataLocation)
            path = directory + '/settings.ini'
        self.settings = QSettings(str(path), QSettings.Format.IniFormat)

    def load(self):
        return normalize({field.name: self.settings.value('preferences/' + field.name)
                          for field in fields(Preferences())
                          if self.settings.contains('preferences/' + field.name)})

    def save(self, preferences):
        for key, value in asdict(preferences).items():
            self.settings.setValue('preferences/' + key, value)
        return self.sync()

    def position(self):
        point = self.settings.value('pet/position')
        return point if isinstance(point, QPoint) else None

    def save_position(self, point):
        self.settings.setValue('pet/position', point)
        return self.sync()

    def sync(self):
        self.settings.sync()
        return self.settings.status() == QSettings.Status.NoError
