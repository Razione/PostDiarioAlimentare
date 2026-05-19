import sys

if sys.platform == 'darwin':
    try:
        import ctypes
        from ctypes.util import find_library

        objc = ctypes.CDLL(find_library('objc'))
        ctypes.CDLL(find_library('AppKit'))

        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        objc.objc_msgSend.restype = ctypes.c_void_p
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        ns_app_class = objc.objc_getClass(b'NSApplication')
        shared_app_sel = objc.sel_registerName(b'sharedApplication')
        if ns_app_class and shared_app_sel:
            objc.objc_msgSend(ns_app_class, shared_app_sel)

        ns_bundle_class = objc.objc_getClass(b'NSBundle')
        main_bundle_sel = objc.sel_registerName(b'mainBundle')
        if ns_bundle_class and main_bundle_sel:
            objc.objc_msgSend(ns_bundle_class, main_bundle_sel)
    except Exception:
        pass
