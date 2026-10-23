"""Read-only Windows Shell desktop discovery. No Explorer injection or icon moves.

Coordinates are physical pixels; the Qt adapter converts them per monitor.
All COM pointers and native bitmaps are owned and released within one scan.
"""
import ctypes as C
from ctypes import wintypes as W
import hashlib
import sys
import uuid


class DesktopUnavailable(RuntimeError):
    pass


class GUID(C.Structure):
    _fields_ = [('data', C.c_ubyte * 16)]

    def __init__(self, text):
        super().__init__()
        self.data[:] = uuid.UUID(text).bytes_le


class VariantValue(C.Union):
    _fields_ = [('number', C.c_long), ('padding', C.c_ubyte * (16 if C.sizeof(C.c_void_p) == 8 else 8))]


class VARIANT(C.Structure):
    _fields_ = [('vt', C.c_ushort), ('r1', C.c_ushort), ('r2', C.c_ushort), ('r3', C.c_ushort), ('value', VariantValue)]


class STRRET(C.Structure):
    class Value(C.Union):
        _fields_ = [('wide', C.c_void_p), ('offset', W.UINT), ('text', C.c_char * 260)]
    _fields_ = [('kind', W.UINT), ('value', Value)]


def _call(pointer, slot, types=(), args=(), result=C.c_long):
    table = C.cast(pointer, C.POINTER(C.POINTER(C.c_void_p))).contents
    function = C.WINFUNCTYPE(result, C.c_void_p, *types)(table[slot])
    return function(pointer, *args)


def _check(code, operation):
    if code < 0:
        raise DesktopUnavailable(f'{operation}失败 (0x{code & 0xffffffff:08x})，请刷新桌面图标')


def _query(pointer, iid):
    output = C.c_void_p()
    _check(_call(pointer, 0, (C.POINTER(GUID), C.POINTER(C.c_void_p)), (C.byref(GUID(iid)), C.byref(output))), '读取桌面接口')
    return output


def _api():
    if sys.platform != 'win32':
        raise DesktopUnavailable('此功能目前仅支持 Windows 桌面')
    user = C.WinDLL('user32', use_last_error=True)
    user.FindWindowW.argtypes = [W.LPCWSTR, W.LPCWSTR]; user.FindWindowW.restype = W.HWND
    user.FindWindowExW.argtypes = [W.HWND, W.HWND, W.LPCWSTR, W.LPCWSTR]; user.FindWindowExW.restype = W.HWND
    user.IsWindowVisible.argtypes = [W.HWND]; user.IsIconic.argtypes = [W.HWND]
    user.GetWindowRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
    user.ClientToScreen.argtypes = [W.HWND, C.POINTER(W.POINT)]
    user.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
    user.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
    return user


def _listview(user):
    result = []
    callback_type = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    def inspect(hwnd, unused):
        view = user.FindWindowExW(hwnd, None, 'SHELLDLL_DefView', None)
        if view:
            icons = user.FindWindowExW(view, None, 'SysListView32', None)
            if icons:
                result.append(icons)
        return True
    user.EnumWindows(callback_type(inspect), 0)
    if not result:
        raise DesktopUnavailable('未找到资源管理器桌面，请确认 Windows 桌面已加载')
    return result[0]


def _name(folder, pidl, flags):
    value = STRRET()
    _check(_call(folder, 11, (C.c_void_p, W.DWORD, C.POINTER(STRRET)), (pidl, flags, C.byref(value))), '读取图标名称')
    text = C.create_unicode_buffer(32768)
    helper = C.WinDLL('shlwapi')
    helper.StrRetToBufW.argtypes = [C.POINTER(STRRET), C.c_void_p, W.LPWSTR, W.UINT]
    _check(helper.StrRetToBufW(C.byref(value), pidl, text, len(text)), '转换图标名称')
    return text.value


def _icon_image(pidl, size):
    # Desktop PIDLs are relative to the shell namespace root, hence absolute.
    from PySide6.QtGui import QImage
    shell = C.WinDLL('shell32')
    shell.SHCreateItemFromIDList.argtypes = [C.c_void_p, C.POINTER(GUID), C.POINTER(C.c_void_p)]
    factory = C.c_void_p(); bitmap = C.c_void_p()
    code = shell.SHCreateItemFromIDList(pidl, C.byref(GUID('bcc18b79-ba16-442f-80c4-8a59c30c463b')), C.byref(factory))
    if code < 0:
        return None
    try:
        code = _call(factory, 3, (W.SIZE, W.UINT, C.POINTER(C.c_void_p)), (W.SIZE(size, size), 4, C.byref(bitmap)))
        if code < 0 or not bitmap:
            return None
        # Qt's fromHBITMAP drops alpha. Read the original BGRA DIB instead.
        class Header(C.Structure):
            _fields_ = [('size', W.DWORD), ('width', C.c_long), ('height', C.c_long),
                        ('planes', W.WORD), ('bits', W.WORD), ('compression', W.DWORD),
                        ('bytes', W.DWORD), ('xppm', C.c_long), ('yppm', C.c_long),
                        ('used', W.DWORD), ('important', W.DWORD)]
        header = Header(C.sizeof(Header), size, -size, 1, 32, 0, size*size*4, 0, 0, 0, 0)
        data = (C.c_ubyte * (size*size*4))()
        user = _api(); user.GetDC.argtypes = [W.HWND]; user.GetDC.restype = W.HDC
        user.ReleaseDC.argtypes = [W.HWND, W.HDC]
        gdi = C.WinDLL('gdi32')
        gdi.GetDIBits.argtypes = [W.HDC, C.c_void_p, W.UINT, W.UINT, C.c_void_p, C.c_void_p, W.UINT]
        dc = user.GetDC(None)
        try:
            if not gdi.GetDIBits(dc, bitmap, 0, size, data, C.byref(header), 0):
                return None
            return QImage(bytes(data), size, size, size*4, QImage.Format.Format_ARGB32_Premultiplied).copy()
        finally:
            user.ReleaseDC(None, dc)
    finally:
        if bitmap:
            gdi = C.WinDLL('gdi32'); gdi.DeleteObject.argtypes = [C.c_void_p]; gdi.DeleteObject(bitmap)
        _call(factory, 2, result=W.ULONG)


def _accessible_item(accessible, index, expected_name):
    """Use Explorer's actual item bounds instead of guessed grid padding."""
    child=VARIANT(); child.vt=3; child.value.number=index+1
    name=C.c_void_p()
    if _call(accessible,10,(VARIANT,C.POINTER(C.c_void_p)),(child,C.byref(name)))<0: return None
    try:
        if not name or C.wstring_at(name)!=expected_name: return None
    finally:
        if name:
            automation=C.WinDLL('oleaut32');automation.SysFreeString.argtypes=[C.c_void_p];automation.SysFreeString(name)
    x,y,w,h=C.c_long(),C.c_long(),C.c_long(),C.c_long()
    code=_call(accessible,22,(C.POINTER(C.c_long),)*4+(VARIANT,),(C.byref(x),C.byref(y),C.byref(w),C.byref(h),child))
    return (x.value,y.value,w.value,h.value) if code>=0 and w.value>0 and h.value>0 else None


def scan_desktop(image_id=None, image_ids=()):
    """Return stable IDs, labels and icon rectangles, plus selected icon alpha."""
    user = _api()
    hwnd = _listview(user)
    if not user.IsWindowVisible(hwnd):
        raise DesktopUnavailable('桌面图标已隐藏，请在桌面右键“查看”中显示桌面图标')
    origin = W.POINT(); user.ClientToScreen(hwnd, C.byref(origin))
    ole = C.WinDLL('ole32')
    ole.CoInitializeEx.argtypes = [C.c_void_p, W.DWORD]
    initialized = ole.CoInitializeEx(None, 2)
    if initialized < 0 and initialized != -2147417850:
        _check(initialized, '初始化桌面接口')
    pointers = []
    ole.CoCreateInstance.argtypes = [C.POINTER(GUID), C.c_void_p, W.DWORD, C.POINTER(GUID), C.POINTER(C.c_void_p)]
    ole.CoTaskMemFree.argtypes = [C.c_void_p]
    try:
        windows = C.c_void_p()
        _check(ole.CoCreateInstance(C.byref(GUID('9ba05972-f6a8-11cf-a442-00a0c90a8f39')), None, 4, C.byref(GUID('85cb6900-4d95-11cf-960c-0080c7f4ee85')), C.byref(windows)), '连接资源管理器')
        pointers.append(windows)
        accessible=C.c_void_p()
        accessibility=C.WinDLL('oleacc')
        accessibility.AccessibleObjectFromWindow.argtypes=[W.HWND,W.DWORD,C.POINTER(GUID),C.POINTER(C.c_void_p)]
        if accessibility.AccessibleObjectFromWindow(hwnd,0xfffffffc,C.byref(GUID('618736e0-3c3d-11cf-810c-00aa00389b71')),C.byref(accessible))>=0:
            pointers.append(accessible)
        location, root = VARIANT(), VARIANT(); location.vt = 3; location.value.number = 0
        desktop = C.c_void_p(); desktop_handle = C.c_long()
        _check(_call(windows, 15, (C.POINTER(VARIANT), C.POINTER(VARIANT), C.c_int, C.POINTER(C.c_long), C.c_int, C.POINTER(C.c_void_p)), (C.byref(location), C.byref(root), 8, C.byref(desktop_handle), 1, C.byref(desktop))), '获取桌面视图')
        if not desktop:
            raise DesktopUnavailable('资源管理器暂未提供桌面视图，请稍后刷新')
        pointers.append(desktop)
        provider = _query(desktop, '6d5140c1-7436-11ce-8034-00aa006009fa'); pointers.append(provider)
        browser = C.c_void_p()
        _check(_call(provider, 3, (C.POINTER(GUID), C.POINTER(GUID), C.POINTER(C.c_void_p)), (C.byref(GUID('4c96be40-915c-11cf-99d3-00aa004ae837')), C.byref(GUID('000214e2-0000-0000-c000-000000000046')), C.byref(browser))), '读取桌面浏览器')
        pointers.append(browser)
        view = C.c_void_p()
        _check(_call(browser, 15, (C.POINTER(C.c_void_p),), (C.byref(view),)), '读取桌面文件夹'); pointers.append(view)
        folder_view = _query(view, '1af3a467-214f-4298-908e-06b03e0b39f9'); pointers.append(folder_view)
        folder = C.c_void_p()
        _check(_call(folder_view, 5, (C.POINTER(GUID), C.POINTER(C.c_void_p)), (C.byref(GUID('000214e6-0000-0000-c000-000000000046')), C.byref(folder))), '读取桌面项目'); pointers.append(folder)
        mode, icon_size = W.UINT(), C.c_int()
        _check(_call(folder_view, 36, (C.POINTER(W.UINT), C.POINTER(C.c_int)), (C.byref(mode), C.byref(icon_size))), '读取图标尺寸')
        spacing = W.POINT()
        _check(_call(folder_view, 12, (C.POINTER(W.POINT),), (C.byref(spacing),)), '读取图标间距')
        count = C.c_int()
        _check(_call(folder_view, 7, (W.UINT, C.POINTER(C.c_int)), (2, C.byref(count))), '枚举桌面图标')
        icons = []; image = None; images = {}
        requested=set(image_ids)
        if image_id: requested.add(image_id)
        size = max(16, min(256, icon_size.value))
        for index in range(min(count.value, 2000)):
            pidl = C.c_void_p()
            if _call(folder_view, 6, (C.c_int, C.POINTER(C.c_void_p)), (index, C.byref(pidl))) < 0:
                continue
            try:
                name = _name(folder, pidl, 0)
                identity = _name(folder, pidl, 0x8000)
                point = W.POINT()
                _check(_call(folder_view, 11, (C.c_void_p, C.POINTER(W.POINT)), (pidl, C.byref(point))), '读取图标位置')
                # FVM_ICON positions are the item top-left; glyph is centered
                # in its spacing cell, with the standard two-pixel top inset.
                x = origin.x + point.x + (spacing.x - size) / 2
                y = origin.y + point.y + 2
                bounds=_accessible_item(accessible,index,name) if accessible else None
                if bounds:
                    x=bounds[0]+(bounds[2]-size)/2
                    y=bounds[1]+2
                icon_id = hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24]
                attrs = W.ULONG(0x20000000)
                one = C.c_void_p(pidl.value)
                _call(folder, 9, (W.UINT, C.POINTER(C.c_void_p), C.POINTER(W.ULONG)), (1, C.byref(one), C.byref(attrs)))
                item=dict(id=icon_id,name=name,folder=bool(attrs.value & 0x20000000),rect=dict(x=x,y=y,width=size,height=size))
                if bounds: item['label_rect']=dict(x=bounds[0],y=y+size,width=bounds[2],height=max(1,bounds[1]+bounds[3]-y-size))
                icons.append(item)
                if icon_id in requested:
                    glyph = _icon_image(pidl, size)
                    if glyph is not None: images[icon_id]=glyph
                    if icon_id == image_id: image=glyph
            finally:
                ole.CoTaskMemFree(pidl)
        return {'icons': icons, 'image': image, 'images':images, 'hwnd': int(hwnd)}
    finally:
        for pointer in reversed(pointers):
            if pointer:
                _call(pointer, 2, result=W.ULONG)
        if initialized >= 0:
            ole.CoUninitialize()


def transparent_overlay(user, hwnd):
    """Ignore invisible layered surfaces, not ordinary topmost app windows."""
    get_style = user.GetWindowLongPtrW if C.sizeof(C.c_void_p) == 8 else user.GetWindowLongW
    get_style.argtypes = [W.HWND, C.c_int]
    get_style.restype = C.c_ssize_t
    style = get_style(hwnd, -20)
    if not style & 0x80000:  # WS_EX_LAYERED
        return False
    if style & 0x20:  # WS_EX_TRANSPARENT: non-interactive layered overlay
        return True
    color, alpha, flags = W.DWORD(), W.BYTE(), W.DWORD()
    read = user.GetLayeredWindowAttributes
    read.argtypes = [W.HWND, C.POINTER(W.DWORD), C.POINTER(W.BYTE), C.POINTER(W.DWORD)]
    read.restype = W.BOOL
    return bool(read(hwnd, C.byref(color), C.byref(alpha), C.byref(flags))
                and flags.value & 2 and alpha.value == 0)


def desktop_exposed(rect, ignore_hwnd, ignore_hwnds=()):
    """Conservative occlusion: never draw a resting pet over an ordinary app."""
    user = _api()
    blocked = []
    callback_type = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    x, y, width, height = rect
    def inspect(hwnd, unused):
        if int(hwnd) in (ignore_hwnd, *ignore_hwnds) or not user.IsWindowVisible(hwnd) or user.IsIconic(hwnd):
            return True
        if transparent_overlay(user, hwnd):
            return True
        name = C.create_unicode_buffer(256); user.GetClassNameW(hwnd, name, 256)
        if name.value in ('Progman', 'WorkerW', 'Shell_TrayWnd', 'Shell_SecondaryTrayWnd', 'tooltips_class32'):
            return True
        # Ignore cloaked windows on inactive virtual desktops.
        cloak = W.DWORD()
        dwm = C.WinDLL('dwmapi'); dwm.DwmGetWindowAttribute.argtypes = [W.HWND, W.DWORD, C.c_void_p, W.DWORD]
        if dwm.DwmGetWindowAttribute(hwnd, 14, C.byref(cloak), C.sizeof(cloak)) == 0 and cloak.value:
            return True
        bounds = W.RECT()
        if user.GetWindowRect(hwnd, C.byref(bounds)) and bounds.left < x+width and bounds.right > x and bounds.top < y+height and bounds.bottom > y:
            blocked.append(True); return False
        return True
    user.EnumWindows(callback_type(inspect), 0)
    return not blocked


def set_input_passthrough(hwnd, enabled):
    """Only change our own layered pet window, never an Explorer window."""
    if sys.platform != 'win32': return
    user=_api()
    get=user.GetWindowLongPtrW if C.sizeof(C.c_void_p)==8 else user.GetWindowLongW
    put=user.SetWindowLongPtrW if C.sizeof(C.c_void_p)==8 else user.SetWindowLongW
    get.argtypes=[W.HWND,C.c_int]; get.restype=C.c_ssize_t
    put.argtypes=[W.HWND,C.c_int,C.c_ssize_t]; put.restype=C.c_ssize_t
    style=get(hwnd,-20)
    changed=style|0x20 if enabled else style&~0x20
    if changed!=style: put(hwnd,-20,changed)
