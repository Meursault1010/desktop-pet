"""Visual roles shared by the native companion surfaces and the workbench."""

PALETTES = {
    'light': dict(bg='#ffffff', canvas='#f0f4f8', fg='#25394b', muted='#617486',
                  hover='#e8eff5', border='#dfe7ee', control='#b9c9d5',
                  accent='#447a9a', on_accent='#ffffff', inset='#f4f7fb',
                  line='#dfe7ee', star='#8daec3', danger='#a44751'),
    'mist': dict(bg='#f6f9fc', canvas='#e8eef3', fg='#25394b', muted='#586e80',
                 hover='#e0eaf2', border='#d7e2ea', control='#b4c6d3',
                 accent='#3d718f', on_accent='#ffffff', inset='#edf3f7',
                 line='#d7e2ea', star='#83a5bd', danger='#a44751'),
    'dark': dict(bg='#192733', canvas='#101b26', fg='#e6eff7', muted='#9baebe',
                 hover='#293e50', border='#2d4050', control='#506b7f',
                 accent='#8ab9d5', on_accent='#101b26', inset='#1e2e3c',
                 line='#2d4050', star='#7499b1', danger='#eea6af'),
}


def palette(theme):
    return PALETTES.get(theme, PALETTES['mist'])


def motion_allowed(reduced=False):
    """Honor both the workbench setting and Windows' animation preference."""
    if reduced:
        return False
    try:
        import ctypes
        enabled = ctypes.c_int(0)
        return bool(ctypes.windll.user32.SystemParametersInfoW(
            0x1042, 0, ctypes.byref(enabled), 0) and enabled.value)
    except (AttributeError, OSError):
        return False
