import sys

if sys.platform == 'darwin':
    try:
        import ctypes

        libobjc = ctypes.CDLL('/usr/lib/libobjc.dylib')
        # Load AppKit so NSApplication class is available
        ctypes.CDLL('/System/Library/Frameworks/AppKit.framework/AppKit')

        libobjc.objc_getClass.restype = ctypes.c_void_p
        libobjc.objc_getClass.argtypes = [ctypes.c_char_p]
        libobjc.sel_registerName.restype = ctypes.c_void_p
        libobjc.sel_registerName.argtypes = [ctypes.c_char_p]
        libobjc.objc_msgSend.restype = ctypes.c_void_p
        libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        cls = libobjc.objc_getClass(b'NSApplication')
        sel = libobjc.sel_registerName(b'sharedApplication')
        if cls and sel:
            # Calling [NSApplication sharedApplication] registers the main
            # bundle with CoreFoundation so CFBundleGetMainBundle() returns
            # a valid non-NULL bundle when Qt's static initializers run.
            libobjc.objc_msgSend(cls, sel)
    except Exception:
        pass
