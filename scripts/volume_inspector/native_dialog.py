"""Native bounded TaskDialog for disposable approval acceptance only.

No automated Yes action exists. Timer/close/cancel always refuse. This is a
normal desktop dialog, not credential reauthentication or a secure-attention UI.
"""
import ctypes as C
import os
from ctypes import wintypes as W


def token_context(w):
    token, thread_token = W.HANDLE(), W.HANDLE()
    open_thread = w.bind(w.A, 'OpenThreadToken', [W.HANDLE, W.DWORD, W.BOOL, C.POINTER(W.HANDLE)])
    thread = w.bind(w.K, 'GetCurrentThread', [], W.HANDLE)
    if open_thread(thread(), 8, True, C.byref(thread_token)):
        w.close_handle(thread_token)
        raise PermissionError('Impersonated operator refused')
    if C.get_last_error() != 1008:
        raise PermissionError('Thread identity unavailable')
    w.check(w.open_token(w.process(), 8, C.byref(token)))
    try:
        def value(kind):
            size = W.DWORD()
            w.token_info(token, kind, None, 0, C.byref(size))
            if not 0 < size.value <= 4096:
                raise PermissionError('Bounded token context unavailable')
            buf = C.create_string_buffer(size.value)
            w.check(w.token_info(token, kind, buf, size, C.byref(size)))
            return buf.raw
        session = int.from_bytes(value(12)[:4], 'little')
        elevation = int.from_bytes(value(20)[:4], 'little')
        restricted = bool(w.bind(w.A, 'IsTokenRestricted', [W.HANDLE])(token))
        statistics = value(10)
        if len(statistics) < 16:
            raise PermissionError('Logon identity unavailable')
        u = C.WinDLL('user32', use_last_error=True)
        open_desktop = w.bind(u, 'OpenInputDesktop', [W.DWORD, W.BOOL, W.DWORD], W.HANDLE)
        close_desktop = w.bind(u, 'CloseDesktop', [W.HANDLE])
        desktop = open_desktop(0, False, 1)
        interactive = bool(desktop and session > 0)
        if desktop:
            close_desktop(desktop)
        import hashlib
        return {'sid_hash': hashlib.sha256(w.current_sid().encode()).hexdigest(), 'session': session,
                'logon_hash': hashlib.sha256(statistics[8:16]).hexdigest(), 'elevated': bool(elevation),
                'restricted': restricted, 'interactive': interactive, 'pid': os.getpid()}
    finally:
        w.close_handle(token)


class ActCtx(C.Structure):
    _fields_ = [('size', W.DWORD), ('flags', W.DWORD), ('source', W.LPCWSTR), ('architecture', W.WORD),
                ('language', W.WORD), ('directory', W.LPCWSTR), ('resource', W.LPCWSTR), ('application', W.LPCWSTR), ('module', W.HMODULE)]


CALLBACK = C.WINFUNCTYPE(W.LONG, W.HWND, W.UINT, W.WPARAM, W.LPARAM, C.c_ssize_t)


class Config(C.Structure):
    _pack_ = 1  # CommCtrl.h wraps TASKDIALOGCONFIG in pshpack1.h.
    _fields_ = [('size', W.UINT), ('parent', W.HWND), ('instance', W.HINSTANCE), ('flags', W.DWORD),
                ('common', W.DWORD), ('title', W.LPCWSTR), ('icon', C.c_void_p), ('instruction', W.LPCWSTR),
                ('content', W.LPCWSTR), ('buttons', W.UINT), ('button_array', C.c_void_p), ('default', C.c_int),
                ('radios', W.UINT), ('radio_array', C.c_void_p), ('default_radio', C.c_int), ('verification', W.LPCWSTR),
                ('expanded', W.LPCWSTR), ('expand_text', W.LPCWSTR), ('collapse_text', W.LPCWSTR),
                ('footer_icon', C.c_void_p), ('footer', W.LPCWSTR), ('callback', CALLBACK), ('data', C.c_ssize_t), ('width', W.UINT)]


MANIFEST = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0"><assemblyIdentity version="1.0.0.0" processorArchitecture="*" name="Atlas.SyntheticApproval" type="win32"/><dependency><dependentAssembly><assemblyIdentity type="win32" name="Microsoft.Windows.Common-Controls" version="6.0.0.0" processorArchitecture="*" publicKeyToken="6595b64144ccf1df" language="*"/></dependentAssembly></dependency></assembly>'''


class NativeDialog:
    def __init__(self, w, output):
        self.w, self.output = w, output

    def confirm(self, text, timeout_ms=45000):
        if type(timeout_ms) is not int or not 1000 <= timeout_ms <= 45000 or len(text) > 4096:
            raise ValueError('Bounded dialog required')
        w = self.w
        self.output._write(self.output.root_handle, 'dialog.manifest', MANIFEST)
        ctx = ActCtx()
        ctx.size, ctx.source = C.sizeof(ctx), self.output.root+'\\dialog.manifest'
        create = w.bind(w.K, 'CreateActCtxW', [C.POINTER(ActCtx)], W.HANDLE)
        activate = w.bind(w.K, 'ActivateActCtx', [W.HANDLE, C.POINTER(C.c_size_t)])
        deactivate = w.bind(w.K, 'DeactivateActCtx', [W.DWORD, C.c_size_t])
        release = w.bind(w.K, 'ReleaseActCtx', [W.HANDLE], None)
        handle = create(C.byref(ctx))
        if handle == w.INVALID:
            w.check(False)
        cookie = C.c_size_t()
        result = {'created': False, 'timed_out': False, 'approved': False, 'button': 0, 'verified': False}
        active = False
        try:
            w.check(activate(handle, C.byref(cookie)))
            active = True
            user = C.WinDLL('user32', use_last_error=True)
            send = w.bind(user, 'SendMessageW', [W.HWND, W.UINT, W.WPARAM, W.LPARAM], W.LPARAM)
            @CALLBACK
            def notify(hwnd, notice, elapsed, _unused, _data):
                if notice == 0:
                    result['created'] = True
                if notice == 4 and elapsed >= timeout_ms:
                    result['timed_out'] = True
                    send(hwnd, 0x400+102, 2, 0)  # Cancel only; never approve.
                return 0
            cfg = Config()
            cfg.size, cfg.flags, cfg.common, cfg.default = C.sizeof(cfg), 0x800 | 8, 2 | 8, 2
            cfg.title = 'Atlas — SYNTHETIC recovery approval test'
            cfg.instruction = 'Approve this disposable test recovery only?'
            cfg.content = text
            cfg.verification = 'I reviewed the exact synthetic helper, revision and recovery action.'
            cfg.footer = 'No real Atlas service, Docker container or production registry will change. Cancel keeps the test blocked.'
            cfg.callback, cfg.width = notify, 420
            task = w.bind(C.WinDLL('comctl32', use_last_error=True), 'TaskDialogIndirect',
                          [C.POINTER(Config), C.POINTER(C.c_int), C.c_void_p, C.POINTER(W.BOOL)], W.LONG)
            button, verified = C.c_int(), W.BOOL()
            hr = task(C.byref(cfg), C.byref(button), None, C.byref(verified))
            if hr != 0:
                raise OSError('Native task dialog failed', hr)
            result.update(button=button.value, verified=bool(verified.value))
            result['approved'] = result['created'] and not result['timed_out'] and button.value == 6 and bool(verified.value)
            return result
        finally:
            if active:
                w.check(deactivate(0, cookie))
            release(handle)
