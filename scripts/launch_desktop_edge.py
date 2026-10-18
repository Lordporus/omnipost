import ctypes
from ctypes import wintypes
import subprocess
import time
import urllib.request
import json

kernel32 = ctypes.windll.kernel32

class STARTUPINFO(ctypes.Structure):
    _fields_ = [
        ('cb', wintypes.DWORD),
        ('lpReserved', wintypes.LPWSTR),
        ('lpDesktop', wintypes.LPWSTR),
        ('lpTitle', wintypes.LPWSTR),
        ('dwX', wintypes.DWORD),
        ('dwY', wintypes.DWORD),
        ('dwXSize', wintypes.DWORD),
        ('dwYSize', wintypes.DWORD),
        ('dwXCountChars', wintypes.DWORD),
        ('dwYCountChars', wintypes.DWORD),
        ('dwFillAttribute', wintypes.DWORD),
        ('dwFlags', wintypes.DWORD),
        ('wShowWindow', wintypes.WORD),
        ('cbReserved2', wintypes.WORD),
        ('lpReserved2', ctypes.c_void_p),
        ('hStdInput', wintypes.HANDLE),
        ('hStdOutput', wintypes.HANDLE),
        ('hStdError', wintypes.HANDLE),
    ]

class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('hProcess', wintypes.HANDLE),
        ('hThread', wintypes.HANDLE),
        ('dwProcessId', wintypes.DWORD),
        ('dwThreadId', wintypes.DWORD),
    ]

def launch_on_user_desktop():
    # 1. Kill any existing edge instances on port 9444
    try:
        data = urllib.request.urlopen('http://127.0.0.1:9444/json/version', timeout=1).read()
    except Exception:
        data = None

    # Find and kill any process holding 9444 or tweetytweets profile
    cmd_ps = "Get-CimInstance Win32_Process -Filter \"Name = 'msedge.exe'\" | Where-Object { $_.CommandLine -like '*9444*' -or $_.CommandLine -like '*tweetytweets*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
    subprocess.run(["powershell", "-NoProfile", "-Command", cmd_ps], capture_output=True)
    time.sleep(1)

    si = STARTUPINFO()
    si.cb = ctypes.sizeof(STARTUPINFO)
    si.lpDesktop = 'WinSta0\\Default'
    si.dwFlags = 1  # STARTF_USESHOWWINDOW
    si.wShowWindow = 1  # SW_SHOWNORMAL
    pi = PROCESS_INFORMATION()

    cmd = (
        r'"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" '
        r'--remote-debugging-port=9444 '
        r'--remote-allow-origins=* '
        r'--user-data-dir="C:\Users\Sachin\.tweetytweets\edge-profile" '
        r'--new-window '
        r'--window-size=1280,800 '
        r'--window-position=50,50 '
        r'"https://x.com/home"'
    )

    ret = kernel32.CreateProcessW(
        None,
        cmd,
        None,
        None,
        False,
        0,
        None,
        None,
        ctypes.byref(si),
        ctypes.byref(pi)
    )

    if not ret:
        err = kernel32.GetLastError()
        print(f"CreateProcessW failed with error code: {err}")
        return False

    print(f"Successfully launched Edge on user desktop WinSta0\\Default with PID: {pi.dwProcessId}")
    return True

if __name__ == '__main__':
    launch_on_user_desktop()
