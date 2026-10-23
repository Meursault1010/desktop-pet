"""Deterministic 30-minute scheduler soak; isolated settings and synthetic desktop.

This does not claim a real multi-monitor or thirty-minute wall-clock UI test.
Run with the project's Python. Report includes separate real Windows probe cost.
"""
import json
import random
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from PySide6.QtGui import QImage, QColor
from test_pet_patrol import PatrolTests
from desktop_icons import desktop_exposed


def main():
    PatrolTests.setUpClass()
    case = PatrolTests('test_busy_user_gets_quiet_backoff')
    case.setUp()
    try:
        p, life = case.pet, case.life
        icon = case.icon()
        image = QImage(48,48,QImage.Format.Format_RGBA8888)
        image.fill(QColor('#78abc8'))
        life.icons.cache_images[icon['id']] = image
        clock = [case.now]
        random.seed(20261023)
        stories = Counter()
        original = life.complete
        def complete(now):
            stories[life.story or life.kind] += 1
            original(now)
        life.complete = complete
        life.next_at = clock[0]+5
        times = []
        peak_budget = 0.
        moved = 0.
        before = p.pos()
        with patch('time.monotonic',side_effect=lambda:clock[0]), \
                patch.object(life,'exposed',side_effect=lambda *a,**k:not 300 <= clock[0]-case.now < 360), \
                patch.object(p.state.routine,'update',return_value=False):
            for i in range(18000):
                clock[0] = case.now+i*.1
                life.icons.scanned_at = clock[0]
                if i == 5000:
                    p.bubble.say('测试交流')
                if i == 5100:
                    p.bubble.clear()
                if i == 8000:
                    life.icons.icons=[]  # Synthetic Explorer loss/recovery.
                if i == 9200:
                    life.icons.icons=[icon]
                p.state.action_player.frame(clock[0])
                start = time.perf_counter()
                life.tick(clock[0],.1,case.at+timedelta(seconds=i*.1))
                p.animator.update_ambient(clock[0])
                p.animator.advance_roll(clock[0])
                times.append((time.perf_counter()-start)*1000)
                if p.pos() != before:
                    moved += .1
                before=p.pos()
                peak_budget=max(peak_budget,60-life.policy.remaining(clock[0],'默认'))
                assert peak_budget <= 60.10001, peak_budget
                assert p.screen_area().contains(p.rect().translated(p.pos()))
        assert len(stories) >= 2, stories
        assert moved < 1800*.25, moved
        probes=[]
        for _ in range(30):
            start=time.perf_counter()
            desktop_exposed((0,0,100,100),int(p.winId()),(int(p.bubble.winId()),))
            probes.append((time.perf_counter()-start)*1000)
        def stats(values):
            values=sorted(values)
            return dict(mean_ms=round(sum(values)/len(values),3),
                        p95_ms=round(values[int((len(values)-1)*.95)],3),max_ms=round(max(values),3))
        report=dict(kind='synthetic-desktop-and-virtual-clock',seed=20261023,simulated_seconds=1800,
                    stories=dict(stories),position_changed_seconds=round(moved,1),
                    peak_ten_minute_budget_seconds=round(peak_budget,1),
                    scheduler=stats(times),real_windows_occlusion_probe=stats(probes),
                    limitations=['Windows probe is real; story environment is synthetic.',
                                 'Not a real mixed-DPI or Explorer restart test.'])
        folder=Path(__file__).resolve().parents[1]/'output/autoplay-verification'
        folder.mkdir(parents=True,exist_ok=True)
        (folder/'soak.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False))
    finally:
        case.tearDown()
        case.doCleanups()


if __name__ == '__main__':
    main()
