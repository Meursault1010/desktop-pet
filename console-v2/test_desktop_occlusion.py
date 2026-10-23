"""Invisible overlay regression: desktop routes must still avoid visible apps."""
import ctypes as C
from ctypes import wintypes as W
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from desktop_icons import transparent_overlay


class OverlayTests(unittest.TestCase):
    def surface(self, style, alpha=255, flags=2, readable=True):
        def read(hwnd, color, out_alpha, out_flags):
            C.cast(out_alpha, C.POINTER(W.BYTE)).contents.value = alpha
            C.cast(out_flags, C.POINTER(W.DWORD)).contents.value = flags
            return readable
        return SimpleNamespace(GetWindowLongPtrW=Mock(return_value=style),
                               GetWindowLongW=Mock(return_value=style),
                               GetLayeredWindowAttributes=Mock(side_effect=read))

    def test_zero_alpha_fullscreen_overlay_does_not_block(self):
        self.assertTrue(transparent_overlay(self.surface(0x80000, alpha=0), 1))

    def test_layered_mouse_passthrough_overlay_does_not_block(self):
        self.assertTrue(transparent_overlay(self.surface(0x80020, readable=False), 1))

    def test_visible_translucent_window_still_blocks(self):
        self.assertFalse(transparent_overlay(self.surface(0x80000, alpha=128), 1))

    def test_failed_alpha_query_is_conservative(self):
        self.assertFalse(transparent_overlay(self.surface(0x80000, alpha=0, readable=False), 1))

    def test_colorkey_does_not_imply_fully_transparent(self):
        self.assertFalse(transparent_overlay(self.surface(0x80000, alpha=0, flags=1), 1))

    def test_ordinary_window_still_blocks(self):
        self.assertFalse(transparent_overlay(self.surface(0x80), 1))


if __name__ == '__main__':
    unittest.main()
