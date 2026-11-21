import ctypes
from ctypes import wintypes
import subprocess
import time
import urllib.request
import json
import os
from pathlib import Path

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

def launch():
    print("Stopping any processes holding port 9444...")
    cmd_ps = "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*9444*' -and ($_.Name -eq 'chrome.exe' -or $_.Name -eq 'msedge.exe') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
    subprocess.run(["powershell", "-NoProfile", "-Command", cmd_ps], capture_output=True)
    time.sleep(1.5)

    profile_dir = Path(os.environ["USERPROFILE"]) / ".tweetytweets" / "edge-profile"
    chrome_path = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    if not chrome_path.exists():
        chrome_path = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

    # Clean Singleton locks
    for f in profile_dir.glob("Singleton*"):
        try:
            f.unlink()
        except Exception:
            pass

    si = STARTUPINFO()
    si.cb = ctypes.sizeof(STARTUPINFO)
    si.lpDesktop = 'WinSta0\\Default'
    si.dwFlags = 1  # STARTF_USESHOWWINDOW
    si.wShowWindow = 1  # SW_SHOWNORMAL
    pi = PROCESS_INFORMATION()

    cmd = (
        f'"{chrome_path}" '
        f'--remote-debugging-port=9444 '
        f'--remote-allow-origins=* '
        f'--user-data-dir="{profile_dir}" '
        f'--new-window '
        f'--window-size=1280,800 '
        f'--window-position=50,50 '
        f'--no-first-run '
        f'--no-default-browser-check '
        f'--disable-background-mode '
        f'"https://x.com/home"'
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

    print(f"Successfully launched Chrome on user desktop with PID: {pi.dwProcessId}")
    
    # Wait for CDP to respond
    for _ in range(15):
        time.sleep(1)
        try:
            res = urllib.request.urlopen("http://127.0.0.1:9444/json/version", timeout=1).read()
            data = json.loads(res)
            print("Browser online:", data.get("Browser"))
            return True
        except Exception:
            pass
    print("Browser did not respond in time.")
    return False

if __name__ == "__main__":
    launch()
