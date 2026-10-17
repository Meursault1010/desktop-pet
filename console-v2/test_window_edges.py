"""Fullscreen classification without touching native windows."""
import unittest
from window_edges import covers_monitor


class FullscreenGeometryTests(unittest.TestCase):
    def test_borderless_fullscreen_and_rounding(self):
        self.assertTrue(covers_monitor((0,0,1920,1080),(0,0,1920,1080)))
        self.assertTrue(covers_monitor((1,1,1918,1078),(0,0,1920,1080)))

    def test_maximized_with_taskbar_and_regular_window_are_not_fullscreen(self):
        self.assertFalse(covers_monitor((0,0,1920,1040),(0,0,1920,1080)))
        self.assertFalse(covers_monitor((200,200,900,600),(0,0,1920,1080)))

    def test_negative_monitor_origin_and_mixed_resolution(self):
        monitor=(-2560,-200,2560,1440)
        self.assertTrue(covers_monitor(monitor,monitor))
        self.assertFalse(covers_monitor((0,0,1920,1080),monitor))
        self.assertFalse(covers_monitor((-2560,-200,1920,1080),monitor))


if __name__=='__main__': unittest.main()
