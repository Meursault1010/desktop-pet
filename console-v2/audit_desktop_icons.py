"""Read-only native-coordinate audit; no Windows input or file mutations."""
import ctypes as C
from ctypes import wintypes as W
from desktop_icons import _api, _listview, _call, _check, GUID, VARIANT, scan_desktop

if __name__=='__main__':
    from PySide6.QtWidgets import QApplication
    app=QApplication([])
    user=_api(); hwnd=_listview(user)
    ole=C.WinDLL('ole32'); ole.CoInitialize(None)
    accessibility=C.WinDLL('oleacc'); pointer=C.c_void_p()
    accessibility.AccessibleObjectFromWindow.argtypes=[W.HWND,W.DWORD,C.POINTER(GUID),C.POINTER(C.c_void_p)]
    _check(accessibility.AccessibleObjectFromWindow(hwnd,0xfffffffc,C.byref(GUID('618736e0-3c3d-11cf-810c-00aa00389b71')),C.byref(pointer)),'读取图标边界')
    try:
        for i,icon in enumerate(scan_desktop()['icons'][:4]):
            child=VARIANT();child.vt=3;child.value.number=i+1
            x,y,w,h=C.c_long(),C.c_long(),C.c_long(),C.c_long()
            _check(_call(pointer,22,(C.POINTER(C.c_long),)*4+(VARIANT,),(C.byref(x),C.byref(y),C.byref(w),C.byref(h),child)),'读取实际边界')
            print('shell glyph:',icon['rect'],'item bounds:',(x.value,y.value,w.value,h.value))
        print('Qt screens:',[(s.geometry().getRect(),s.devicePixelRatio()) for s in app.screens()])
    finally: _call(pointer,2,result=W.ULONG);ole.CoUninitialize()
